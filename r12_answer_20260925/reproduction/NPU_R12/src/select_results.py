"""Select only evaluated feasible candidates; keep same-plan L2 comparisons.

Never replace missing cases by 1x, never average a partial suite as full-suite
performance, and never confuse timeout with proven infeasibility.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import shutil
import statistics


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--screen',type=Path,required=True)
    ap.add_argument('--plans',type=Path,required=True)
    ap.add_argument('--baselines',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    raw=json.loads((args.screen/'summary.json').read_text(encoding='utf-8'))['rows']
    bykey={(r['case'],r['requested_cores'],r['variant'],r['mode']):r for r in raw}
    groups=defaultdict(list)
    for r in raw:
        if r['status']=='ok':groups[(r['case'],r['requested_cores'],r['mode'])].append(r)
    rows=[]
    for case,n,mode in sorted(k for k in groups if k[2] in ('A','B')):
        candidates=groups[(case,n,mode)]
        best=min(candidates,key=lambda r:(r['makespan'],r['data_movement_bytes']['added_copy_bytes'],r['variant']))
        row={'case':case,'cores':n,'scene':mode,'selected_variant':best['variant'],
             'makespan':best['makespan'],'added_copy_bytes':best['data_movement_bytes']['added_copy_bytes'],
             'partition_added_copy_bytes':best['data_movement_bytes'].get('partition_added_copy_bytes'),
             'spill_added_copy_bytes':best['data_movement_bytes'].get('spill_added_copy_bytes'),
             'plan_sha256':best['plan_sha256'],'source_result':os.path.relpath((args.screen/f"{case}_n{n}_{best['variant']}_{mode}.json").resolve(), args.out.resolve())}
        p=args.baselines/(case+'.json')
        if p.exists():
            base=json.loads(p.read_text(encoding='utf-8'))
            if base['status']=='ok' and base['graph_sha256']==best['graph_sha256'] and base['config_sha256']==best['config_sha256']:
                row['singlecore_makespan']=base['makespan']
                row['speedup']=base['makespan']/best['makespan']
        if mode=='B':
            cache=bykey.get((case,n,best['variant'],'L2'))
            if cache and cache['status']=='ok' and cache['plan_sha256']==best['plan_sha256']:
                row['same_plan_L2_makespan']=cache['makespan']
                row['same_plan_L2_relative_speedup']=best['makespan']/cache['makespan']
                row['cache_stats']=cache.get('cache_stats')
        scene='A' if best['variant']=='components' or mode=='A' else 'B'
        plan=args.plans/case/f"n{n}_{best['variant']}_{scene}.json"
        if not plan.exists():raise FileNotFoundError(plan)
        from hashlib import sha256
        if sha256(plan.read_bytes()).hexdigest()!=best['plan_sha256']:raise ValueError('Selected plan hash mismatch')
        dest=args.out/'selected_plans'/mode/f'n{n}'/f'{case}_multicore_res.json'
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(plan,dest)
        row['selected_plan_file']=str(dest.relative_to(args.out));rows.append(row)
    means=[]
    for mode in ['A','B']:
        for n in [2,3,4,5]:
            sub=[r for r in rows if r['scene']==mode and r['cores']==n and 'speedup' in r]
            means.append({'scene':mode,'cores':n,'valid_case_count':len(sub),
                          'mean_speedup_of_available_cases':statistics.mean(r['speedup'] for r in sub) if sub else None,
                          'full_100_case_mean_valid':len(sub)==100})
    res={'selection':'lexicographic (official Makespan, official added COPY bytes, variant name)',
         'L2_comparison':'same plan as selected no-L2 B baseline, not a Cache-specialized optimization',
         'rows':rows,'means':means}
    (args.out/'selected_summary.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Selected',len(rows),'evaluated scene/core/case plans')
    return 0


if __name__=='__main__':raise SystemExit(main())
