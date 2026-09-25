"""Lightweight no-eviction liveness proxy including internal tensors.

Coordinates are local COMPUTE OP POSITIONS, not cycles. Prefetch, asynchronous
COPY, spills, rematerialization and Pipe overlap are intentionally omitted.
Above-capacity values indicate proxy pressure, never infeasibility.
"""
from __future__ import annotations
from collections import defaultdict
from solver import GraphIndex


def tensor_liveness(index: GraphIndex, plan: dict, capacity: dict) -> dict:
    sg_core={sg:k for k,order in enumerate(plan['core_schedules']) for sg in order}
    sg_rank={sg:i for order in plan['core_schedules'] for i,sg in enumerate(order)}
    owner={u:sg_core[plan['node_to_subgraph'][str(u)]] for u in index.ids}
    topo_rank={u:i for i,u in enumerate(index.topo)};by_core=defaultdict(list)
    for u in index.ids:by_core[owner[u]].append(u)
    result=[]
    for k in range(len(plan['core_schedules'])):
        seq=sorted(by_core[k],key=lambda u:(sg_rank[plan['node_to_subgraph'][str(u)]],topo_rank[u]))
        rank={u:i for i,u in enumerate(seq)}
        for u in seq:
            assert all(owner[v]!=k or rank[v]<rank[u] for v in index.pred[u]),'proxy order violates local data dependency'
        uses=defaultdict(list)
        for i,u in enumerate(seq):
            for t in index.op_inputs[u]|index.op_outputs[u]:uses[t].append((i,u))
        alloc=defaultdict(list);release=defaultdict(list);lives=[]
        for t,touches in uses.items():
            tensor=index.tensors[t];pos='UB' if tensor['pos']=='DDR' else tensor['pos'];size=tensor['size']
            first,last=touches[0][0],touches[-1][0];alloc[first].append((pos,size,t));release[last].append((pos,size,t))
            local_producers=[u for u in index.producers[t] if owner[u]==k]
            category='internal_or_local_output' if local_producers else 'external_or_remote_input'
            lives.append({'tensor_id':t,'pos':pos,'size_bytes':size,'category':category,'first_position':first,'last_position':last,
                'last_use_op':touches[-1][1],'byte_positions':size*(last-first+1),
                'subgraphs_touched':len({plan['node_to_subgraph'][str(u)] for _,u in touches})})
        used={p:0 for p in capacity};peak=used.copy();area=used.copy();overflow=used.copy();timeline=[]
        for i,u in enumerate(seq):
            for p,size,t in alloc[i]:used[p]+=size
            for p in capacity:
                peak[p]=max(peak[p],used[p]);area[p]+=used[p];overflow[p]+=max(0,used[p]-capacity[p])
            timeline.append({'position':i,'op_id':u,'live_before_release_bytes':used.copy()})
            for p,size,t in release[i]:used[p]-=size
        assert not any(used.values())
        result.append({'core_id':k,'positions':len(seq),'no_eviction_peak_bytes':peak,'live_byte_positions':area,
            'over_capacity_byte_positions':overflow,'largest_lifetimes':sorted(lives,key=lambda x:(-x['byte_positions'],x['tensor_id']))[:30],
            'internal_tensor_count':sum(x['category']=='internal_or_local_output' for x in lives),
            'input_tensor_count':sum(x['category']=='external_or_remote_input' for x in lives),
            'all_lifetimes':lives})
    return {'coordinate':'local compute-operation position','scope':'no-eviction proxy, all touched internal and external tensors',
        'NOT_a_capacity_or_spill_certificate':True,'cores':result}
