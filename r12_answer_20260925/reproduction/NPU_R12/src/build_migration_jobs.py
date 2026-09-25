from pathlib import Path
import json,sys,time,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'official/code'))
from solver import GraphIndex,make_plan
from migration import migrate_blocks
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config
cfg=read_evaluation_config(str(ROOT/'official/data/config.txt'));delay=read_scene_b_config(str(ROOT/'official/data/config.txt'))['cross_core_copy_delay_cycles']
jobs=[];rows=[]
for case in ['case_002','case_005','case_006','case_010','case_016','case_085']:
 path=ROOT/'official/data'/(case+'.json');g=json.loads(path.read_text());ix=GraphIndex(g)
 base,_=make_plan(g,4,'chainwave','B',ROOT/'official',ix)
 seen={}
 for weight in [0.0,0.2]:
  t=time.perf_counter();plan,meta=migrate_blocks(ix,base,cfg['bandwidth'],delay,weight)
  name=f'migrate{weight:g}';out=ROOT/'plans/migration'/(case+'_n4_'+name+'.json');out.parent.mkdir(parents=True,exist_ok=True)
  text=json.dumps(plan,sort_keys=True);out.write_text(text);sha=hashlib.sha256(text.encode()).hexdigest()
  rows.append({'case':case,'variant':name,'meta':meta,'plan_sha256':sha,'seconds':time.perf_counter()-t})
  if sha in seen:continue
  seen[sha]=name
  for mode in ['B','L2']:
   jobs.append({'graph':str(path),'plan':str(out),'mode':mode,'variant':name,'cores':4,
                'output':str(ROOT/'results/migration'/(case+'_'+name+'_'+mode+'.json'))})
  print(case,name,'moves',len(meta['moves']),'bytes',meta['after_pre_spill_bytes'],'seconds',round(time.perf_counter()-t,3),flush=True)
(ROOT/'reports/migration_jobs.json').write_text(json.dumps(jobs,indent=2));(ROOT/'reports/migration_manifest.json').write_text(json.dumps(rows,indent=2))
