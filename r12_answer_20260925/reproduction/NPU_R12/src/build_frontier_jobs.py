from pathlib import Path
import json,sys,time,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'official/code'))
from solver import GraphIndex,make_plan
from optimizer_v2 import frontier_plan
from evaluation_validation import read_evaluation_config
from traffic_model import predict_partition_bytes
cap=read_evaluation_config(str(ROOT/'official/data/config.txt'))['capacity']
rows=[];jobs=[]
for case in ['case_002','case_005','case_006','case_010','case_016','case_085']:
 path=ROOT/'official/data'/(case+'.json');g=json.loads(path.read_text());ix=GraphIndex(g)
 base,_=make_plan(g,4,'chainwave','B',ROOT/'official',ix);t=time.perf_counter()
 plan,meta=frontier_plan(ix,base,cap);text=json.dumps(plan,sort_keys=True)
 out=ROOT/'plans/frontier'/(case+'_n4_chainfrontier.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(text)
 assert predict_partition_bytes(g,base,'B')==predict_partition_bytes(g,plan,'B')
 rows.append({'case':case,'meta':meta,'seconds':time.perf_counter()-t,'plan_sha256':hashlib.sha256(text.encode()).hexdigest()})
 for mode in ['B','L2']:
  jobs.append({'graph':str(path),'plan':str(out),'mode':mode,'variant':'chainfrontier','cores':4,
               'output':str(ROOT/'results/frontier'/(case+'_'+mode+'.json'))})
 print(case,meta['subgraphs'],round(time.perf_counter()-t,3),flush=True)
(ROOT/'reports/frontier_jobs.json').write_text(json.dumps(jobs,indent=2));(ROOT/'reports/frontier_manifest.json').write_text(json.dumps(rows,indent=2))
