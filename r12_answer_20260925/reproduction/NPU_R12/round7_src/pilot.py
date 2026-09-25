from task_frontier import *
from run_experiments import run_job,source_hash
import argparse,time,json

def main():
 ap=argparse.ArgumentParser();ap.add_argument('case');a=ap.parse_args();out=ROOT/'round7_results/pilot'/a.case;out.mkdir(parents=True,exist_ok=True)
 graph=ROOT/'official/data'/f'{a.case}.json';ix=GraphIndex(json.loads(graph.read_text()));start=time.perf_counter();rows=candidates(ix,5);manifest=[]
 for name,plan,meta in rows:
  pp=out/(name+'_plan.json');pp.write_text(json.dumps(plan,sort_keys=True));(out/(name+'_features.json')).write_text(json.dumps(meta,indent=2))
  r=run_job(dict(graph=str(graph),plan=str(pp),mode='A',cores=5,variant=name,output=str(out/(name+'_result.json'))),ROOT/'official',40,False,source_hash(ROOT/'official'),False)
  manifest.append(dict(name=name,meta=meta,status=r['status'],makespan=r.get('makespan')))
 (out/'summary.json').write_text(json.dumps(dict(case=a.case,wall=time.perf_counter()-start,rows=manifest),indent=2))
if __name__=='__main__':main()
