"""Frozen v0.2 coverage matrix. Scores always come from unmodified official code.

This is a restartable experiment driver, not a new scheduling algorithm.
1-core B/L2 uses the exact whole-graph singlecore plan for a controlled comparison.
2--5 cores run solve_case_v2, with a fixed budget and optional certified-gap stop.
No previous best per-case plans are injected into the solver.
"""
from __future__ import annotations
import argparse, hashlib, json, os, signal, subprocess, sys, time
from pathlib import Path


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_atomic(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--workers',type=int,default=3);ap.add_argument('--budget',type=float,default=600)
    ap.add_argument('--per-eval-timeout',type=float,default=120);ap.add_argument('--gap',type=float,default=.03)
    ap.add_argument('--baseline-summary',type=Path);ap.add_argument('--cases',nargs='*');ap.add_argument('--resume',action='store_true')
    a=ap.parse_args();root=a.root.resolve();official=root/'official';out=root/'stage3_results/fullgrid';out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(official/'code'))
    from singlecore_evaluate import build_singlecore_plan
    names=('solve_case_v2.py','optimizer_v2.py','migration.py','bounds.py','solver.py','traffic_model.py','run_experiments.py','eval_worker.py')
    signature={'algorithm':'frozen-v0.2','budget_seconds':a.budget,'per_eval_timeout':a.per_eval_timeout,'gap_stop':a.gap,
        'solver_hashes':{x:sha(root/'src'/x) for x in names},
        'official_hashes':{p.name:sha(p) for p in sorted((official/'code').glob('*.py'))},
        'config_sha256':sha(official/'data/config.txt'),
        'python':sys.version,'runtime_flags':['-S'],'one_core_protocol':'single whole-graph plan; evaluated as B and L2, not an optimized singlecore baseline'}
    graphs=sorted((official/'data').glob('case_*.json'))
    if a.cases:graphs=[g for g in graphs if g.stem in set(a.cases)]
    signature['graphs']={g.name:sha(g) for g in graphs}
    manifest=out/'protocol.json'
    if manifest.exists() and json.loads(manifest.read_text())!=signature:raise ValueError('Protocol changed; use a separate output directory')
    write_atomic(manifest,signature)
    jobs=[]
    # Small graphs first: no result-based case selection; full matrix is declared up front.
    for g in sorted(graphs,key=lambda p:(p.stat().st_size,p.name)):
        one=out/'one_core_plans'/g.name;write_atomic(one,build_singlecore_plan(json.loads(g.read_text())))
        for n in (2,3,4,5,1):
            for scene in (('A','B','L2') if n>1 else ('B','L2')):
                ident=f'{g.stem}_n{n}_{scene}';cell=out/ident
                if n==1:
                    target=cell/'evaluation.json'
                    cmd=[sys.executable,'-S',str(root/'src/eval_worker.py'),'--official',str(official),'--graph',str(g),'--mode',scene,'--plan',str(one),'--output',str(target)]
                else:
                    target=cell/'plan.selection.json'
                    cmd=[sys.executable,'-S',str(root/'src/solve_case_v2.py'),str(g),'--official',str(official),'-n',str(n),'--scene',scene,
                        '--budget',str(a.budget),'--per-eval-timeout',str(a.per_eval_timeout),'--relative-gap-stop',str(a.gap),
                        '-o',str(cell/'plan.json'),'--workdir',str(cell/'candidates')]
                    if a.resume:cmd.append('--resume')
                jobs.append({'id':ident,'case':g.stem,'cores':n,'scene':scene,'result':str(target.relative_to(root)),'command':cmd})
    write_atomic(out/'matrix_manifest.json',[{k:v for k,v in j.items() if k!='command'} for j in jobs])
    pending=[];completed=[];running={};start=time.monotonic();stopping=False
    for j in jobs:
        status_file=out/j['id']/'status.json'
        if a.resume and status_file.exists():
            old=json.loads(status_file.read_text());result=root/j['result']
            if old.get('status')=='ok' and result.exists() and sha(result)==old.get('result_sha256'):
                completed.append(old);continue
        if (out/j['id']/'plan.json').exists():raise FileExistsError('Unverified old plan file; preserve or remove explicitly: '+j['id'])
        pending.append(j)
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        while pending or running:
            limit=a.workers
            if a.baseline_summary:
                try:b=json.loads(a.baseline_summary.read_text());baseline_done=b.get('jobs_finished')==9
                except (OSError,ValueError):baseline_done=False
                if not baseline_done:limit=1
            while pending and len(running)<limit and not stopping:
                j=pending.pop(0);cell=out/j['id'];cell.mkdir(parents=True,exist_ok=True)
                log=open(cell/'stdout.log','a');p=subprocess.Popen(j['command'],cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                j.update(pid=p.pid,started_monotonic=time.monotonic());running[p.pid]=(p,j,log)
                write_atomic(cell/'running.json',{k:v for k,v in j.items() if k!='command'})
            for pid,(p,j,log) in list(running.items()):
                elapsed=time.monotonic()-j['started_monotonic'];timeout=a.budget+30
                if p.poll() is None and (elapsed>timeout or stopping):
                    os.killpg(pid,signal.SIGTERM)
                    try:p.wait(timeout=2)
                    except subprocess.TimeoutExpired:os.killpg(pid,signal.SIGKILL);p.wait()
                    status='cancelled' if stopping else 'driver_timeout'
                elif p.poll() is None:continue
                else:status='process_error'
                log.close();rpath=root/j['result'];result={}
                if rpath.exists():
                    try:result=json.loads(rpath.read_text());status=result.get('status',status)
                    except ValueError:status='invalid_result_json'
                row={k:j[k] for k in ('id','case','cores','scene','result')};row.update(status=status,returncode=p.returncode,driver_wall_seconds=elapsed)
                if result:row.update(makespan=result.get('makespan'),selected_variant=result.get('selected_variant'),result_sha256=sha(rpath))
                write_atomic(out/j['id']/'status.json',row);completed.append(row);del running[pid]
                print(j['id'],status,result.get('makespan'),round(elapsed,3),flush=True)
            write_atomic(out/'progress.json',{'requested':len(jobs),'completed':len(completed),'success':sum(r['status']=='ok' for r in completed),
                'running':[j['id'] for _,j,_ in running.values()],'pending':len(pending),'wall_seconds':time.monotonic()-start,'rows':completed})
            if stopping and not running:break
            time.sleep(.25)
    finally:
        for pid,(p,j,log) in running.items():
            try:os.killpg(pid,signal.SIGTERM)
            except ProcessLookupError:pass
    return 0 if len(completed)==len(jobs) and all(r['status']=='ok' for r in completed) else 2
if __name__=='__main__':raise SystemExit(main())
