"""Generate and structurally validate plans for all requested cases/cores.

The grid is NOT a completed performance experiment. A manifest records every
candidate; formal execution is a separate evaluation stage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--official',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--cases',nargs='*')
    ap.add_argument('--cores',type=int,nargs='+',default=[2,3,4,5])
    ap.add_argument('--variants',nargs='+',choices=['components','chainwave'],default=['components','chainwave'])
    args=ap.parse_args();official=args.official.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(official/'code'))
    from contest_io import _read_json
    from solver import GraphIndex,make_plan
    graphs=sorted((official/'data').glob('case_*.json'))
    if args.cases:
        requested=set(args.cases)
        if requested-{p.stem for p in graphs}:ap.error('Unknown requested case')
        graphs=[p for p in graphs if p.stem in requested]
    rows=[];st=time.perf_counter()
    for path in graphs:
        start=time.perf_counter();g=_read_json(str(path));idx=GraphIndex(g)
        pre=time.perf_counter()-start;gh=hashlib.sha256(path.read_bytes()).hexdigest()
        for cores in args.cores:
            for variant in args.variants:
                for scene in (['A','B'] if variant=='chainwave' else ['A']):
                    t=time.perf_counter()
                    dest=out/path.stem/f'n{cores}_{variant}_{scene}.json'
                    meta={'case':path.stem,'cores':cores,'variant':variant,'scene':scene,
                          'preprocessing_seconds':pre,'graph_sha256':gh}
                    try:
                        plan,info=make_plan(g,cores,variant,scene,official,index=idx)
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        dest.write_text(json.dumps(plan,sort_keys=True),encoding='utf-8')
                        meta.update(info,status='structural_ok',plan_file=str(dest.relative_to(out)),
                                    plan_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
                    except Exception as exc:
                        meta.update(status='construction_error',error=f'{type(exc).__name__}: {exc}')
                    meta['construction_and_validation_seconds']=time.perf_counter()-t
                    dest.with_suffix('.meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
                    rows.append(meta)
        print(path.stem,len(rows),round(time.perf_counter()-start,3),flush=True)
        (out/'manifest.json').write_text(json.dumps({'cases_processed':sum(r['cores']==args.cores[0] and r['variant']==args.variants[0] and r['scene']=='A' for r in rows),
            'elapsed_seconds':time.perf_counter()-st,'rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if all(r['status']=='structural_ok' for r in rows) else 2


if __name__=='__main__':
    raise SystemExit(main())
