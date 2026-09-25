"""Exact pre-spill COPY-byte predictor for official bipartite input graphs.

Derived from the supplied _build_scene_a_tasks/_build_scene_b_tasks. This predicts
partition_added_copy_bytes, NOT spill bytes and NOT actual post-L2 DDR bytes.
Direct op->op input edges are rejected here rather than assigned invented sizes.
"""
from __future__ import annotations
from collections import defaultdict


def predict_partition_bytes(graph: dict, plan: dict, scene: str) -> dict:
    if scene not in ('A','B','L2'):raise ValueError('Unknown scene')
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from multicore_cut_evaluate_problem_1 import _copy_traffic_bytes
    view=derive_multicore_plan(graph,plan)
    op_by_id={o['id']:o for o in graph['ops']}
    tids={t['id']:t for t in graph['tensors']}
    producers=defaultdict(set);consumers=defaultdict(set)
    for edge in graph['edges']:
        s,t=edge['source'],edge['target']
        if s in op_by_id and t in op_by_id:raise ValueError('Predictor only covers task-defined bipartite inputs')
        if s in op_by_id:producers[t].add(s)
        elif t in op_by_id:consumers[s].add(t)
    mapping=view['mapping']
    owner={u:(mapping[u] if scene=='A' else view['core_by_subgraph'][mapping[u]]) for u in mapping}
    reads=writes=0
    for t,tensor in tids.items():
        P={owner[u] for u in producers[t] if u in owner}
        C={owner[u] for u in consumers[t] if u in owner}
        final=any(op_by_id[u]['op']=='COPY_OUT' for u in consumers[t])
        size=tensor['size']
        if scene=='A':
            reads+=size*len(C-P)
            writes+=size*sum(final or not C or bool(C-{p}) for p in P)
        else:
            if C and not P:reads+=size*len(C)
            if P and (final or not C):writes+=size*len(P)
            links=sum(p!=c for p in P for c in C)
            reads+=size*links;writes+=size*links
    original=_copy_traffic_bytes(graph)
    return {'original_graph_copy_bytes':original,'pre_spill_copy_in_bytes':reads,
            'pre_spill_copy_out_bytes':writes,'pre_spill_copy_bytes':reads+writes,
            'predicted_partition_added_copy_bytes':reads+writes-original,
            'scope':'pre-spill COPY volume; Cache hits not subtracted'}
