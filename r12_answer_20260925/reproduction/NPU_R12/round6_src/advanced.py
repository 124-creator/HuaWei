"""Finite, deterministic additions to the frozen solver (official code untouched).

A fixed-placement transfer-critical-path lower bound is used only in B/L2.
Critical paths reconstructed from a previous official trace are diagnostics, not
counterfactual predictions. Every selected improvement is officially evaluated.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT/'src', ROOT/'official/code'):
    if str(p) not in sys.path: sys.path.insert(0, str(p))
from bounds import candidate_lower_bound, global_compute_lower_bound
from solver import GraphIndex, make_plan
from migration import migrate_blocks
from optimizer_v2 import check_plan
from trace_guided_moves import regroup


def plan_hash(plan: dict) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()


def append_idle_cores(plan: dict, cores: int) -> dict:
    if type(cores) is not int or cores < len(plan['core_schedules']):
        raise ValueError('Target must be an integer >= existing core count')
    out = deepcopy(plan)
    out['core_schedules'].extend([] for _ in range(cores-len(out['core_schedules'])))
    return out


def placement_bound(index: GraphIndex, plan: dict, scene: str) -> dict:
    """Optimistic bound under the FIXED placement, not a global optimum bound.

    In B, each remote tensor dependency requires producer compute completion,
    COPY_OUT, 500 cycles, COPY_IN, and only then the consuming computation.
    Assume exclusive DDR service to get optimistic transfer durations. In L2,
    additionally allow every remote read to hit and use the faster 250 BW.
    For A use existing resource bound; Task barriers have different semantics.
    """
    bound = candidate_lower_bound(index, plan, scene, 60, 250)
    if scene == 'A':
        bound['transfer_dependency_path_cycles'] = 0
        return bound
    sgcore = {sg:k for k, seq in enumerate(plan['core_schedules']) for sg in seq}
    owners = {int(u):sgcore[sg] for u, sg in plan['node_to_subgraph'].items()}
    lags = defaultdict(dict)
    for t, producers in index.producers.items():
        size = index.tensors[t]['size']
        read_bw = 250 if scene == 'L2' else 60
        lag = (size + 59)//60 + 500 + (size+read_bw-1)//read_bw
        for v in index.consumers[t]:
            for u in producers:
                if owners[u] != owners[v]:
                    lags[v][u] = max(lags[v].get(u, 0), lag)
    finish = {}
    for v in index.topo:
        finish[v] = index.ops[v]['cycles'] + max(
            (finish[u]+lags[v].get(u, 0) for u in index.pred[v]), default=0)
    value = max(finish.values(), default=0)
    bound['transfer_dependency_path_cycles'] = value
    bound['lower_bound_cycles'] = max(bound['lower_bound_cycles'], value)
    bound['scope'] = 'fixed placement; relaxed transfer-dependent critical path + resources; no optimality equality assumed'
    return bound


def core_candidates(index: GraphIndex, n: int, scene: str, incumbent: int,
                    official: Path, limit: int=6):
    variants=[]; log=[]; seen=set()
    for m in range(1, n):
        lb = global_compute_lower_bound(index, m)['global_lower_bound_cycles']
        if lb > incumbent:
            log.append({'activity':m, 'status':'all_placements_compute_bound_pruned', 'bound':lb})
            continue
        seed, meta = make_plan(index.graph, m, 'chainwave', scene, official, index)
        proposals=[('chainwave', seed, meta)]
        if scene != 'A':
            for w in (0.0, 0.2):
                p, meta = migrate_blocks(index, seed, 60, 500, w)
                proposals.append((f'migrate{w:g}', p, meta))
        for variant, plan, meta in proposals:
            plan = append_idle_cores(plan, n)
            fp=plan_hash(plan)
            if fp in seen:
                log.append({'activity':m,'variant':variant,'status':'duplicate'})
                continue
            seen.add(fp); bound=placement_bound(index, plan, scene)
            if bound['lower_bound_cycles'] > incumbent:
                log.append({'activity':m,'variant':variant,'status':'fixed_placement_bound_pruned','bound':bound})
                continue
            variants.append((plan, {'name':f'active{m}_{variant}', 'activity':m, 'bound':bound,
                                    'construction':meta}))
    def key(item):
        p,meta=item
        return (meta['bound']['lower_bound_cycles'],
                meta['bound']['pre_spill_traffic']['pre_spill_copy_bytes'], meta['name'])
    variants.sort(key=key)
    # First candidate from each surviving activity count, then fill by score.
    chosen=[]; activities=set()
    for x in variants:
        if x[1]['activity'] not in activities:
            chosen.append(x); activities.add(x[1]['activity'])
    for x in variants:
        if x[1]['name'] not in {v[1]['name'] for v in chosen}: chosen.append(x)
    return chosen[:limit], {'considered':log, 'ranked_names':[m['name'] for _,m in variants],
                             'selected_for_evaluation':[m['name'] for _,m in chosen[:limit]],
                             'max_actual_evaluations':limit}


def critical_candidates(index: GraphIndex, base: dict, analysis: dict,
                        scene: str, limit: int=4, max_links: int=24,
                        max_proposals: int=96):
    """One nonrecursive round of whole-block moves from an actual critical chain.

    Limit links and proposal count before expensive exact accounting. Do not
    claim the sum of removed observed gates is a counterfactual time saving.
    """
    n=len(base['core_schedules'])
    blocks,block_of,pred,succ=index.chain_blocks()
    sgcore={sg:k for k,seq in enumerate(base['core_schedules']) for sg in seq}
    opcore={u:sgcore[base['node_to_subgraph'][str(u)]] for u in index.ids}
    owner={}
    for b, members in enumerate(blocks):
        ks={opcore[u] for u in members}
        if len(ks)!=1: return [], {'status':'seed_splits_chain_block'}
        owner[b]=ks.pop()
    gates={(x['core_id'],x['op_id']) for x in analysis['one_observed_critical_chain'] if x['incoming_gate']=='cross_release'}
    links=[x for x in analysis['cross_links_by_post_release_gap']
           if (x['target_core'],x['target_copy_in_id']) in gates][:max_links]
    proposals=[]; supports=[]
    for link in links:
        t=link['tensor_id']; src=link['source_core']; dst=link['target_core']
        pp={block_of[u] for u in index.producers[t] if opcore[u]==src}
        cc={block_of[u] for u in index.consumers[t] if opcore[u]==dst}
        for group,to,label in ((pp,dst,'producer'),(cc,src,'consumer')):
            if group:proposals.append((group,to,[t],label))
        supports.append(pp|cc)
    for i in range(len(links)):
        for j in range(i+1, len(links)):
            group=supports[i]|supports[j]
            if supports[i]&supports[j] and len(group)<=4:
                for to in sorted({owner[b] for b in group}):
                    proposals.append((group,to,[links[i]['tensor_id'],links[j]['tensor_id']],'connected_pair'))
            if len(proposals)>=max_proposals:break
        if len(proposals)>=max_proposals:break
    proposals=proposals[:max_proposals]
    oldbound=placement_bound(index, base, scene)
    oldbytes=oldbound['pre_spill_traffic']['pre_spill_copy_bytes']
    rows=[];seen=set();failed=[]
    for group,to,ts,label in proposals:
        target=dict(owner)
        for b in group:target[b]=to
        changes=tuple(sorted((b,k) for b,k in target.items() if k!=owner[b]))
        if not changes or changes in seen:continue
        seen.add(changes)
        try:
            plan=regroup(index,blocks,target,n,pred,succ)
            bound=placement_bound(index, plan, scene)
        except (ValueError,RuntimeError) as exc:
            failed.append({'changes':changes,'status':'structural_rejection','error':str(exc)})
            continue
        if bound['lower_bound_cycles']>analysis['makespan']:
            failed.append({'changes':changes,'status':'bound_pruned','bound':bound['lower_bound_cycles']})
            continue
        removed=0
        for link in links:
            t=link['tensor_id']
            ps=[u for u in index.producers[t] if opcore[u]==link['source_core']]
            cs=[u for u in index.consumers[t] if opcore[u]==link['target_core']]
            if ps and cs and len({target[block_of[u]] for u in ps+cs})==1:removed+=1
        byte_delta=bound['pre_spill_traffic']['pre_spill_copy_bytes']-oldbytes
        # Ranking heuristic only. Exact bound is used separately for rejection.
        score=(bound['lower_bound_cycles']-oldbound['lower_bound_cycles'])+byte_delta/60-500*removed
        meta={'changes':[{'block':b,'from':owner[b],'to':k} for b,k in changes],
              'trigger_tensors':ts,'side':label,'removed_observed_gates':removed,
              'pre_spill_byte_delta':byte_delta,'rank_score_not_makespan':score,'bound':bound}
        rows.append((score,byte_delta,str(changes),plan,meta))
    rows.sort(key=lambda row:row[:3])
    chosen=[(p,{**m,'name':f'critical_{i:02d}'}) for i,(_,_,_,p,m) in enumerate(rows[:limit])]
    return chosen, {'status':'ok','critical_links_examined':len(links),
                    'proposals_bounded':len(proposals),'distinct_changes':len(seen),
                    'bound_survivors':len(rows),'rejections':failed,
                    'max_actual_evaluations':limit}
