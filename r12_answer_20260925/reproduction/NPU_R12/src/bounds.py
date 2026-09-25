"""Optimistic resource lower bounds for safe candidate rejection.
Only strictly larger lower bounds prune: equality may improve secondary bytes.
"""
from __future__ import annotations
import math
from fractions import Fraction

def _ceil_ratio(n, d):
    q=Fraction(n)/Fraction(str(d))
    return -(-q.numerator//q.denominator)
from solver import GraphIndex
from traffic_model import predict_partition_bytes


def candidate_lower_bound(index: GraphIndex, plan: dict, scene: str,
                          bandwidth: int, cache_bandwidth: int = 250) -> dict:
    if scene not in ('A','B','L2') or bandwidth<=0 or cache_bandwidth<=0:
        raise ValueError('invalid scene/bandwidth')
    traffic=predict_partition_bytes(index.graph,plan,scene)
    core_of_sg={sg:k for k,order in enumerate(plan['core_schedules']) for sg in order}
    load={}; owner={int(u):core_of_sg[sg] for u,sg in plan['node_to_subgraph'].items()}
    for u,op in index.ops.items():
        if op['pipe'] in ('PIPE_M','PIPE_V'):
            key=(owner[u],op['pipe']);load[key]=load.get(key,0)+op['cycles']
    per_pipe=max(load.values(),default=0)
    length={}
    for u in index.topo:
        # All formal non-COPY input operations have given fixed compute cycles.
        duration=index.ops[u]['cycles'] if index.ops[u]['pipe'] in ('PIPE_M','PIPE_V') else 0
        length[u]=duration+max((length[p] for p in index.pred[u]),default=0)
    critical=max(length.values(),default=0)
    reads=traffic['pre_spill_copy_in_bytes'];writes=traffic['pre_spill_copy_out_bytes']
    if scene=='L2':
        # Relaxation: every read can choose either resource; writes must use DDR.
        # It ignores compulsory misses, FIFO, capacity and initial emptiness.
        transfer=max(_ceil_ratio(writes,bandwidth),_ceil_ratio(reads+writes,bandwidth+cache_bandwidth))
    else:transfer=_ceil_ratio(reads+writes,bandwidth)
    return {'lower_bound_cycles':max(per_pipe,critical,transfer),
            'fixed_core_pipe_cycles':per_pipe,'compute_critical_path_cycles':critical,
            'relaxed_copy_resource_cycles':transfer,'pre_spill_traffic':traffic,
            'scope':'optimistic lower bound; ignores spill, waits and some overlap constraints'}


def global_compute_lower_bound(index: GraphIndex, cores: int) -> dict:
    """Partition-independent lower bound from fixed compute work and dependencies."""
    if cores<1:raise ValueError('positive core count required')
    wm,wv=index.weight(index.ids)
    length={}
    for u in index.topo:
        duration=index.ops[u]['cycles'] if index.ops[u]['pipe'] in ('PIPE_M','PIPE_V') else 0
        length[u]=duration+max((length[p] for p in index.pred[u]),default=0)
    cp=max(length.values(),default=0)
    return {'global_lower_bound_cycles':max(_ceil_ratio(wm,cores),_ceil_ratio(wv,cores),cp),
            'matrix_cycles':wm,'vector_cycles':wv,'compute_critical_path_cycles':cp,
            'scope':'all partitions on this core count; compute-only optimistic resource bound'}
