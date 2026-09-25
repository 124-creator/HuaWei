"""R12.0: indexed insertion calendar + observed-Spill local microbatching.

Original R10/R11 and official files remain byte-identical. Profiles:
reference = execute the supplied R11; indexed = R10 + indexed insertion;
full = indexed + at most TWO local Spill-triggered microbatch candidates.
All activities in a request share the same soft budget. No historical scores or
winning plans are read. Reuse in the batch runner is signature-checked only.
"""
from __future__ import annotations
from pathlib import Path
import argparse,json,platform,shutil,sys,time
ROOT=Path(__file__).resolve().parents[1]
for d in ('official/code','src','round6_src','round7_src','round10_src','round11_src','round12_src'):sys.path.insert(0,str(ROOT/d))
from runtime import execute,write_json,sha
from run_experiments import run_job,source_hash
from solver import GraphIndex
from bounds import candidate_lower_bound
from window_bound import bound
from optimizer_v2 import check_plan

def sources():
 return {str(p.relative_to(ROOT)):sha(p) for d in ('official/code','src','round6_src','round7_src','round10_src','round11_src','round12_src') for p in sorted((ROOT/d).glob('*.py'))}

def read_control(folder):
 f=folder/'report.json'
 if not f.is_file():return None
 r=json.loads(f.read_text());s=r.get('selected')
 if r.get('status')!='ok' or not s:return None
 plan=folder/s['plan'];raw=folder/s['raw']
 if sha(plan)!=r['selected_plan_sha256'] or sha(raw)!=r['selected_raw_sha256']:raise ValueError('Control selected digest mismatch')
 d=json.loads(raw.read_text())
 if d['makespan']!=s['makespan']:raise ValueError('Control value mismatch')
 return {'name':s['name'],'makespan':d['makespan'],'added_copy_bytes':d['data_movement_bytes']['added_copy_bytes'],'plan':plan,'raw':raw}

def solve(graph,n,scene,out,budget=600,profile='full'):
 if n<1 or scene not in ('A','B','L2') or budget<=0 or profile not in ('reference','indexed','full'):raise ValueError('Invalid request')
 graph=graph.resolve();out=out.resolve()
 if out.exists() and any(out.iterdir()):raise FileExistsError('Use a fresh/empty output directory')
 out.mkdir(parents=True,exist_ok=True);start=time.perf_counter();remaining=lambda:max(0.0,budget-(time.perf_counter()-start))
 r={'version':'R12.0','status':'running','case':graph.stem,'cores':n,'scene':scene,'profile':profile,'budget_seconds':budget,
    'graph_sha256':sha(graph),'config_sha256':sha(ROOT/'official/data/config.txt'),'official_source_sha256':source_hash(ROOT/'official'),
    'source_files':sources(),'environment':{'python':sys.version,'platform':platform.platform()},'stages':[],
    'input_policy':'Original graph only; no previous result or plan is a solver input; diagnostic observes this request only.'}
 def snap(c):return {k:str(v.relative_to(out)) if isinstance(v,Path) else v for k,v in c.items()} if c else None
 write_json(out/'report.json',r)
 oldentry='round11_src/solve_round11.py' if profile=='reference' else 'round10_src/solve_round10.py'
 folder=out/'control'
 r['control_process']=execute([sys.executable,'-S',str(ROOT/oldentry),str(graph),'-n',str(n),'--scene',scene,'--budget',str(max(.1,remaining()-.5)),'--out',str(folder)],max(.1,remaining()),out/'control.log')
 best=read_control(folder);r['control']=snap(best);write_json(out/'report.json',r)
 ix=None;global_lb=None
 def evaluate(pp,name,timeout):
  nonlocal best,ix,global_lb
  if ix is None:ix=GraphIndex(json.loads(graph.read_text()));global_lb=bound(ix,n)['window_lower_bound']
  p=json.loads(pp.read_text());check_plan(ix,p)
  stage={'name':name,'plan':str(pp.relative_to(out)),'plan_sha256':sha(pp)}
  if best and p==json.loads(best['plan'].read_text()):stage['status']='duplicate_plan';return stage
  lb=candidate_lower_bound(ix,p,scene,60)['lower_bound_cycles'];stage['resource_lower_bound']=lb
  if best and lb>best['makespan']:stage['status']='bound_pruned';return stage
  if remaining()<=.2:stage['status']='budget_exhausted';return stage
  meta=pp.with_suffix('.meta.json')
  row=run_job({'graph':str(graph),'plan':str(pp),'mode':scene,'variant':name,'cores':n,'output':str(meta)},ROOT/'official',min(timeout,remaining()),False,r['official_source_sha256'],False)
  stage.update(status=row['status'],metadata=str(meta.relative_to(out)),evaluation_wall_seconds=row['wall_seconds'])
  if row['status']=='ok':
   raw=meta.parent/row['official_result_file'];z=json.loads(raw.read_text())
   if z['makespan']<global_lb:raise AssertionError('Official result below global compute window bound')
   c={'name':name,'makespan':z['makespan'],'added_copy_bytes':z['data_movement_bytes']['added_copy_bytes'],'plan':pp,'raw':raw}
   stage['candidate']=snap(c)
   if best is None or (c['makespan'],c['added_copy_bytes'],c['name'])<(best['makespan'],best['added_copy_bytes'],best['name']):best=c
  return stage
 if profile!='reference' and remaining()>.5:
  gen=out/'indexed_insertion'
  proc=execute([sys.executable,'-S',str(ROOT/'round12_src/fast_insertion.py'),str(graph),'-n',str(n),'--scene',scene,'--out',str(gen)],min(30,remaining()),out/'indexed_generation.log')
  r['insertion_generation']=proc
  if proc['status']=='ok':r['stages'].append(evaluate(gen/'plan.json','indexed_insertion',120))
  else:r['stages'].append({'name':'indexed_insertion','status':'generation_'+proc['status']})
 r['indexed_selected']=snap(best);r['indexed_wall_seconds']=time.perf_counter()-start;write_json(out/'report.json',r)
 if profile=='full' and best and scene in ('B','L2') and remaining()>.5:
  raw=json.loads(best['raw'].read_text())
  if raw['data_movement_bytes']['spill_added_copy_bytes']>0:
   diag=out/'local_microbatch';base=snap(best);r['residency_seed']=base
   proc=execute([sys.executable,'-S',str(ROOT/'round12_src/residency_bands.py'),str(graph),'--plan',str(best['plan']),'--raw',str(best['raw']),'--out',str(diag)],min(40,remaining()),out/'microbatch_generation.log')
   r['residency_generation']=proc
   if proc['status']=='ok':
    proposals=json.loads((diag/'proposals.json').read_text());r['residency_diagnostic']=proposals['diagnostic']
    for c in proposals['candidates']:
     stage=evaluate(diag/c['plan'],c['name'],45);r['stages'].append(stage);write_json(out/'report.json',r)
   else:r['stages'].append({'name':'local_microbatch','status':'generation_'+proc['status']})
  else:r['stages'].append({'name':'local_microbatch','status':'no_observed_spill'})
 if best:
  shutil.copy2(best['plan'],out/'selected_plan.json')
  shutil.copy2(best['plan'],out/(graph.stem+'_multicore_res.json'))
  r.update(status='ok',selected=snap(best),selected_plan_sha256=sha(out/'selected_plan.json'),selected_raw_sha256=sha(best['raw']))
 else:r['status']='no_valid_solution'
 r['wall_seconds']=time.perf_counter()-start;r['budget_exceeded']=r['wall_seconds']>budget
 write_json(out/'report.json',r);return r

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('graph',type=Path);ap.add_argument('-n','--cores',type=int,required=True);ap.add_argument('--scene',choices=['A','B','L2'],required=True);ap.add_argument('--budget',type=float,default=600);ap.add_argument('--profile',choices=['reference','indexed','full'],default='full');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 r=solve(a.graph,a.cores,a.scene,a.out,a.budget,a.profile);print(json.dumps({k:r.get(k) for k in ('status','case','scene','cores','profile','selected','wall_seconds')},ensure_ascii=False),flush=True);raise SystemExit(0 if r['status']=='ok' else 2)
