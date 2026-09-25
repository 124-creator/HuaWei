"""Small controlled cache-timing experiment from actual FIFO read events.

Never adds waits or operations. Split an existing subgraph at chain-block
boundaries to move a same-tensor early reader forward or a concurrent reader back.
Only legal quotient/task orders survive. Not part of frozen coverage protocol.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,sys
from copy import deepcopy
from pathlib import Path
from solver import GraphIndex
from optimizer_v2 import check_plan
from traffic_model import predict_partition_bytes


def split_input_group(index,base,tid,core,direction):
    blocks,block_of,_,_=index.chain_blocks();plan=deepcopy(base);order=plan['core_schedules'][core]
    consumers=[u for u in index.consumers.get(tid,set()) if base['node_to_subgraph'][str(u)] in set(order)]
    if not consumers:return None
    sg=min((base['node_to_subgraph'][str(u)] for u in consumers),key=order.index)
    blockset={block_of[u] for u in consumers if base['node_to_subgraph'][str(u)]==sg}
    members={int(u) for u,s in base['node_to_subgraph'].items() if s==sg}
    target={u for b in blockset for u in blocks[b]}
    if not target<=members:return None
    other=members-target
    if not target or not other:return None
    first,second=(target,other) if direction=='early' else (other,target)
    new=max(base['node_to_subgraph'].values(),default=-1)+1
    for u in first:plan['node_to_subgraph'][str(u)]=sg
    for u in second:plan['node_to_subgraph'][str(u)]=new
    at=order.index(sg);order[at:at+1]=[sg,new]
    try:check_plan(index,plan)
    except (ValueError,RuntimeError):return None
    return plan


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--limit',type=int,default=6)
    a=ap.parse_args();root=a.root.resolve();official=root/'official';sys.path.insert(0,str(official/'code'))
    from run_experiments import run_job,source_hash
    rows=[]
    for case in ['case_005','case_006','case_010']:
        g=json.loads((official/'data'/f'{case}.json').read_text());ix=GraphIndex(g)
        base=json.loads((root/'selected_plans'/f'{case}_n4_L2.json').read_text());diag=json.loads((root/'stage3_results/trace'/f'{case}_L2best.json').read_text())
        out=root/'stage3_results/cache_timing'/case;out.mkdir(parents=True,exist_ok=True)
        overlaps=sorted(diag['fifo']['inflight_overlap_requests'],key=lambda x:(-x['size_bytes'],-x['overlap_window_cycles'],x['time'],x['op_id']))
        seen={json.dumps(base,sort_keys=True)};candidates=[]
        for ev in overlaps:
            t=ev['tensor_id'];dst=ev['core_id'];src=ev['previous_core']
            options=[]
            late=split_input_group(ix,base,t,dst,'late')
            early=split_input_group(ix,base,t,src,'early')
            if late:options.append(('defer_concurrent_reader',late))
            if early:options.append(('advance_first_reader',early))
            if early:
                both=split_input_group(ix,early,t,dst,'late')
                if both:options.append(('both',both))
            for kind,p in options:
                key=json.dumps(p,sort_keys=True)
                if key in seen:continue
                seen.add(key);candidates.append((p,{'trigger':ev,'action':kind}))
                assert predict_partition_bytes(g,p,'B')==predict_partition_bytes(g,base,'B'),'fixed-core B traffic changed'
                if len(candidates)>=a.limit:break
            if len(candidates)>=a.limit:break
        measured=[]
        for i,(p,why) in enumerate(candidates):
            path=out/f'timing_{i:02d}_plan.json';path.write_text(json.dumps(p,sort_keys=True))
            r=run_job({'graph':str(official/'data'/f'{case}.json'),'plan':str(path),'mode':'L2','cores':4,'variant':f'cache_timing_{i:02d}','output':str(out/f'timing_{i:02d}_L2.json')},official,40,True,source_hash(official),False)
            measured.append({'index':i,'plan':str(path.relative_to(root)),'why':why,'status':r['status'],'makespan':r.get('makespan'),'cache_stats':r.get('cache_stats')})
        summary={'case':case,'base_makespan':diag['makespan'],'base_evictions':diag['fifo']['eviction_count'],'candidates':measured,'scope':'fixed-core B traffic; actual cold-read timing candidates, not a general FIFO capacity optimizer'}
        good=[r for r in measured if r['status']=='ok'];summary['best_candidate']=min(good,key=lambda r:r['makespan']) if good else None
        (out/'summary.json').write_text(json.dumps(summary,indent=2));rows.append(summary)
    (root/'stage3_reports/cache_timing_summary.json').write_text(json.dumps(rows,indent=2))
if __name__=='__main__':main()
