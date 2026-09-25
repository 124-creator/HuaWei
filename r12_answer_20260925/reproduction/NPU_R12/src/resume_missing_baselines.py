"""Resume only missing fixed baselines from explicit inherited coverage evidence.
Never substitutes a B/L2 singlecore result for the official singlecore entry.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from run_experiments import run_job,source_hash,sha

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--workers',type=int,default=3);p.add_argument('--timeout',type=float,default=3600);p.add_argument('--dry-run',action='store_true');a=p.parse_args();root=a.root.resolve();official=root/'official'
 prev=root/'stage3_reports/baseline_coverage_stage3.json'
 if not prev.exists():prev=root/'reports/baseline_coverage_stage2.json'
 data=json.loads(prev.read_text());missing=data['missing'];out=root/'stage3_results/baseline_resume';out.mkdir(parents=True,exist_ok=True)
 jobs=[{'graph':str(official/'data'/f'{case}.json'),'mode':'single','output':str(out/f'{case}.json')} for case in missing]
 print(json.dumps({'requested':len(jobs),'cases':missing,'timeout':a.timeout,'workers':a.workers,'note':'Coverage inherited from referenced evidence, not recalculated or imputed.'},ensure_ascii=False))
 if a.dry_run:return 0
 rows=[];code=source_hash(official)
 with ThreadPoolExecutor(max_workers=a.workers)as pool:
  fs=[pool.submit(run_job,j,official,a.timeout,True,code,False)for j in jobs]
  for f in as_completed(fs):
   rows.append(f.result());(out/'summary.json').write_text(json.dumps({'jobs_requested':len(jobs),'jobs_finished':len(rows),'rows':rows},indent=2))
 return 0 if all(x['status']=='ok'for x in rows)else 2
if __name__=='__main__':raise SystemExit(main())
