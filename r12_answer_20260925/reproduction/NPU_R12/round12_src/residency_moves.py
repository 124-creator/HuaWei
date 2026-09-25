"""One-round, bounded local moves guided by actual official Spill records.
Preserves every operation's subgraph and core. Does not replace private cache
policy or claim static lifetimes are exact. Each resulting plan requires official
full evaluation because queue/resource behavior may worsen or deadlock.
"""
from __future__ import annotations
import sys,time,json,copy,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for d in ('official/code','src','round6_src','round7_src','round10_src','round11_src','round12_src'):
    sys.path.insert(0,str(ROOT/d))
from solver import GraphIndex
from optimizer_v2 import check_plan
from runtime import sha,write_json

def capture_spills(graph,plan):
    # Observe the returned values of the UNCHANGED official step2 call.
    # The temporary observer returns the original object verbatim. No scheduling
    # semantics or source files are altered. Final scoring runs in fresh processes.
    import multicore_cut_evaluate_problem_2 as model
    from evaluation_validation import read_evaluation_config
    config=read_evaluation_config(str(ROOT/'official/data/config.txt'))
    original=model.step2_spill_insertion;captured=[]
    def observe(g,seq,**kw):
        result=original(g,seq,**kw)
        captured.append({'first_original_ops':[o['id'] for o in g['ops'][:1]],'ops':{o['id']:o for o in g['ops']},'records':result.get('spill_records',[])})
        return result
    try:
        model.step2_spill_insertion=observe
        tasks,links,_,traffic,_=model._build_scene_b_tasks(graph,plan,config['bandwidth'],config['capacity'])
    finally:model.step2_spill_insertion=original
    # Calls are in increasing nonempty core order, per official task construction.
    active=[k for k,s in enumerate(plan['core_schedules']) if s]
    if len(active)!=len(captured):raise AssertionError('Diagnostic core alignment failed')
    return tasks,{k:r['records'] for k,r in zip(active,captured)},traffic

def moves(ix,base,raw,limit=4,max_scan=32,max_shift=32):
    if raw['scene'] not in ('B','B_L2','B_WITH_L2','B+L2','L2') and 'cache_stats' not in raw:
        raise ValueError('This diagnostic applies to core-merged B/L2 only')
    tic=time.perf_counter();tasks,records,traffic=capture_spills(ix.graph,base)
    for field in ('partition_added_copy_bytes','spill_added_copy_bytes','scheduled_copy_bytes'):
        if traffic[field]!=raw['data_movement_bytes'][field]:raise AssertionError('Captured official Spill differs from scored plan')
    timeline={(c['core_id'],o['op_id']):o for c in raw['per_core_timeline'] for o in c['ops']}
    positions={s:i for seq in base['core_schedules'] for i,s in enumerate(seq)}
    pool=[]
    for k,rr in records.items():
        sg=tasks[k]['op_subgraph']
        for r in rr:
            a,b=sg.get(r['prev_use_op']),sg.get(r['next_use_op'])
            if a is None or b is None or a==b:continue
            ia,ib=positions[a],positions[b]
            if ib<=ia+1:continue
            observed=timeline.get((k,r['spill_in_id']),{})
            duration=observed.get('duration',0)
            # Ranking only: avoid claiming that this cost is an additive saving.
            score=(r['size']*(1+int(r['spill_out_copies_data'])))*min(128,ib-ia)
            pool.append((score,duration,k,a,b,r))
    pool.sort(key=lambda x:(-x[0],-x[1],x[2],x[5]['logical_tid'],x[4]))
    proposals=[];seen=set();rejected=[]
    baseline_map=base['node_to_subgraph']
    for score,dur,k,a,b,r in pool[:max_scan]:
        seq=base['core_schedules'][k];ia,ib=positions[a],positions[b]
        for direction in ('consumer_earlier','producer_later'):
            p=copy.deepcopy(base);q=p['core_schedules'][k]
            if direction=='consumer_earlier':
                newpos=max(ia+1,ib-max_shift);moved=q.pop(ib);q.insert(newpos,moved)
            else:
                newpos=min(ib-1,ia+max_shift);moved=q.pop(ia);q.insert(newpos,moved)
            signature=(k,tuple(q))
            if signature in seen:continue
            seen.add(signature)
            meta={'direction':direction,'core':k,'tensor':r['logical_tid'],'size':r['size'],'prev_group':a,'next_group':b,'shifted_group':moved,'ranking_score':score,'observed_reload_duration':dur,
                  'scope':'same subgraph membership and core; local queue only; actual benefit unknown'}
            try:check_plan(ix,p)
            except (ValueError,RuntimeError,AssertionError) as e:
                rejected.append({**meta,'status':'structural_rejection','error':str(e)[:200]});continue
            if p['node_to_subgraph']!=baseline_map:raise AssertionError('Membership changed')
            proposals.append((p,meta))
            if len(proposals)>=limit:break
        if len(proposals)>=limit:break
    diagnostic={'captured_spill_events':sum(map(len,records.values())),'captured_traffic':traffic,'eligible_event_count':len(pool),'scanned_event_cap':max_scan,'max_local_shift':max_shift,'proposals':len(proposals),'rejections':rejected,'seconds':time.perf_counter()-tic,
                'warning':'Observed Spill-guided queue interventions; not an exact peak predictor or causal estimate.'}
    return proposals,diagnostic

def main():
 ap=argparse.ArgumentParser();ap.add_argument('graph',type=Path);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--raw',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--limit',type=int,default=4);a=ap.parse_args()
 ix=GraphIndex(json.loads(a.graph.read_text()));base=json.loads(a.plan.read_text());raw=json.loads(a.raw.read_text())
 ps,diag=moves(ix,base,raw,a.limit);a.out.mkdir(parents=True,exist_ok=True)
 manifest=[]
 for i,(p,m) in enumerate(ps):
  name=f'local_{i:02d}';write_json(a.out/(name+'.plan.json'),p);manifest.append({'name':name,'plan':name+'.plan.json','sha256':sha(a.out/(name+'.plan.json')),'meta':m})
 write_json(a.out/'proposals.json',{'candidates':manifest,'diagnostic':diag})
if __name__=='__main__':main()
