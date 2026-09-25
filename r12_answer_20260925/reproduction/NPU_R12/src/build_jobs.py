"""Create portable evaluation manifests from an existing generated plan grid."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--official',type=Path,required=True)
    ap.add_argument('--plans',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--cases',nargs='*')
    ap.add_argument('--cores',type=int,nargs='+',default=[2,3,4,5])
    args=ap.parse_args();off=args.official.resolve();plans=args.plans.resolve();res=args.results.resolve();out=args.output.resolve()
    cases=sorted(p.stem for p in (off/'data').glob('case_*.json'))
    if args.cases:
        if set(args.cases)-set(cases):ap.error('Unknown cases')
        cases=[c for c in cases if c in args.cases]
    jobs=[]
    for c in cases:
        for n in args.cores:
            for v in ['components','chainwave']:
                for mode in ['A','B','L2']:
                    scene='A' if v=='components' or mode=='A' else 'B'
                    plan=plans/c/f'n{n}_{v}_{scene}.json'
                    if not plan.exists():raise FileNotFoundError(plan)
                    jobs.append({'graph':os.path.relpath(off/'data'/f'{c}.json',out.parent),
                                 'plan':os.path.relpath(plan,out.parent),'mode':mode,'variant':v,'cores':n,
                                 'output':os.path.relpath(res/f'{c}_n{n}_{v}_{mode}.json',out.parent)})
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(jobs,indent=2),encoding='utf-8')
    print('Wrote',len(jobs),'jobs to',out)
    return 0


if __name__=='__main__':raise SystemExit(main())
