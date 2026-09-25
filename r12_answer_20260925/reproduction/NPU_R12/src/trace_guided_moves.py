"""Bounded diagnostic extension of existing chain-block migration.

Uses observed critical cross-copy gates, not maximum all-operation delay sums.
Not part of the frozen coverage protocol. Original evaluator decides acceptance.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,sys,time
from pathlib import Path
from solver import GraphIndex
from optimizer_v2 import check_plan
from traffic_model import predict_partition_bytes
from bounds import candidate_lower_bound
from residency_proxy import tensor_liveness


def regroup(index,blocks,owner,N,pred,succ):
    level={}
    for b in index.topological(list(range(len(blocks))),pred,succ):level[b]=1+max((level[p] for p in pred[b]),default=-1)
    groups=collections.defaultdict(list)
    for b,members in enumerate(blocks):groups[(level[b],owner[b])].extend(members)
    mapping={};orders=[[] for _ in range(N)]
    for sg,((depth,k),members) in enumerate(sorted(groups.items())):
        orders[k].append(sg)
        for u in members:mapping[str(u)]=sg
    p={'node_to_subgraph':mapping,'core_schedules':orders};check_plan(index,p);return p


def propose(index,base,analysis,cap,bw,limit=10):
    N=len(base['core_schedules']);blocks,block_of,pred,succ=index.chain_blocks()
    cs={sg:k for k,order in enumerate(base['core_schedules']) for sg in order};opcore={u:cs[base['node_to_subgraph'][str(u)]] for u in index.ids}
    owner={}
    for b,members in enumerate(blocks):
        owners={opcore[u] for u in members}
        if len(owners)!=1:raise ValueError('selected base splits an indivisible chain')
        owner[b]=owners.pop()
    critical={(x['core_id'],x['op_id']) for x in analysis['one_observed_critical_chain'] if x['incoming_gate']=='cross_release'}
    links=[x for x in analysis['cross_links_by_post_release_gap'] if (x['target_core'],x['target_copy_in_id']) in critical]
    possibilities=[]
    for link in links:
        t=link['tensor_id'];src=link['source_core'];dst=link['target_core']
        pset={block_of[u] for u in index.producers.get(t,set()) if opcore[u]==src}
        cset={block_of[u] for u in index.consumers.get(t,set()) if opcore[u]==dst}
        for group,to,side in [(pset,dst,'producer'),(cset,src,'consumer')]:
            if group:possibilities.append((group,to,[t],side))
    # Connected pairs of critical gates; bounded before evaluation, no recursive search.
    for i,a in enumerate(links):
        for b in links[i+1:]:
            aset={block_of[u] for u in index.producers.get(a['tensor_id'],set())|index.consumers.get(a['tensor_id'],set())}
            bset={block_of[u] for u in index.producers.get(b['tensor_id'],set())|index.consumers.get(b['tensor_id'],set())}
            if aset&bset:
                group=aset|bset
                if len(group)<=4:
                    for to in sorted({owner[g] for g in group}):possibilities.append((group,to,[a['tensor_id'],b['tensor_id']],'connected_pair'))
    old=predict_partition_bytes(index.graph,base,'B')['pre_spill_copy_bytes']
    bound0=candidate_lower_bound(index,base,'B',bw,250)['lower_bound_cycles']
    candidates=[];seen=set()
    for group,to,ts,side in possibilities:
        proposed=dict(owner)
        for b in group:proposed[b]=to
        key=tuple(sorted((b,k) for b,k in proposed.items() if k!=owner[b]))
        if not key or key in seen:continue
        seen.add(key);plan=regroup(index,blocks,proposed,N,pred,succ)
        traffic=predict_partition_bytes(index.graph,plan,'B')['pre_spill_copy_bytes']
        bound=candidate_lower_bound(index,plan,'B',bw,250)
        if bound['lower_bound_cycles']>analysis['makespan']:continue
        saved=0
        for link in links:
            t=link['tensor_id'];ps=[u for u in index.producers.get(t,set()) if opcore[u]==link['source_core']]
            cs0=[u for u in index.consumers.get(t,set()) if opcore[u]==link['target_core']]
            if ps and cs0 and len({proposed[block_of[u]] for u in ps+cs0})==1:saved+=1
        score=bound['lower_bound_cycles']-bound0+(traffic-old)/bw-500*saved
        meta={'changes':[{'block':b,'from':owner[b],'to':k} for b,k in key],'trigger_tensors':ts,'side':side,
              'removed_observed_critical_links':saved,'pre_spill_byte_delta':traffic-old,'ranking_proxy':score,'candidate_bound':bound}
        candidates.append((score,traffic,json.dumps(key),plan,meta))
    candidates.sort(key=lambda x:x[:3]);return [(p,m) for _,_,_,p,m in candidates[:limit]],{'possible_moves':len(possibilities),'distinct_moves':len(seen),'bound_survivors':len(candidates)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--cases',nargs='*',default=['case_005','case_006','case_010']);ap.add_argument('--limit',type=int,default=10)
    a=ap.parse_args();root=a.root.resolve();official=root/'official';sys.path.insert(0,str(official/'code'))
    from evaluation_validation import read_evaluation_config
    from run_experiments import run_job,source_hash
    cfg=read_evaluation_config(str(official/'data/config.txt'));records=[]
    for case in a.cases:
        g=json.loads((official/'data'/f'{case}.json').read_text());ix=GraphIndex(g);base=json.loads((root/'selected_plans'/f'{case}_n4_B.json').read_text())
        analysis=json.loads((root/'stage3_results/trace'/f'{case}_B.json').read_text());candidates,meta=propose(ix,base,analysis,cfg['capacity'],cfg['bandwidth'],a.limit)
        out=root/'stage3_results/targeted'/case;out.mkdir(parents=True,exist_ok=True)
        (out/'base_internal_liveness_proxy.json').write_text(json.dumps(tensor_liveness(ix,base,cfg['capacity'])))
        rows=[]
        for i,(plan,m) in enumerate(candidates):
            pp=out/f'move_{i:02d}_plan.json';pp.write_text(json.dumps(plan,sort_keys=True))
            r=run_job({'graph':str(official/'data'/f'{case}.json'),'plan':str(pp),'mode':'B','cores':4,'variant':f'trace_move_{i:02d}','output':str(out/f'move_{i:02d}_B.json')},official,30,True,source_hash(official),False)
            rows.append({'candidate':i,'move':m,'status':r['status'],'makespan':r.get('makespan'),'plan':str(pp.relative_to(root))})
        summary={'case':case,'base_makespan':analysis['makespan'],'generation':meta,'rows':rows,'scope':'diagnostic candidates; excluded from frozen fullgrid selection'}
        good=[r for r in rows if r['status']=='ok'];summary['best_candidate']=min(good,key=lambda r:r['makespan']) if good else None
        (out/'summary.json').write_text(json.dumps(summary,indent=2));records.append(summary)
    (root/'stage3_reports/targeted_summary.json').write_text(json.dumps(records,indent=2))
if __name__=='__main__':main()
