"""Bounded structural improvements over v0.1; evaluator sources are untouched.

* Component microbatches control scope of official per-subgraph ordering.
* Shared-input residency ordering is a proxy, NOT a capacity certificate.
* Adjacent same-core contraction includes data AND core-order edges, and rejects
  alternate paths that would create a quotient cycle.

No new operations, dependencies, waits, tensor sizes, or hardware settings are
submitted. Every candidate still requires the official execution evaluator.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from copy import deepcopy
import heapq
from pathlib import Path
from typing import Any
from solver import GraphIndex, make_plan


def check_plan(index: GraphIndex, plan: dict) -> dict:
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order
    view = derive_multicore_plan(index.graph, plan)
    validate_task_order(view)
    return view


def canonicalize(plan: dict) -> dict:
    """Only relabel subgraphs, preserving membership, cores, and order."""
    sgids = [sg for order in plan['core_schedules'] for sg in order]
    translate = {old: new for new, old in enumerate(sgids)}
    return {'node_to_subgraph': {str(u): translate[sg] for u, sg in plan['node_to_subgraph'].items()},
            'core_schedules': [[translate[sg] for sg in order] for order in plan['core_schedules']]}


def component_order(index: GraphIndex, components: list[list[int]], policy: str,
                    capacity: dict[str, int]) -> tuple[list[int], dict]:
    """Greedy shared-input live-range proxy on indivisible compute components.

    Treat each component atomically. An external input becomes live at its first
    component and remains until its last component. Internal intermediates and
    actual COPY issue/completion are omitted, so these peaks are NOT official
    physical memory peaks and must not be used as feasibility tests.
    """
    if policy not in ('residency', 'id'):
        raise ValueError('unknown component-order policy')
    inputs = [{t for u in c for t in index.op_inputs[u] if t in index.external_inputs}
              for c in components]
    counts = Counter(t for ts in inputs for t in ts)
    remaining = set(range(len(components))); live = set(); order = []
    used = {p: 0 for p in capacity}; peak = dict(used)
    # Conceptual local position: same DDR->UB convention as official task build.
    def pos(t): return 'UB' if index.tensors[t]['pos'] == 'DDR' else index.tensors[t]['pos']
    def bytes_by_pos(ts):
        d = {p: 0 for p in capacity}
        for t in ts: d[pos(t)] += index.tensors[t]['size']
        return d
    while remaining:
        def score(i):
            new = bytes_by_pos(inputs[i] - live)
            freed = bytes_by_pos(t for t in inputs[i] if counts[t] == 1)
            after = {p: used[p] + new[p] - freed[p] for p in capacity}
            # Penalize residual occupancy, then transient input-only occupancy.
            return (max(after[p] / capacity[p] for p in capacity),
                    sum(after[p] / capacity[p] for p in capacity),
                    max((used[p] + new[p]) / capacity[p] for p in capacity),
                    min(components[i]))
        i = min(remaining, key=score) if policy == 'residency' else min(remaining, key=lambda i: min(components[i]))
        for t in inputs[i] - live:
            used[pos(t)] += index.tensors[t]['size']
            live.add(t)
        for p in peak: peak[p] = max(peak[p], used[p])
        for t in inputs[i]:
            counts[t] -= 1
            if counts[t] == 0:
                live.remove(t); used[pos(t)] -= index.tensors[t]['size']
        order.append(i); remaining.remove(i)
    return order, {'input_only_peak_proxy_bytes': peak,
                   'scope': 'atomic compute-component order; no internal intermediates or actual overlap'}


def component_batch_plan(index: GraphIndex, base: dict, target_ops: int,
                         policy: str, capacity: dict) -> tuple[dict, dict]:
    """Keep original component->core placement; change batching/order only.

    target_ops=0 means one compute component per subgraph. The positive target
    is a soft batch size, not a hard memory/operation constraint.
    """
    if target_ops < 0: raise ValueError('target_ops must be nonnegative')
    cores = len(base['core_schedules'])
    core_of_sg = {sg: k for k, seq in enumerate(base['core_schedules']) for sg in seq}
    groups = [[] for _ in range(cores)]
    for c in index.components():
        owners = {core_of_sg[base['node_to_subgraph'][str(u)]] for u in c}
        if len(owners) != 1: raise ValueError('base splits a compute dependency component')
        groups[owners.pop()].append(c)
    mapping = {}; schedules = [[] for _ in range(cores)]; sg = 0; diagnostics = []
    for k, comps in enumerate(groups):
        cache = getattr(index, '_component_order_cache', None)
        if cache is None:
            cache = {}; index._component_order_cache = cache
        key = (policy, tuple(sorted(capacity.items())), tuple(tuple(c) for c in comps))
        if key not in cache: cache[key] = component_order(index, comps, policy, capacity)
        order, diag = cache[key]
        diagnostics.append(diag)
        batch = []
        def emit():
            nonlocal sg, batch
            if not batch: return
            for u in batch: mapping[str(u)] = sg
            schedules[k].append(sg); sg += 1; batch = []
        for c in (comps[i] for i in order):
            if batch and (target_ops == 0 or len(batch) + len(c) > target_ops): emit()
            batch.extend(c)
        emit()
    plan = {'node_to_subgraph': mapping, 'core_schedules': schedules}
    check_plan(index, plan)
    return plan, {'construction': 'whole components, fixed core placement, ordered microbatches',
                  'target_ops': target_ops, 'order_policy': policy,
                  'subgraphs': sg, 'input_residency_proxy': diagnostics,
                  'execution_validation': 'not_yet_evaluated'}


def quotient_with_order(index: GraphIndex, plan: dict):
    sgids = {sg for order in plan['core_schedules'] for sg in order}
    pred = {sg: set() for sg in sgids}; succ = {sg: set() for sg in sgids}
    mapping = {int(u): sg for u, sg in plan['node_to_subgraph'].items()}
    for u in index.ids:
        a = mapping[u]
        for v in index.succ[u]:
            b = mapping[v]
            if a != b: succ[a].add(b); pred[b].add(a)
    for order in plan['core_schedules']:
        for a, b in zip(order, order[1:]): succ[a].add(b); pred[b].add(a)
    return pred, succ


def has_alternate_path(succ: dict[int, set[int]], a: int, b: int) -> bool:
    """True iff a->...->b path exists besides the direct a->b edge."""
    seen = {a}; stack = list(succ[a] - {b})
    while stack:
        u = stack.pop()
        if u == b: return True
        if u in seen: continue
        seen.add(u); stack.extend(succ[u] - seen)
    return False


def contract_adjacent(index: GraphIndex, base: dict, passes: int = 1) -> tuple[dict, dict]:
    """Greedy *safe* contraction; runtime benefit is NOT guaranteed.

    Each pass tests pairs of currently adjacent same-core subgraphs. No group is
    merged twice per pass; every accepted merge updates the combined DAG.
    """
    if passes < 1: raise ValueError('passes must be positive')
    plan = deepcopy(base); pred, succ = quotient_with_order(index, plan)
    groups = defaultdict(list)
    for u, sg in plan['node_to_subgraph'].items(): groups[sg].append(u)
    counters = {'accepted_merges': 0, 'alternate_path_rejections': 0, 'passes': 0}
    for _ in range(passes):
        changes = 0
        for k, order in enumerate(plan['core_schedules']):
            result = []; i = 0
            while i < len(order):
                a = order[i]
                if i + 1 >= len(order): result.append(a); break
                b = order[i+1]
                if has_alternate_path(succ, a, b):
                    counters['alternate_path_rejections'] += 1
                    result.append(a); i += 1; continue
                # Contraction of comparable vertices in a DAG is legal exactly
                # when there is no path through a third vertex between them.
                new_pred = (pred[a] | pred[b]) - {a, b}
                new_succ = (succ[a] | succ[b]) - {a, b}
                for p in pred[b] | pred[a]:
                    if p not in (a, b): succ[p].discard(b); succ[p].add(a)
                for s in succ[b] | succ[a]:
                    if s not in (a, b): pred[s].discard(b); pred[s].add(a)
                pred[a] = new_pred; succ[a] = new_succ
                del pred[b]; del succ[b]
                for u in groups.pop(b): plan['node_to_subgraph'][u] = a; groups[a].append(u)
                result.append(a); changes += 1; i += 2
            plan['core_schedules'][k] = result
        counters['passes'] += 1; counters['accepted_merges'] += changes
        if not changes: break
    plan = canonicalize(plan); check_plan(index, plan)
    counters.update(construction='adjacent same-core contraction with alternate-path check',
                    subgraphs=sum(map(len, plan['core_schedules'])),
                    execution_validation='not_yet_evaluated')
    return plan, counters


def build_candidates(graph: dict, cores: int, scene: str, official: Path,
                     index: GraphIndex | None = None) -> list[tuple[str, dict, dict]]:
    """A small fixed portfolio, no outcome-adaptive unbounded search."""
    from evaluation_validation import read_evaluation_config
    index = index or GraphIndex(graph)
    cap = read_evaluation_config(str(official/'data/config.txt'))['capacity']
    comp, cm = make_plan(graph, cores, 'components', scene, official, index)
    chain, chm = make_plan(graph, cores, 'chainwave', scene, official, index)
    out = [('components', comp, cm), ('chainwave', chain, chm)]
    if len(index.components()) > 1:
        targets = [512, 2048] if scene == 'A' else [0, 512]
        for target in targets:
            plan, meta = component_batch_plan(index, comp, target, 'residency', cap)
            out.append(('component_ordered' if target == 0 else f'component_batch{target}', plan, meta))
    for passes in ([1, 4] if scene == 'A' else [4]):
        plan, meta = contract_adjacent(index, chain, passes)
        out.append((f'chainmerge{passes}', plan, meta))
    return out


def frontier_plan(index: GraphIndex, base: dict, capacity: dict) -> tuple[dict, dict]:
    """Reorder chain blocks by release-first ready selection, fixed core owners.

    Only tensors touched by >1 chain block on a core contribute to this proxy.
    This ignores within-block peaks, cross-core COPY timing and spills. It is
    an ordering heuristic and never a physical-capacity or timing certificate.
    """
    blocks, block_of, pred, succ = index.chain_blocks()
    core_sg = {sg:k for k,seq in enumerate(base['core_schedules']) for sg in seq}
    owner={}
    for b,members in enumerate(blocks):
        cores={core_sg[base['node_to_subgraph'][str(u)]] for u in members}
        if len(cores)!=1:raise ValueError('base must keep a chain block on one core')
        owner[b]=cores.pop()
    touched={b:{t for u in members for t in index.op_inputs[u] | index.op_outputs[u]}
             for b,members in enumerate(blocks)}
    counts=Counter((owner[b],t) for b,ts in touched.items() for t in ts)
    boundary={b:{t for t in ts if counts[(owner[b],t)]>1} for b,ts in touched.items()}
    counts=Counter((owner[b],t) for b,ts in boundary.items() for t in ts)
    topo=index.topological(list(range(len(blocks))),pred,succ)
    tail={}
    for b in reversed(topo):
        tail[b]=sum(index.weight(blocks[b]))+max((tail[v] for v in succ[b]),default=0)
    live=set();remaining_pred={b:len(pred[b]) for b in pred};ready={b for b,d in remaining_pred.items() if d==0}
    def normalized(t):
        tensor=index.tensors[t];p='UB' if tensor['pos']=='DDR' else tensor['pos']
        return tensor['size']/capacity[p]
    norm={t:normalized(t) for ts in boundary.values() for t in ts}
    schedules=[[] for _ in base['core_schedules']];mapping={};sg=0
    while ready:
        def score(b):
            k=owner[b];new=sum(norm[t] for t in boundary[b] if (k,t) not in live)
            freed=sum(norm[t] for t in boundary[b] if counts[(k,t)]==1)
            return (new-freed,new,-tail[b],min(blocks[b]))
        b=min(ready,key=score);ready.remove(b);k=owner[b]
        for t in boundary[b]:
            live.add((k,t));counts[(k,t)]-=1
            if counts[(k,t)]==0:live.discard((k,t))
        for u in blocks[b]:mapping[str(u)]=sg
        schedules[k].append(sg);sg+=1
        for v in succ[b]:
            remaining_pred[v]-=1
            if remaining_pred[v]==0:ready.add(v)
    if len(mapping)!=len(index.ids):raise ValueError('incomplete frontier order')
    plan={'node_to_subgraph':mapping,'core_schedules':schedules};check_plan(index,plan)
    return plan,{'construction':'fixed chainwave core owners; release-first topological chain-block order',
                 'subgraphs':sg,'execution_validation':'not_yet_evaluated',
                 'proxy_warning':'shared local boundary tensors only; not actual capacity or spill prediction'}


def affinity_components(index: GraphIndex, cores: int, bandwidth: float,
                        reuse_weight: float = 1.0) -> tuple[dict, dict]:
    """Communication-aware component packing with exact incremental input reads.

    For intact independent compute components, new shared-input membership on a
    core adds exactly one pre-spill input COPY. The local finish proxy is still
    approximate; it does not predict overlap, spill, or the official makespan.
    """
    if cores<1 or bandwidth<=0 or reuse_weight<0:raise ValueError('invalid packing parameters')
    comps=index.components();loads=[[0,0] for _ in range(cores)];seen=[set() for _ in range(cores)];mapping={}
    weighted=[]
    for members in comps:
        inputs={t for u in members for t in index.op_inputs[u] if t in index.external_inputs}
        weighted.append((index.weight(members),members,inputs))
    weighted.sort(key=lambda x:(-sum(x[0]),min(x[1])))
    for weight,members,inputs in weighted:
        def score(k):
            marginal=sum(index.tensors[t]['size'] for t in inputs-seen[k])
            return (max(loads[k][j]+weight[j] for j in range(2))+reuse_weight*marginal/bandwidth,
                    sum(loads[k]),k)
        k=min(range(cores),key=score)
        seen[k].update(inputs)
        for j in range(2):loads[k][j]+=weight[j]
        for u in members:mapping[str(u)]=k
    used=set(mapping.values())
    plan={'node_to_subgraph':mapping,'core_schedules':[[k] if k in used else [] for k in range(cores)]}
    check_plan(index,plan)
    return plan,{'construction':'compute-component packing with incremental shared-input read charge',
                 'reuse_weight':reuse_weight,'compute_cycles_by_core':loads,
                 'input_copy_bytes_proxy':sum(index.tensors[t]['size'] for ts in seen for t in ts),
                 'execution_validation':'not_yet_evaluated'}
