"""Isolated adapter to unmodified official evaluators (standard library only)."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--official', type=Path, required=True)
    ap.add_argument('--graph', type=Path, required=True)
    ap.add_argument('--mode', choices=['single', 'A', 'B', 'L2'], required=True)
    ap.add_argument('--plan', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--trace', action='store_true')
    args = ap.parse_args()
    sys.path.insert(0, str(args.official.resolve() / 'code'))
    from contest_io import _read_json, format_scene_a_trace_json, format_multicore_result_log
    from evaluation_validation import read_evaluation_config
    from singlecore_evaluate import evaluate_singlecore
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a, read_scene_a_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config
    config = args.official / 'data' / 'config.txt'
    started = time.perf_counter()
    meta = {'case': args.graph.stem, 'mode': args.mode,
            'graph_sha256': sha256(args.graph), 'config_sha256': sha256(config),
            'plan_sha256': sha256(args.plan) if args.plan else None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        graph = _read_json(str(args.graph))
        settings = read_evaluation_config(str(config))
        if args.mode == 'single':
            waits = read_scene_a_config(str(config))
            result = evaluate_singlecore(graph, **settings,
                cross_core_wait=waits['task_cross_core_wait_cycles'],
                same_core_wait=waits['task_same_core_wait_cycles'])
        else:
            if args.plan is None:
                raise ValueError('--plan is required for multicore evaluation')
            plan = _read_json(str(args.plan))
            if args.mode == 'A':
                waits = read_scene_a_config(str(config))
                result = evaluate_scene_a(graph, plan, **settings,
                    cross_core_wait=waits['task_cross_core_wait_cycles'],
                    same_core_wait=waits['task_same_core_wait_cycles'])
            elif args.mode == 'B':
                waits = read_scene_b_config(str(config))
                result = evaluate_scene_b(graph, plan, **settings,
                    cross_core_copy_delay=waits['cross_core_copy_delay_cycles'])
            else:
                waits = read_scene_b_config(str(config))
                result = evaluate_problem_3(graph, plan, **settings,
                    cross_core_copy_delay=waits['cross_core_copy_delay_cycles'],
                    **read_cache_config(str(config)))
        meta.update(status='ok', evaluation_seconds=time.perf_counter()-started,
                    makespan=result['makespan'], num_cores=result['num_cores'],
                    data_movement_bytes=result['data_movement_bytes'],
                    cache_stats=result.get('cache_stats'),
                    memory_peak_by_core=result.get('memory_peak_by_core'))
        raw = args.output.with_suffix('.official.json')
        raw.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        meta['official_result_file'] = raw.name
        meta['official_result_sha256'] = sha256(raw)
        if args.trace:
            args.output.with_suffix('.trace.json').write_text(
                format_scene_a_trace_json(args.graph.name, result), encoding='utf-8')
            args.output.with_suffix('.log.txt').write_text(
                format_multicore_result_log(args.graph.name, result), encoding='utf-8')
        ret = 0
    except Exception as exc:
        meta.update(status='evaluation_error', evaluation_seconds=time.perf_counter()-started,
                    error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        cycle = getattr(exc, 'cycle', None)
        if cycle is not None:
            meta['cycle'] = cycle
        ret = 2
    args.output.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in meta.items() if k not in ('traceback','cycle')}, ensure_ascii=False), flush=True)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
