"""From-scratch bounded solver; no historical winner/result is read as input.

Protocol r6.1: unchanged v0.2 first, then <=6 lower-activity candidates and
<=4 observed-critical-chain moves, within one shared 600-second SOFT budget.
Every generator and evaluator is isolated in a timeout-controlled subprocess.
A failed generator does not invalidate an already fully evaluated incumbent.
"""
from __future__ import annotations
import argparse,hashlib,json,os,platform,shutil,signal,subprocess,sys,time,traceback
from pathlib import Path
from advanced import ROOT
from run_experiments import run_job, source_hash


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)


def execute(cmd,timeout,log):
    started=time.perf_counter()
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                          text=True,encoding='utf-8',errors='replace',start_new_session=(os.name=='posix'))
    try:
        text,_=proc.communicate(timeout=max(.1,timeout));status='ok' if proc.returncode==0 else 'process_error'
    except subprocess.TimeoutExpired:
        if os.name=='posix':os.killpg(proc.pid,signal.SIGKILL)
        else:proc.kill()
        text,_=proc.communicate();status='timeout'
    Path(log).write_text(text,encoding='utf-8')
    return {'status':status,'returncode':proc.returncode,'wall_seconds':time.perf_counter()-started,
            'timeout_seconds':timeout,'command':cmd}


def solve(graph: Path, n: int, scene: str, out: Path, budget: float=600,
          profile: str='full') -> dict:
    start=time.perf_counter();out=out.resolve();graph=graph.resolve()
    if out.exists() and any(out.iterdir()):raise FileExistsError('Use an empty directory; no stale result reuse')
    if n<1 or budget<=0 or scene not in ('A','B','L2') or profile not in ('base','core','full'):
        raise ValueError('Invalid cores, budget, scene or profile')
    out.mkdir(parents=True,exist_ok=True)
    official=ROOT/'official';control_plan=out/'control.json';control_work=out/'control_work'
    report={'protocol':'r6.1','case':graph.stem,'scene':scene,'cores':n,'profile':profile,
            'budget_seconds':budget,'graph_sha256':sha(graph),'config_sha256':sha(official/'data/config.txt'),
            'official_source_sha256':source_hash(official),
            'solver_sources':{str(p.relative_to(ROOT)):sha(p) for folder in ('round6_src','src') for p in sorted((ROOT/folder).glob('*.py'))},
            'environment':{'python':sys.version,'platform':platform.platform()},'stages':[],
            'status':'running','input_contract':'only graph, configuration and source code; no historical result lookup'}
    write_json(out/'report.json',report)
    def remaining():return max(0,budget-(time.perf_counter()-start))
    cmd=[sys.executable,'-S',str(ROOT/'src/solve_case_v2.py'),str(graph),'--official',str(official),
         '-n',str(n),'--scene',scene,'--budget',str(max(.1,remaining()-.2)),
         '--per-eval-timeout','120','--relative-gap-stop','0.03','--workdir',str(control_work),'-o',str(control_plan)]
    base_process=execute(cmd,remaining()+.5,out/'control.log');report['base_process']=base_process
    sel=control_plan.with_suffix('.selection.json')
    if not sel.exists() or not control_plan.exists():
        report.update(status='no_valid_control',wall_seconds=time.perf_counter()-start)
        write_json(out/'report.json',report);return report
    control=json.loads(sel.read_text(encoding='utf-8'))
    if control.get('status')!='ok':
        report.update(status='no_valid_control',wall_seconds=time.perf_counter()-start)
        write_json(out/'report.json',report);return report
    variant=control['selected_variant']
    meta=json.loads((control_work/f'{variant}_result.json').read_text(encoding='utf-8'))
    raw=control_work/meta['official_result_file']
    if sha(raw)!=meta['official_result_sha256']:raise AssertionError('Control raw hash mismatch')
    best={'name':'control_'+variant,'makespan':meta['makespan'],
          'added_copy_bytes':meta['data_movement_bytes']['added_copy_bytes'],
          'plan':control_plan,'raw':raw}
    global_lb=control['global_compute_bound']['global_lower_bound_cycles']
    def snapshot(row):
        return {k:(str(v.relative_to(out)) if isinstance(v,Path) else v) for k,v in row.items()}
    report['control']=snapshot(best);report['global_compute_lower_bound']=global_lb
    report['control_wall_seconds']=base_process['wall_seconds'];report['after_core']=snapshot(best)
    seen={sha(control_plan)}
    # Include all successful/failed/pruned base candidate plan fingerprints to avoid
    # paying again for exactly the same submitted plan in a subsequent stage.
    for pp in control_work.glob('*_plan.json'):seen.add(sha(pp))
    kinds=[] if profile=='base' else [('core',6)]
    if profile=='full' and scene!='A':kinds.append(('critical',4))
    for kind,limit in kinds:
        stage={'kind':kind,'max_evaluations':limit,'evaluations':[]}
        if global_lb>0 and best['makespan']<=1.03*global_lb:
            stage['status']='certified_3percent_stop';report['stages'].append(stage);continue
        if remaining()<2:
            stage['status']='shared_budget_exhausted';report['stages'].append(stage);continue
        d=out/kind;d.mkdir(exist_ok=True)
        generator=[sys.executable,'-S',str(ROOT/'round6_src/generate.py'),'--graph',str(graph),
                   '--plan',str(best['plan']),'--raw',str(best['raw']),'--scene',scene,
                   '--kind',kind,'--limit',str(limit),'--out',str(d)]
        stage['generation_process']=execute(generator,min(45,remaining()),d/'generate.log')
        path=d/'proposals.json'
        if stage['generation_process']['status']!='ok' or not path.exists():
            stage['status']='generation_not_completed';report['stages'].append(stage);continue
        generated=json.loads(path.read_text(encoding='utf-8'));stage['generation']=generated['metadata']
        for item in generated['rows']:
            pp=d/item['plan_file'];m=item['meta'];fp=sha(pp)
            if fp in seen:
                stage['evaluations'].append({'name':m['name'],'status':'duplicate_plan'});continue
            seen.add(fp)
            if m['bound']['lower_bound_cycles']>best['makespan']:
                stage['evaluations'].append({'name':m['name'],'status':'bound_pruned',
                    'bound':m['bound']['lower_bound_cycles'],'incumbent':best['makespan']});continue
            if remaining()<.25:
                stage['evaluations'].append({'name':m['name'],'status':'shared_budget_exhausted'});continue
            name=m['name'];row=run_job({'graph':str(graph),'plan':str(pp),'mode':scene,
                'variant':name,'cores':n,'output':str(d/f'{name}_result.json')},official,
                min(40,remaining()),False,report['official_source_sha256'],False)
            stage['evaluations'].append({'name':name,'status':row['status'],'makespan':row.get('makespan'),
                'wall_seconds':row['wall_seconds'],'bound':m['bound']['lower_bound_cycles'],
                'metadata':str((d/f'{name}_result.json').relative_to(out)),
                'plan':str(pp.relative_to(out))})
            if row['status']=='ok':
                if row['makespan']<m['bound']['lower_bound_cycles']:
                    raise AssertionError('New transfer-path lower bound contradicted by official result')
                candidate={'name':name,'makespan':row['makespan'],
                    'added_copy_bytes':row['data_movement_bytes']['added_copy_bytes'],
                    'plan':pp,'raw':d/row['official_result_file']}
                if (candidate['makespan'],candidate['added_copy_bytes'],name)<(best['makespan'],best['added_copy_bytes'],best['name']):best=candidate
        stage['status']='completed';report['stages'].append(stage)
        if kind=='core':report['after_core']=snapshot(best)
        report['selected']=snapshot(best);write_json(out/'report.json',report)
    selected=out/'selected_plan.json';shutil.copy2(best['plan'],selected)
    report['selected']=snapshot(best)
    report.update(status='ok',wall_seconds=time.perf_counter()-start,
                  selected_plan_sha256=sha(selected),selected_raw_sha256=sha(best['raw']),
                  completed_within_soft_budget=(time.perf_counter()-start<=budget),
                  additional_evaluations=sum(e.get('status') in ('ok','timeout','evaluation_error','process_error') for st in report['stages'] for e in st['evaluations']))
    write_json(out/'report.json',report)
    return report


def main():
    ap=argparse.ArgumentParser();ap.add_argument('graph',type=Path);ap.add_argument('-n','--cores',type=int,required=True)
    ap.add_argument('--scene',choices=['A','B','L2'],required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--budget',type=float,default=600);ap.add_argument('--profile',choices=['base','core','full'],default='full')
    a=ap.parse_args()
    r=solve(a.graph,a.cores,a.scene,a.out,a.budget,a.profile)
    print(json.dumps({k:r.get(k) for k in ('status','case','scene','cores','control','after_core','selected','wall_seconds')},ensure_ascii=False))
    return 0 if r['status']=='ok' else 2
if __name__=='__main__':raise SystemExit(main())
