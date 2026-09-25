"""Bounded subprocess runner. Timeouts are not infeasibility certificates.

Job isolation works on Windows/Linux. For resume, only reuse successful records
whose graph/config/plan/official-code/worker hashes match current inputs.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hash(official: Path) -> str:
    return hashlib.sha256(json.dumps({p.name: sha(p) for p in sorted((official/'code').glob('*.py'))},sort_keys=True).encode()).hexdigest()


def run_job(job: dict, official: Path, timeout: float, resume: bool, code_hash: str, trace: bool) -> dict:
    out = Path(job['output']); graph = Path(job['graph'])
    out.parent.mkdir(parents=True, exist_ok=True)
    plan = Path(job['plan']) if job.get('plan') else None
    worker = Path(__file__).with_name('eval_worker.py')
    signature = {'graph_sha256': sha(graph), 'config_sha256': sha(official/'data/config.txt'),
                 'plan_sha256': sha(plan) if plan else None, 'official_code_sha256': code_hash,
                 'worker_sha256': sha(worker), 'mode': job['mode'], 'runtime_flags': ['-S']}
    if resume and out.exists():
        try:
            old = json.loads(out.read_text(encoding='utf-8'))
            raw = out.with_name(old.get('official_result_file', 'missing'))
            if (old.get('status') == 'ok' and all(old.get(k) == v for k,v in signature.items())
                    and raw.is_file() and sha(raw) == old.get('official_result_sha256')):
                return old
        except (ValueError, OSError):
            pass
    for p in (out, out.with_suffix('.official.json'), out.with_suffix('.trace.json'), out.with_suffix('.log.txt')):
        if p.exists(): p.unlink()
    cmd = [sys.executable, '-S', str(worker), '--official', str(official), '--graph', str(graph),
           '--mode', job['mode'], '--output', str(out)]
    if plan: cmd.extend(['--plan', str(plan)])
    if trace: cmd.append('--trace')
    start = time.perf_counter()
    row = {'case': graph.stem, 'mode': job['mode'], 'variant': job.get('variant', 'single'),
           'requested_cores': job.get('cores', 1), 'timeout_seconds': timeout, **signature}
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        if out.exists(): row.update(json.loads(out.read_text(encoding='utf-8')))
        else: row.update(status='process_error', error=done.stderr[-8000:], returncode=done.returncode)
    except subprocess.TimeoutExpired:
        row.update(status='timeout', error='Per-evaluation subprocess time limit; feasibility is unknown.')
    row['wall_seconds'] = time.perf_counter()-start
    out.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    print(row['case'], row['mode'], row['variant'], row['requested_cores'], row['status'],
          row.get('makespan','-'), round(row['wall_seconds'],3), flush=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--official', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--jobs', type=Path, help='JSON job list; otherwise run all singlecore baselines')
    ap.add_argument('--cases', nargs='*')
    ap.add_argument('--timeout', type=float, default=120)
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--trace', action='store_true')
    args=ap.parse_args()
    if args.timeout <= 0 or args.workers < 1: ap.error('timeout/workers must be positive')
    official=args.official.resolve(); output=args.out.resolve(); output.mkdir(parents=True,exist_ok=True)
    if args.jobs:
        jobs=json.loads(args.jobs.read_text(encoding='utf-8'))
        for job in jobs:
            for k in ('graph','plan','output'):
                if job.get(k) and not Path(job[k]).is_absolute():
                    job[k]=str((args.jobs.resolve().parent/job[k]).resolve())
    else:
        graphs=sorted((official/'data').glob('case_*.json'))
        if args.cases:
            requested=set(args.cases); available={p.stem for p in graphs}
            if requested-available: ap.error('Unknown cases: '+str(sorted(requested-available)))
            graphs=[p for p in graphs if p.stem in requested]
        graphs.sort(key=lambda p:(-p.stat().st_size,p.name))
        jobs=[{'graph':str(p),'mode':'single','output':str(output/(p.stem+'.json'))} for p in graphs]
    outs=[str(Path(j['output']).resolve()) for j in jobs]
    if len(outs)!=len(set(outs)): ap.error('Duplicate job output paths')
    source=source_hash(official); rows=[]; begin=time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(run_job,j,official,args.timeout,args.resume,source,args.trace) for j in jobs]
        for future in as_completed(futures):
            rows.append(future.result())
            summary={'jobs_requested':len(jobs),'jobs_finished':len(rows),'workers':args.workers,
                     'batch_wall_seconds':time.perf_counter()-begin,'rows':sorted(rows,key=lambda r:(r['case'],r['mode'],r.get('requested_cores',1),r.get('variant','')))}
            (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if all(r['status']=='ok' for r in rows) else 2


if __name__=='__main__':
    raise SystemExit(main())
