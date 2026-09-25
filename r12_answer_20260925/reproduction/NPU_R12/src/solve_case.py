"""End-to-end bounded two-candidate solver. Outputs only evaluated feasible plans.

The overall budget is a soft wall-time budget (generation/I/O may overrun it).
Every evaluator runs in a separate process with a strict per-call timeout.
L2 mode evaluates the same two structural constructions under L2; it is not a
specialized cache-working-set optimizer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('graph',type=Path)
    ap.add_argument('--official',type=Path,required=True)
    ap.add_argument('-n','--cores',type=int,required=True)
    ap.add_argument('--scene',choices=['A','B','L2'],required=True)
    ap.add_argument('--budget',type=float,default=600)
    ap.add_argument('--per-eval-timeout',type=float,default=120)
    ap.add_argument('-o','--output',type=Path,required=True)
    ap.add_argument('--workdir',type=Path)
    args=ap.parse_args()
    if args.budget<=0 or args.per_eval_timeout<=0:ap.error('Positive budget/timeouts required')
    if args.cores<1:ap.error('Positive core count required')
    official=args.official.resolve();sys.path.insert(0,str(official/'code'))
    from contest_io import _read_json
    from solver import GraphIndex,make_plan
    from run_experiments import run_job,source_hash
    start=time.perf_counter();graph=args.graph.resolve();g=_read_json(str(graph));index=GraphIndex(g)
    output=args.output.resolve()
    work=args.workdir.resolve() if args.workdir else output.parent/(output.stem+'_work')
    work.mkdir(parents=True,exist_ok=True)
    # Avoid returning an old successful plan as if this invocation had produced it.
    if output.exists():ap.error('Output already exists; choose a new path or explicitly remove the old output.')
    candidates=[];fingerprints=set();construction=[]
    for variant in ['components','chainwave']:
        p,meta=make_plan(g,args.cores,variant,args.scene,official,index=index)
        text=json.dumps(p,sort_keys=True);fp=hashlib.sha256(text.encode()).hexdigest()
        construction.append(meta)
        if fp in fingerprints:continue
        fingerprints.add(fp);dest=work/(variant+'_plan.json');dest.write_text(text,encoding='utf-8')
        candidates.append((variant,dest))
    results=[];ch=source_hash(official)
    for j,(variant,path) in enumerate(candidates):
        remain=args.budget-(time.perf_counter()-start)
        if remain<=0:break
        # Reserve a share for each remaining candidate instead of spending all
        # time on the first construction.
        timeout=min(args.per_eval_timeout,max(.1,remain/(len(candidates)-j)))
        result=run_job({'graph':str(graph),'plan':str(path),'mode':args.scene,
                        'variant':variant,'cores':args.cores,'output':str(work/(variant+'_result.json'))},
                       official,timeout,False,ch,False)
        results.append(result)
    good=[r for r in results if r['status']=='ok']
    report={'algorithm':'v0.1 two structural candidates, official selection',
            'scene':args.scene,'cores':args.cores,'budget_seconds':args.budget,
            'wall_seconds':time.perf_counter()-start,'constructions':construction,'evaluations':results,
            'status':'no_evaluated_feasible_plan' if not good else 'ok'}
    if good:
        best=min(good,key=lambda r:(r['makespan'],r['data_movement_bytes']['added_copy_bytes'],r['variant']))
        src=work/(best['variant']+'_plan.json');output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,output)
        report.update(selected_variant=best['variant'],makespan=best['makespan'],
                      added_copy_bytes=best['data_movement_bytes']['added_copy_bytes'],
                      plan_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    report['wall_seconds']=time.perf_counter()-start
    output.with_suffix('.selection.json').parent.mkdir(parents=True,exist_ok=True)
    output.with_suffix('.selection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('evaluations','constructions')},ensure_ascii=False,indent=2))
    return 0 if good else 2


if __name__=='__main__':raise SystemExit(main())
