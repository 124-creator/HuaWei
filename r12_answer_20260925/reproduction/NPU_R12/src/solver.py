"""Deterministic initial NPU solver, v0.1 (not a final competition optimizer).

Two complementary constructions:
  components: preserve every weak compute-dependency component, pack onto cores.
  chainwave: contract nonbranching chains, group same-depth blocks by core.

Only the two prescribed fields are written to the submitted plan. Metadata is a
separate file. Official structural validation is mandatory; full execution
validation requires the official scenario evaluator and is NOT implied here.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

COMPUTE_PIPES = ('PIPE_M', 'PIPE_V')


class GraphIndex:
    def __init__(self, graph: dict[str, Any]):
        from evaluation_validation import validate_graph
        from stub_multicore_cut_and_schedule import _build_op_adjacency, _contract_excluded_copy_nodes
        validate_graph(graph)
        self.graph=graph
        self.ops={o['id']:o for o in graph['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')}
        self.ids=sorted(self.ops)
        _, full_succ = _build_op_adjacency(graph)
        self.pred,self.succ=_contract_excluded_copy_nodes(self.ids,full_succ)
        self.tensors={t['id']:t for t in graph['tensors']}
        self.producers=defaultdict(set); self.consumers=defaultdict(set)
        self.op_inputs=defaultdict(set); self.op_outputs=defaultdict(set)
        for e in graph['edges']:
            u,v=e['source'],e['target']
            if u in self.ops and v in self.tensors:
                self.producers[v].add(u); self.op_outputs[u].add(v)
            if u in self.tensors and v in self.ops:
                self.consumers[u].add(v); self.op_inputs[v].add(u)
        self.external_inputs={t for t in self.consumers if not self.producers[t]}
        self.topo=self.topological(self.ids,self.pred,self.succ)

    @staticmethod
    def topological(ids, pred, succ) -> list[int]:
        degree={u:len(pred[u]) for u in ids}
        ready=deque(sorted(u for u in ids if degree[u]==0)); order=[]
        while ready:
            u=ready.popleft(); order.append(u)
            for v in sorted(succ[u]):
                degree[v]-=1
                if degree[v]==0: ready.append(v)
        if len(order)!=len(ids): raise ValueError('Dependency cycle')
        return order

    def weight(self, members: list[int]) -> tuple[int,int]:
        return tuple(sum(self.ops[u]['cycles'] for u in members if self.ops[u]['pipe']==p)
                     for p in COMPUTE_PIPES)

    def components(self) -> list[list[int]]:
        visited=set(); components=[]
        for root in self.ids:
            if root in visited: continue
            visited.add(root); stack=[root]; comp=[]
            while stack:
                u=stack.pop(); comp.append(u)
                for v in self.pred[u] | self.succ[u]:
                    if v not in visited: visited.add(v); stack.append(v)
            components.append(sorted(comp))
        return components

    def chain_blocks(self):
        # Each merged edge has source out-degree=1 and target in-degree=1.
        # Thus contracting it cannot create an alternate-path quotient cycle.
        seen=set(); blocks=[]
        for u in self.topo:
            if u in seen: continue
            chain=[]; v=u
            while v not in seen:
                chain.append(v); seen.add(v)
                if len(self.succ[v])!=1: break
                w=next(iter(self.succ[v]))
                if len(self.pred[w])!=1: break
                v=w
            blocks.append(chain)
        block_of={u:b for b,members in enumerate(blocks) for u in members}
        bp={b:set() for b in range(len(blocks))}; bs={b:set() for b in bp}
        for u in self.ids:
            for v in self.succ[u]:
                a,b=block_of[u],block_of[v]
                if a!=b: bs[a].add(b);bp[b].add(a)
        return blocks,block_of,bp,bs


def components_plan(index: GraphIndex, cores: int):
    loads=[[0,0] for _ in range(cores)]; mapping={}
    comps=index.components()
    weighted=[(index.weight(c),c) for c in comps]
    weighted.sort(key=lambda x:(-sum(x[0]),x[1][0]))
    for w,comp in weighted:
        k=min(range(cores),key=lambda k:(max(loads[k][j]+w[j] for j in range(2)),sum(loads[k]),k))
        for j in range(2): loads[k][j]+=w[j]
        for u in comp: mapping[str(u)]=k
    used=set(mapping.values())
    return {'node_to_subgraph':mapping,'core_schedules':[[k] if k in used else [] for k in range(cores)]}, {
        'component_count':len(comps),'largest_component_ops':max(map(len,comps),default=0),
        'compute_cycles_by_core':loads,'construction':'preserve weak compute components'}


def chainwave_plan(index: GraphIndex, cores: int, scene: str, bandwidth: float,
                   same_wait: int, cross_wait: int, copy_delay: int):
    blocks,block_of,bp,bs=index.chain_blocks()
    ids=list(range(len(blocks))); topo=index.topological(ids,bp,bs)
    # Separate initialization to make the dependency recurrence explicit.
    level={}
    for b in topo: level[b]=1+max((level[a] for a in bp[b]),default=-1)
    weights={b:index.weight(blocks[b]) for b in ids}
    tail={}
    for b in reversed(topo): tail[b]=sum(weights[b])+max((tail[v] for v in bs[b]),default=0)
    waves=defaultdict(list)
    for b in ids: waves[level[b]].append(b)
    boundary=defaultdict(dict); input_sets={}; output_sets={}
    for b,members in enumerate(blocks):
        member_set=set(members)
        input_sets[b]={t for u in members for t in index.op_inputs[u] if not (index.producers[t] & member_set)}
        output_sets[b]={t for u in members for t in index.op_outputs[u]
                        if not index.consumers[t] or index.consumers[t]-member_set}
    for t, consumers in index.consumers.items():
        for u in index.producers[t]:
            a=block_of[u]
            for b in {block_of[v] for v in consumers}-{a}:
                boundary[(a,b)][t]=index.tensors[t]['size']
    pair_bytes={edge:sum(ts.values()) for edge,ts in boundary.items()}
    block_io={b:input_sets[b]|output_sets[b] for b in ids}
    core_finish=[0.0]*cores; core_has_task=[False]*cores
    assigned={}; block_finish={}; schedules=[[] for _ in range(cores)]; mapping={}; next_sg=0
    all_loads=[[0,0] for _ in range(cores)]
    for depth in sorted(waves):
        group_blocks=[[] for _ in range(cores)]
        group_weights=[[0,0] for _ in range(cores)]
        group_ready=[core_finish[k]+(same_wait if scene=='A' and core_has_task[k] else 0) for k in range(cores)]
        group_io=[set() for _ in range(cores)]; group_io_bytes=[0]*cores
        candidates=sorted(waves[depth],key=lambda b:(-tail[b],-sum(weights[b]),min(blocks[b])))
        for b in candidates:
            def estimate(k):
                ready=group_ready[k]
                for parent in bp[b]:
                    remote=assigned[parent]!=k
                    latency=(cross_wait if remote else same_wait) if scene=='A' else (copy_delay if remote else 0)
                    # Communication is a ranking proxy, not the final simulator.
                    transfer=(2*pair_bytes.get((parent,b),0)/bandwidth) if remote else 0
                    ready=max(ready,block_finish[parent]+latency+transfer)
                w=[group_weights[k][j]+weights[b][j] for j in range(2)]
                io_bytes=group_io_bytes[k]+sum(index.tensors[t]['size'] for t in block_io[b] if t not in group_io[k])
                copy_work=io_bytes/bandwidth
                value=ready+max(w[0],w[1],copy_work)
                return value,ready,io_bytes
            values=[estimate(k) for k in range(cores)]
            k=min(range(cores),key=lambda k:(values[k][0],sum(group_weights[k]),k))
            assigned[b]=k;group_blocks[k].append(b)
            _,group_ready[k],group_io_bytes[k]=values[k]
            group_io[k].update(block_io[b])
            for j in range(2): group_weights[k][j]+=weights[b][j]
        for k in range(cores):
            if not group_blocks[k]: continue
            sg=next_sg;next_sg+=1;schedules[k].append(sg)
            for b in group_blocks[k]:
                for u in blocks[b]: mapping[str(u)]=sg
            copy_work=group_io_bytes[k]/bandwidth
            core_finish[k]=group_ready[k]+max(*group_weights[k],copy_work)
            core_has_task[k]=True
            for b in group_blocks[k]:block_finish[b]=core_finish[k]
            for j in range(2):all_loads[k][j]+=group_weights[k][j]
    return {'node_to_subgraph':mapping,'core_schedules':schedules},{
        'chain_block_count':len(blocks),'wave_count':len(waves),'compute_cycles_by_core':all_loads,
        'construction':'nonbranching chains, same-depth groups, ready/load-aware placement',
        'proxy_finish_cycles':core_finish,
        'proxy_warning':'Not an official Makespan; ignores detailed overlap, spill and time-varying contention.'}


def make_plan(graph: dict, cores: int, variant: str, scene: str, official: Path, index=None):
    if type(cores) is not int or cores<1: raise ValueError('cores must be a positive integer')
    if scene not in ('A','B','L2'): raise ValueError('Unknown scene')
    if variant not in ('components','chainwave','serial'): raise ValueError('Unknown variant')
    from evaluation_validation import read_evaluation_config,validate_task_order
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    index=index or GraphIndex(graph)
    if variant=='serial':
        plan={'node_to_subgraph':{str(u):0 for u in index.ids},'core_schedules':[[0] if index.ids else []]+[[] for _ in range(cores-1)]}
        meta={'construction':'all compute operations on core 0; idle cores permitted'}
    elif variant=='components':plan,meta=components_plan(index,cores)
    else:
        cfg=official/'data/config.txt'; settings=read_evaluation_config(str(cfg))
        a=read_scene_a_config(str(cfg)); b=read_scene_b_config(str(cfg))
        plan,meta=chainwave_plan(index,cores,scene,settings['bandwidth'],
            a['task_same_core_wait_cycles'],a['task_cross_core_wait_cycles'],b['cross_core_copy_delay_cycles'])
    view=derive_multicore_plan(graph,plan)
    validate_task_order(view)  # Stronger than field/quotient validation alone.
    meta.update(variant=variant,scene=scene,cores=cores,compute_ops=len(index.ids),
        subgraphs=len(view['subgraph_ids']),active_cores=sum(bool(x) for x in plan['core_schedules']),
        validation='official_input_and_task_order_passed',execution_validation='not_yet_evaluated',
        cross_subgraph_dependency_pairs=len(view['dependency_pairs']))
    return plan,meta


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('graph',type=Path);ap.add_argument('--official',type=Path,required=True)
    ap.add_argument('-n','--cores',type=int,default=4)
    ap.add_argument('--variant',choices=['components','chainwave','serial'],default='components')
    ap.add_argument('--scene',choices=['A','B','L2'],default='A')
    ap.add_argument('-o','--output',type=Path)
    args=ap.parse_args();official=args.official.resolve();sys.path.insert(0,str(official/'code'))
    from contest_io import _read_json
    started=time.perf_counter();graph=_read_json(str(args.graph))
    plan,meta=make_plan(graph,args.cores,args.variant,args.scene,official)
    output=args.output or args.graph.with_name(args.graph.stem+'_multicore_res.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(plan,ensure_ascii=False,sort_keys=True),encoding='utf-8')
    meta.update(generation_and_validation_seconds=time.perf_counter()-started,
                graph_sha256=hashlib.sha256(args.graph.read_bytes()).hexdigest(),
                plan_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    output.with_suffix('.meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
