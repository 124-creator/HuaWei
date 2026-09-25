"""From-scratch R11 matrix with isolated result directories and checkpointing.
A resume is allowed only with the same exact protocol/source/graph hashes and
rehashes of both selected files. Matrix jobs are not scored using historical CSVs.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,json,sys,time,platform
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'round11_src'))
from runtime import sha,write_json,execute
from solve_round11 import sources

def valid_resume(d,signature):
    p=d/'driver.json'
    if not p.exists():return None
    row=json.loads(p.read_text())
    if row.get('signature')!=signature or row.get('status')!='ok':return None
    rp=d/'report.json'
    if not rp.exists():return None
    r=json.loads(rp.read_text())
    if r.get('status')!='ok':return None
    raw=d/r['selected']['raw'];plan=d/'selected_plan.json'
    if not (raw.is_file() and plan.is_file()):return None
    if sha(raw)!=r['selected_raw_sha256'] or sha(plan)!=r['selected_plan_sha256']:return None
    return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cases',nargs='+',default=['all']);ap.add_argument('--cores',type=int,nargs='+',default=[5]);ap.add_argument('--scenes',nargs='+',default=['B']);ap.add_argument('--profile',choices=['full','control','insertion_only'],default='full');ap.add_argument('--workers',type=int,default=2);ap.add_argument('--budget',type=float,default=600);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--resume',action='store_true');a=ap.parse_args()
    if a.workers<1 or a.budget<=0 or any(s not in ('A','B','L2') for s in a.scenes) or any(n<1 for n in a.cores):ap.error('invalid argument')
    graphs=sorted((ROOT/'official/data').glob('case_*.json'))
    if a.cases!=['all']:
        lookup={p.stem:p for p in graphs}
        if any(c not in lookup for c in a.cases):ap.error('Unknown case name')
        graphs=[lookup[c] for c in a.cases]
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    frozen={'algorithm':'R11.0','cases':[g.stem for g in graphs],'cores':a.cores,'scenes':a.scenes,'profile':a.profile,'budget_seconds':a.budget,
       'sources':sources(),'graph_sha256':{g.stem:sha(g) for g in graphs},'config_sha256':sha(ROOT/'official/data/config.txt'),
       'python':sys.version,'platform':platform.platform(),'selection':'declared set, ascending case filename; not random sampling',
       'new_candidate':'one HEFT-style insertion construction, <=30 s generation, <=120 s official evaluation, residual shared budget',
       'input_policy':'no results/plans from other methods or earlier requests read by solver'}
    manifest=out/'protocol.json'
    if manifest.exists():
        if not a.resume or json.loads(manifest.read_text())!=frozen:raise ValueError('Existing matrix protocol differs or resume not requested')
    else:write_json(manifest,frozen)
    fingerprint=sha(manifest);jobs=[(g,n,s) for g in graphs for n in a.cores for s in a.scenes];records=[];start=time.perf_counter()
    def one(job):
        g,n,s=job;name=f'{g.stem}_n{n}_{s}';d=out/name;signature={'protocol_sha256':fingerprint,'case':g.stem,'cores':n,'scene':s,'profile':a.profile,'graph_sha256':sha(g)}
        old=valid_resume(d,signature) if a.resume else None
        if old:return {**old,'resume_revalidated':True}
        if d.exists() and any(d.iterdir()):
            # Preserve an interrupted/failed attempt instead of silently overwriting it.
            archive=out/'interrupted_attempts';archive.mkdir(exist_ok=True)
            d.rename(archive/(name+'_'+str(time.time_ns())))
        cmd=[sys.executable,'-S',str(ROOT/'round11_src/solve_round11.py'),str(g),'-n',str(n),'--scene',s,'--profile',a.profile,'--budget',str(a.budget),'--out',str(d)]
        proc=execute(cmd,a.budget+5,out/(name+'.driver.log'));rpath=d/'report.json';r=json.loads(rpath.read_text()) if rpath.exists() else {}
        row={'id':name,'case':g.stem,'cores':n,'scene':s,'profile':a.profile,'signature':signature,'process':proc,'status':r.get('status',proc['status']),
             'solver_wall_seconds':r.get('wall_seconds'),'driver_wall_seconds':proc['wall_seconds'],'report':str(rpath.relative_to(ROOT))}
        if row['status']=='ok':
            rp=d/r['selected']['raw'];pp=d/'selected_plan.json'
            if sha(rp)!=r['selected_raw_sha256'] or sha(pp)!=r['selected_plan_sha256']:raise ValueError('Result hash mismatch')
            row.update(makespan=r['selected']['makespan'],added_copy_bytes=r['selected']['added_copy_bytes'],selected_name=r['selected']['name'],
                       control_makespan=r.get('control',{}).get('makespan') if r.get('control') else None,
                       plan=str(pp.relative_to(ROOT)),raw=str(rp.relative_to(ROOT)),plan_sha256=sha(pp),raw_sha256=sha(rp))
        write_json(d/'driver.json',row);return row
    def snapshot():
        statuses={k:sum(r['status']==k for r in records) for k in sorted({r['status'] for r in records})}
        write_json(out/'summary.json',{'declared':len(jobs),'finished':len(records),'statuses':statuses,'complete':len(records)==len(jobs),
            'protocol_sha256':fingerprint,'workers_this_run':a.workers,'batch_wall_seconds':time.perf_counter()-start,'records':sorted(records,key=lambda r:r['id'])})
    snapshot()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(one,j):j for j in jobs}
        for f in as_completed(futures):
            records.append(f.result());snapshot();r=records[-1]
            print(len(records),'/',len(jobs),r['id'],r['status'],r.get('control_makespan'),r.get('makespan'),round(r['driver_wall_seconds'],3),flush=True)
    return 0 if all(r['status']=='ok' for r in records) else 2
if __name__=='__main__':raise SystemExit(main())
