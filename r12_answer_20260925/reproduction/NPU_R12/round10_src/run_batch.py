from pathlib import Path
import argparse,json,sys,time,subprocess,concurrent.futures,os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'round6_src'));from solve_round6 import execute,sha,write_json

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--track',choices=['B5','supplement','ablation'],required=True);ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
 if a.track=='B5':jobs=[(f'case_{i:03}',s,'full') for i in range(1,101) for s in ['B']]
 elif a.track=='supplement':jobs=[(f'case_{i:03}',s,'full') for i in [1,2,5,6,10,14,44,46,80,86] for s in ['A','L2']]
 else:jobs=[(f'case_{i:03}',s,p) for i in [5,6,44,46,80,86] for s in ['B','L2'] for p in ['control','component']]
 out=ROOT/'round10_results'/a.track;out.mkdir(parents=True,exist_ok=True)
 manifest={'track':a.track,'jobs':jobs,'workers':a.workers,'budget':600,'source_sha':sha(ROOT/'round10_src/solve_round10.py'),'started_epoch':time.time(),'evidence':'fresh per job; no history lookup; independently executed ablations; no cross-run cache'}
 write_json(out/'manifest.json',manifest)
 def work(job):
  case,s,p=job;d=out/f'{case}_{s}_{p}';cmd=[sys.executable,'-S',str(ROOT/'round10_src/solve_round10.py'),str(ROOT/'official/data'/f'{case}.json'),'-n','5','--scene',s,'--profile',p,'--budget','600','--out',str(d)]
  record={'id':d.name,'driver':execute(cmd,615,out/(d.name+'.log'))}
  rp=d/'report.json'
  if rp.exists():
   r=json.loads(rp.read_text());record.update(status=r['status'],makespan=r.get('selected',{}).get('makespan'),control=r.get('control',{}).get('makespan'),wall_seconds=r.get('wall_seconds'),report=str(rp.relative_to(ROOT)))
  else:record['status']='missing_report'
  print(json.dumps(record,ensure_ascii=False),flush=True);return record
 records=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
  futures=[ex.submit(work,j) for j in jobs]
  for f in concurrent.futures.as_completed(futures):records.append(f.result());write_json(out/'summary.json',{'declared':len(jobs),'records':records,'complete':len(records)==len(jobs)})
if __name__=='__main__':main()
