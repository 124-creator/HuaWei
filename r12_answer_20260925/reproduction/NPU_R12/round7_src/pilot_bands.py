from task_frontier import *
from run_experiments import run_job,source_hash
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,time,json

def run(c):
 out=ROOT/'round7_results/pilot_bands'/c;out.mkdir(parents=True,exist_ok=True)
 graph=ROOT/'official/data'/f'{c}.json';ix=GraphIndex(json.loads(graph.read_text()));manifest=[];start=__import__('time').perf_counter()
 choices=[('bands4',lambda:band_components(ix,4)),('bands16',lambda:band_components(ix,16)),('bands64',lambda:band_components(ix,64)),('cones025',lambda:closed_cones(ix,5,.25)),('cones0125',lambda:closed_cones(ix,5,.125))]
 for name,fn in choices:
  groups,meta=fn();plan,mm=list_assign(ix,groups,5);bound=task_lower_bound(ix,plan);meta.update(mm);meta['bound']=bound
  pp=out/(name+'_plan.json');pp.write_text(json.dumps(plan,sort_keys=True));(out/(name+'_features.json')).write_text(json.dumps(meta,indent=2))
  r=run_job(dict(graph=str(graph),plan=str(pp),mode='A',cores=5,variant=name,output=str(out/(name+'_result.json'))),ROOT/'official',30,False,source_hash(ROOT/'official'),False)
  manifest.append(dict(name=name,meta=meta,status=r['status'],makespan=r.get('makespan')))
 (out/'summary.json').write_text(json.dumps(dict(case=c,wall=__import__('time').perf_counter()-start,rows=manifest),indent=2))
 return c
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=3) as pool:
  for f in as_completed([pool.submit(run,c) for c in ['case_002','case_005','case_006','case_010','case_044','case_046','case_086']]):print('DONE',f.result(),flush=True)
