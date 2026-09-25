from pathlib import Path
import sys,json,hashlib,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'official/code'))
from solver import GraphIndex
from optimizer_v2 import affinity_components,component_batch_plan
from evaluation_validation import read_evaluation_config
from traffic_model import predict_partition_bytes
cfg=read_evaluation_config(str(ROOT/'official/data/config.txt'));jobs=[];rows=[]
for case in ['case_001','case_004','case_006','case_010','case_014']:
 path=ROOT/'official/data'/(case+'.json');g=json.loads(path.read_text());ix=GraphIndex(g)
 for weight in [0.5,2.0]:
  base,bmeta=affinity_components(ix,4,cfg['bandwidth'],weight)
  plan,meta=component_batch_plan(ix,base,512,'residency',cfg['capacity'])
  name=f'affinity{weight:g}_batch512';dest=ROOT/'plans/affinity'/f'{case}_n4_{name}.json';dest.parent.mkdir(parents=True,exist_ok=True)
  text=json.dumps(plan,sort_keys=True);dest.write_text(text)
  rows.append({'case':case,'variant':name,'base':bmeta,'meta':meta,'plan_file':str(dest.relative_to(ROOT)),
               'plan_sha256':hashlib.sha256(text.encode()).hexdigest(),'traffic':predict_partition_bytes(g,plan,'B')})
  for mode in ['B','L2']:
   jobs.append({'graph':str(path),'plan':str(dest),'mode':mode,'variant':name,'cores':4,
                'output':str(ROOT/'results/affinity'/f'{case}_{name}_{mode}.json')})
  print(case,name,flush=True)
(ROOT/'reports/affinity_jobs.json').write_text(json.dumps(jobs,indent=2));(ROOT/'reports/affinity_manifest.json').write_text(json.dumps(rows,indent=2))
