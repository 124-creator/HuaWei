"""R7.1: from-scratch R6 control, then bounded scenario-A Task optimization.
Official sources/parameters remain unchanged. Six extra full evaluations at most.
All stages share one soft wall-clock budget; no historical plans are read.
"""
from __future__ import annotations
from task_frontier import ROOT
from solve_round6 import execute,sha,write_json
from run_experiments import run_job,source_hash
from pathlib import Path
import sys,json,time,shutil,argparse,platform

def solve(graph,n,scene,out,budget=600,profile='full'):
 start=time.perf_counter();graph=Path(graph).resolve();out=Path(out).resolve()
 if n<1 or budget<=0 or scene not in ('A','B','L2') or profile not in ('control','bands','full'):raise ValueError('Invalid settings')
 if out.exists() and any(out.iterdir()):raise FileExistsError('Use a new or empty output directory')
 out.mkdir(parents=True,exist_ok=True);remaining=lambda:max(0,budget-(time.perf_counter()-start))
 r={'protocol':'r7.1','case':graph.stem,'cores':n,'scene':scene,'profile':profile,'budget_seconds':budget,'status':'running',
    'graph_sha256':sha(graph),'config_sha256':sha(ROOT/'official/data/config.txt'),'official_source_sha256':source_hash(ROOT/'official'),
    'solver_sources':{str(p.relative_to(ROOT)):sha(p) for folder in ('src','round6_src','round7_src') for p in sorted((ROOT/folder).glob('*.py'))},
    'environment':{'python':sys.version,'platform':platform.platform()},'stages':[],'input_contract':'graph, fixed config, code only; no historical winning plan'}
 write_json(out/'report.json',r)
 cmd=[sys.executable,'-S',str(ROOT/'round6_src/solve_round6.py'),str(graph),'-n',str(n),'--scene',scene,'--budget',str(remaining()),'--out',str(out/'control_r6'),'--profile','full']
 r['control_process']=execute(cmd,max(.1,remaining()+1),out/'control.log')
 rp=out/'control_r6/report.json'
 if not rp.exists():r.update(status='no_valid_control',wall_seconds=time.perf_counter()-start);write_json(out/'report.json',r);return r
 c=json.loads(rp.read_text())
 if c.get('status')!='ok':r.update(status='no_valid_control',wall_seconds=time.perf_counter()-start);write_json(out/'report.json',r);return r
 def import_row(row):return {**row,'plan':out/'control_r6'/row['plan'],'raw':out/'control_r6'/row['raw']}
 def snapshot(row):return {k:str(v.relative_to(out)) if isinstance(v,Path) else v for k,v in row.items()}
 best=import_row(c['selected']);r['control']=snapshot(best);r['v02_control']=snapshot(import_row(c['control']));r['after_bands']=snapshot(best)
 r['control_wall_seconds']=c['wall_seconds'];global_lb=c['global_compute_lower_bound'];r['global_compute_lower_bound']=global_lb
 seen={sha(p) for p in (out/'control_r6').rglob('*plan.json')};seen.add(sha(best['plan']))
 kinds=[] if scene!='A' or profile=='control' else (['bands'] if profile=='bands' else ['bands','reassign'])
 for kind in kinds:
  stage={'kind':kind,'evaluations':[]}
  if best['makespan']<=1.03*global_lb:stage['status']='certified_3percent_stop';r['stages'].append(stage);continue
  if remaining()<1:stage['status']='shared_budget_exhausted';r['stages'].append(stage);continue
  d=out/kind;d.mkdir(exist_ok=True)
  cmd=[sys.executable,'-S',str(ROOT/'round7_src/generate_tasks.py'),'--graph',str(graph),'--plan',str(best['plan']),'--raw',str(best['raw']),'--kind',kind,'--out',str(d)]
  stage['generation_process']=execute(cmd,min(45,remaining()),d/'generate.log')
  if stage['generation_process']['status']!='ok' or not (d/'proposals.json').exists():stage['status']='generation_not_completed';r['stages'].append(stage);continue
  proposals=json.loads((d/'proposals.json').read_text());stage['generation_seconds']=proposals['generation_seconds']
  for item in proposals['rows']:
   name=item['name'];pp=d/item['plan_file'];m=item['meta'];fingerprint=sha(pp)
   entry={'name':name,'plan':str(pp.relative_to(out)),'lower_bound':m['bound']['lower_bound_cycles']}
   if fingerprint in seen:entry['status']='duplicate_plan';stage['evaluations'].append(entry);continue
   seen.add(fingerprint)
   if m['bound']['lower_bound_cycles']>best['makespan']:entry.update(status='bound_pruned',incumbent=best['makespan']);stage['evaluations'].append(entry);continue
   if remaining()<.2:entry['status']='shared_budget_exhausted';stage['evaluations'].append(entry);continue
   row=run_job(dict(graph=str(graph),plan=str(pp),mode=scene,variant=name,cores=n,output=str(d/f'{name}_result.json')),ROOT/'official',min(40,remaining()),False,r['official_source_sha256'],False)
   entry.update(status=row['status'],makespan=row.get('makespan'),wall_seconds=row['wall_seconds'],metadata=str((d/f'{name}_result.json').relative_to(out)))
   stage['evaluations'].append(entry)
   if row['status']=='ok':
    if row['makespan']<m['bound']['lower_bound_cycles']:raise AssertionError('Task activation bound contradicted')
    choice={'name':name,'makespan':row['makespan'],'added_copy_bytes':row['data_movement_bytes']['added_copy_bytes'],'plan':pp,'raw':d/row['official_result_file']}
    if (choice['makespan'],choice['added_copy_bytes'],name)<(best['makespan'],best['added_copy_bytes'],best['name']):best=choice
  stage['status']='completed';r['stages'].append(stage)
  if kind=='bands':r['after_bands']=snapshot(best)
  r['selected']=snapshot(best);write_json(out/'report.json',r)
 shutil.copy2(best['plan'],out/'selected_plan.json');r['selected']=snapshot(best)
 r.update(status='ok',selected_plan_sha256=sha(out/'selected_plan.json'),selected_raw_sha256=sha(best['raw']),wall_seconds=time.perf_counter()-start,completed_within_soft_budget=(time.perf_counter()-start<=budget))
 write_json(out/'report.json',r);return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('graph',type=Path);ap.add_argument('-n','--cores',required=True,type=int);ap.add_argument('--scene',required=True,choices=['A','B','L2']);ap.add_argument('--out',required=True,type=Path)
 ap.add_argument('--budget',type=float,default=600);ap.add_argument('--profile',choices=['control','bands','full'],default='full');a=ap.parse_args();r=solve(a.graph,a.cores,a.scene,a.out,a.budget,a.profile)
 print(json.dumps({k:r.get(k) for k in ('status','case','cores','scene','control','after_bands','selected','wall_seconds')},ensure_ascii=False));return 0 if r['status']=='ok' else 2
if __name__=='__main__':raise SystemExit(main())
