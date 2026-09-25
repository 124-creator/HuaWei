"""One bounded sweep of chain-block migration with exact pre-spill COPY deltas.

The surrogate combines fixed-core compute load, global COPY service work and an
optional discounted cross-link delay. It is NOT an exact makespan prediction.
Only two fixed weight settings are tested; no unbounded parameter search.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from copy import deepcopy
from solver import GraphIndex
from optimizer_v2 import check_plan


def migrate_blocks(index: GraphIndex, base: dict, bandwidth: float,
                   copy_delay: int, sync_weight: float = 0.0,
                   max_moves: int = 32, max_blocks: int = 512):
    if bandwidth<=0 or sync_weight<0 or max_moves<0 or max_blocks<0:raise ValueError('invalid migration controls')
    blocks,block_of,pred,succ=index.chain_blocks();N=len(base['core_schedules'])
    core_sg={sg:k for k,seq in enumerate(base['core_schedules']) for sg in seq}
    core={u:core_sg[base['node_to_subgraph'][str(u)]] for u in index.ids}
    owner={}
    for b,members in enumerate(blocks):
        owners={core[u] for u in members}
        if len(owners)!=1:raise ValueError('base splits a chain block')
        owner[b]=owners.pop()
    weights={b:index.weight(members) for b,members in enumerate(blocks)}
    loads=[[0,0] for _ in range(N)]
    for b,k in owner.items():
        for j in range(2):loads[k][j]+=weights[b][j]
    pc={t:Counter(core[u] for u in ps) for t,ps in index.producers.items()}
    cc={t:Counter(core[u] for u in cs) for t,cs in index.consumers.items()}
    for t in index.tensors:pc.setdefault(t,Counter());cc.setdefault(t,Counter())
    final=set();all_ops={o['id']:o for o in index.graph['ops']}
    for e in index.graph['edges']:
        if e['source'] in index.tensors and e['target'] in all_ops and all_ops[e['target']]['op']=='COPY_OUT':final.add(e['source'])
    touch=defaultdict(dict)
    for t in index.tensors:
        pby=Counter(block_of[u] for u in index.producers[t]);cby=Counter(block_of[u] for u in index.consumers[t])
        for b in pby.keys()|cby.keys():touch[b][t]=(pby[b],cby[b])
    def cost(t,p,c):
        P={k for k,v in p.items() if v>0};C={k for k,v in c.items() if v>0}
        links=sum(a!=b for a in P for b in C)
        copies=(len(C) if C and not P else 0)+(len(P) if P and (t in final or not C) else 0)+2*links
        return copies*index.tensors[t]['size'],links
    initial={t:cost(t,pc[t],cc[t]) for t in index.tensors}
    total_bytes=sum(v[0] for v in initial.values());total_links=sum(v[1] for v in initial.values())
    before_bytes=total_bytes;before_links=total_links
    def peak(ls):return max((v for pair in ls for v in pair),default=0)
    initial_peak=peak(loads)
    # Prefer blocks touching expensive existing cross-core tensor links.
    candidates=sorted(range(len(blocks)),key=lambda b:(-sum(index.tensors[t]['size']*initial[t][1] for t in touch[b]),-sum(weights[b]),min(blocks[b])))[:max_blocks]
    moves=[];checks=0
    for b in candidates:
        if len(moves)>=max_moves:break
        src=owner[b];best=None;old_peak=peak(loads)
        targets={owner[p] for p in pred[b]|succ[b]}-{src}
        for dst in sorted(targets):
            checks+=1;dbytes=0;dlinks=0
            for t,(np,nc) in touch[b].items():
                before=cost(t,pc[t],cc[t]);p=pc[t].copy();c=cc[t].copy()
                p[src]-=np;p[dst]+=np;c[src]-=nc;c[dst]+=nc
                after=cost(t,p,c);dbytes+=after[0]-before[0];dlinks+=after[1]-before[1]
            new_loads=[pair[:] for pair in loads]
            for j in range(2):new_loads[src][j]-=weights[b][j];new_loads[dst][j]+=weights[b][j]
            delta=peak(new_loads)-old_peak+dbytes/bandwidth+sync_weight*copy_delay*dlinks/max(1,N)
            proposal=(delta,dbytes,dlinks,dst,new_loads)
            if delta < -1e-9 and (best is None or proposal[:4]<best[:4]):best=proposal
        if best is None:continue
        delta,dbytes,dlinks,dst,loads=best
        for t,(np,nc) in touch[b].items():
            pc[t][src]-=np;pc[t][dst]+=np;cc[t][src]-=nc;cc[t][dst]+=nc
        owner[b]=dst;total_bytes+=dbytes;total_links+=dlinks
        moves.append({'block':b,'ops':len(blocks[b]),'source_core':src,'target_core':dst,
                      'copy_byte_delta':dbytes,'cross_link_delta':dlinks,'surrogate_delta_cycles':delta})
    if not moves:plan=deepcopy(base)
    else:
        topo=index.topological(list(range(len(blocks))),pred,succ);level={}
        for b in topo:level[b]=1+max((level[p] for p in pred[b]),default=-1)
        groups=defaultdict(list)
        for b,members in enumerate(blocks):groups[(level[b],owner[b])].extend(members)
        mapping={};schedules=[[] for _ in range(N)]
        for sg,((depth,k),members) in enumerate(sorted(groups.items())):
            schedules[k].append(sg)
            for u in members:mapping[str(u)]=sg
        plan={'node_to_subgraph':mapping,'core_schedules':schedules}
    check_plan(index,plan)
    from traffic_model import predict_partition_bytes
    exact=predict_partition_bytes(index.graph,plan,'B')
    if exact['pre_spill_copy_bytes']!=total_bytes:raise AssertionError('incremental COPY accounting mismatch')
    return plan,{'construction':'bounded chain-block migration, tensor-exact COPY deltas; level/core regrouping',
                'sync_weight':sync_weight,'moves':moves,'candidate_core_checks':checks,'blocks_considered_limit':max_blocks,
                'before_pre_spill_bytes':before_bytes,'after_pre_spill_bytes':total_bytes,
                'before_cross_links':before_links,'after_cross_links':total_links,
                'before_max_core_pipe_cycles':initial_peak,'after_max_core_pipe_cycles':peak(loads),
                'execution_validation':'not_yet_evaluated','proxy_warning':'surrogate gains require official re-evaluation'}
