"""Run independent from-scratch requests; resumable only with verified evidence.

Uses no historical plan in optimization. Existing *same-protocol* completed jobs
may be reused only for resuming, retaining their original measured wall time.
"""
from __future__ import annotations
import argparse,collections,hashlib,itertools,json,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from solve_round7 import ROOT,write_json,sha


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cases',nargs='+',default=['all'])
    ap.add_argument('--cores',nargs='+',type=int,default=[5]);ap.add_argument('--scenes',nargs='+',default=['B'])
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workers',type=int,default=3)
    ap.add_argument('--profile',choices=['control','bands','full'],default='full');ap.add_argument('--budget',type=float,default=600)
    ap.add_argument('--resume',action='store_true');a=ap.parse_args()
    cases=sorted(p.stem for p in (ROOT/'official/data').glob('case_*.json')) if a.cases==['all'] else sorted(set(a.cases))
    if not cases or a.workers<1 or any(n<1 for n in a.cores) or any(s not in ('A','B','L2') for s in a.scenes):ap.error('invalid arguments')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    sources={str(p.relative_to(ROOT)):sha(p) for folder in ('round7_src','round6_src','src','official/code') for p in sorted((ROOT/folder).glob('*.py'))}
    manifest={'protocol':'r7.1','cases':cases,'cores':a.cores,'scenes':a.scenes,'profile':a.profile,'budget':a.budget,
              'sources':sources,'graphs':{c:sha(ROOT/'official/data'/f'{c}.json') for c in cases},
              'config_sha256':sha(ROOT/'official/data/config.txt')}
    mp=out/'manifest.json'
    if mp.exists():
        if not a.resume or json.loads(mp.read_text(encoding='utf-8'))!=manifest:ap.error('existing directory/protocol mismatch')
    else:write_json(mp,manifest)
    jobs=list(itertools.product(cases,a.cores,a.scenes));start=time.perf_counter();rows=[]
    def run(job):
        c,n,s=job;ident=f'{c}_n{n}_{s}';d=out/ident;rf=d/'report.json'
        if a.resume and rf.exists():
            old=json.loads(rf.read_text(encoding='utf-8'))
            if old.get('status')=='ok' and sha(d/'selected_plan.json')==old['selected_plan_sha256'] and sha(d/old['selected']['raw'])==old['selected_raw_sha256']:
                return {'id':ident,'status':'ok','reused':True,'report':str(rf.relative_to(out)),
                        'control':old['control']['makespan'],'after_bands':old['after_bands']['makespan'],
                        'makespan':old['selected']['makespan'],'wall_seconds':old['wall_seconds']}
        if d.exists():
            # Never overwrite incomplete evidence: archive it, then retry fresh.
            d.rename(out/(ident+'_prior_'+str(time.time_ns())))
        cmd=[sys.executable,'-S',str(ROOT/'round7_src/solve_round7.py'),str(ROOT/'official/data'/f'{c}.json'),
             '-n',str(n),'--scene',s,'--out',str(d),'--budget',str(a.budget),'--profile',a.profile]
        st=time.perf_counter()
        with (out/(ident+'.driver.log')).open('w',encoding='utf-8') as log:
            p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
        r=json.loads(rf.read_text(encoding='utf-8')) if rf.exists() else {}
        status='ok' if p.returncode==0 and r.get('status')=='ok' else 'driver_error'
        row={'id':ident,'status':status,'returncode':p.returncode,'reused':False,'report':str(rf.relative_to(out)),
             'driver_wall_seconds':time.perf_counter()-st}
        if status=='ok':row.update(control=r['control']['makespan'],after_bands=r['after_bands']['makespan'],makespan=r['selected']['makespan'],wall_seconds=r['wall_seconds'])
        print(ident,status,row.get('control'),row.get('makespan'),round(row['driver_wall_seconds'],2),flush=True)
        return row
    def save():write_json(out/'summary.json',{'requested':len(jobs),'finished':len(rows),
        'statuses':dict(collections.Counter(r['status'] for r in rows)),
        'batch_wall_seconds':time.perf_counter()-start,'workers':a.workers,
        'rows':sorted(rows,key=lambda r:r['id'])})
    save()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        fs=[pool.submit(run,j) for j in jobs]
        for f in as_completed(fs):rows.append(f.result());save()
    return 0 if all(r['status']=='ok' for r in rows) else 2
if __name__=='__main__':raise SystemExit(main())
