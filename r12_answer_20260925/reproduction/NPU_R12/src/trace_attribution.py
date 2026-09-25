"""Post-hoc B/L2 trace attribution, using unmodified official task preparation.

Explains fixed traces, not a counterfactual speedup model. The observed duration of
COPY includes shared-bandwidth contention and integer rounding. Memory-reuse
edges are artificial capacity-credit ordering edges, not necessarily a Spill.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, math, sys
from pathlib import Path


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def serial(obj):
    if isinstance(obj,set):return sorted(obj)
    raise TypeError(type(obj).__name__)


def fifo_audit(result):
    """Replay every official cache event in recorded order; hits never refresh FIFO."""
    cap=result.get('cache_capacity_bytes',0);entries=collections.OrderedDict();ever=set();evicted=set();inflight=collections.defaultdict(list)
    ops={(c['core_id'],o['op_id']):o for c in result['per_core_timeline'] for o in c['ops']}
    counts=collections.Counter();sizes=collections.Counter();overlap=[];evictions=[];checks=[]
    for ev in result.get('cache_events',[]):
        kind=ev['event'];tid=ev['tensor_id'];now=ev['time'];size=ev['size_bytes'];item=(ev['core_id'],ev['op_id'])
        if kind=='insert':
            assert tid not in entries and size<=cap
            expected=[]
            while entries and sum(entries.values())+size>cap:
                old,_=entries.popitem(last=False);expected.append(old);evicted.add(old)
            assert expected==ev['evicted_tensor_ids']
            entries[tid]=size;ever.add(tid)
            assert sum(entries.values())==ev['used_bytes']<=cap
            evictions.extend({'time':now,'tensor_id':t} for t in expected)
            continue
        assert kind in ('hit','miss')
        assert (tid in entries)==(kind=='hit'),(kind,tid,now)
        if kind=='hit':label='hit'
        elif size>cap:label='uncacheable_oversize'
        else:
            active=[x for x in inflight[tid] if x['end']>now]
            if active:
                label='miss_while_same_tensor_inflight'
                overlap.append({'time':now,'core_id':item[0],'op_id':item[1],'tensor_id':tid,'size_bytes':size,
                    'prior_read_completes':min(x['end'] for x in active),'overlap_window_cycles':min(x['end'] for x in active)-now,
                    'previous_core':min(active,key=lambda x:x['end'])['core']})
            elif tid in ever:label='miss_after_eviction'
            else:label='cold_miss_without_inflight'
        counts[label]+=1;sizes[label]+=size
        if kind=='miss':inflight[tid].append({'end':ops[item]['end'],'core':item[0],'op_id':item[1]})
    st=result.get('cache_stats')
    if st:
        assert sizes['hit']==st['hit_bytes'];assert sum(v for k,v in sizes.items() if k!='hit')==st['miss_bytes']
        assert counts['hit']==st['copy_in_hits']
    return {'event_replay_checks_passed':True,'requests':dict(counts),'bytes':dict(sizes),'eviction_count':len(evictions),
        'inflight_overlap_requests':overlap,'evictions':evictions,
        'interpretation':'Overlap misses are observed missed reuse opportunities, not guaranteed reducible makespan. Same-time events follow original event list order.'}


def attribute(tasks,links,result):
    from schedule_step3 import _build_graph_views,_op_duration,_uses_ddr_bandwidth
    ops={(c['core_id'],o['op_id']):o for c in result['per_core_timeline'] for o in c['ops']}
    preds={};rows=[];pipe_stats=[];residual=[];opwait=collections.Counter();memory_lives=[];all_cons={}
    incoming=collections.defaultdict(list)
    for link in links:incoming[(link['target_core'],link['target_copy_in_id'])].append((link['source_core'],link['source_copy_out_id']))
    delay=result['cross_core_copy_delay_cycles'];bw=result['bandwidth_bytes_per_cycle'];T=result['makespan']
    for core,task in tasks.items():
        graph=task['graph'];normal_edges=[e for e in graph['edges'] if e.get('dependency')!='MEMORY_REUSE']
        _,_,normal_preds,_=_build_graph_views(graph['ops'],normal_edges)
        pipe_prev={}
        for pipe,seq in task['pipe_ops'].items():
            last=None;idle_sets=collections.Counter();busy=0;startup=0
            for op in seq:
                item=(core,op);o=ops[item];pipe_prev[op]=last
                edges=[];ready_times={'data':0,'memory_reuse':0,'cross_release':0,'pipe':ops[(core,last)]['end'] if last is not None else 0}
                for p in task['op_preds'][op]:
                    category='data' if p in normal_preds[op] else 'memory_reuse'
                    edges.append(((core,p),0,category));ready_times[category]=max(ready_times[category],ops[(core,p)]['end'])
                for p in incoming[item]:
                    edges.append((p,delay,'cross_release'));ready_times['cross_release']=max(ready_times['cross_release'],ops[p]['end']+delay)
                if last is not None:edges.append(((core,last),0,'pipe'))
                preds[item]=edges;start_bound=max(ready_times.values());lag=o['start']-start_bound
                if lag:residual.append({'core':core,'op_id':op,'start':o['start'],'bound':start_bound,'residual':lag})
                assert lag>=0,(item,o,start_bound)
                ptime=ready_times['pipe'];bpoints=sorted({ptime,o['start']}|{t for k,t in ready_times.items() if k!='pipe' and ptime<t<o['start']})
                for a,b in zip(bpoints,bpoints[1:]):
                    labels=tuple(k for k,t in ready_times.items() if k!='pipe' and t>a)
                    idle_sets['+'.join(labels) if labels else 'unexplained']+=b-a
                intrinsic=max(ready_times[k] for k in ('data','memory_reuse','cross_release'))
                queue=max(0,ptime-intrinsic);opwait['pipe_queue_cycles_sum']+=queue
                opwait['release_to_start_cycles_sum']+=max(0,o['start']-ready_times['cross_release']) if incoming[item] else 0
                binds=sorted({cat for p,lag0,cat in edges if ops[p]['end']+lag0==o['start']})
                duration=o['end']-o['start'];assert o['duration']==duration
                rows.append({'core_id':core,'op_id':op,'op':o['op'],'pipe':pipe,'start':o['start'],'end':o['end'],
                    'gates':ready_times,'binding_gates':binds,'unexplained_start_lag':lag,'pipe_queue_after_other_ready':queue})
                busy+=duration;last=op
            tail=T-ops[(core,last)]['end'] if last is not None else T
            assert busy+sum(idle_sets.values())+tail==T
            pipe_stats.append({'core_id':core,'pipe':pipe,'busy_cycles':busy,'busy_fraction_of_makespan':busy/T if T else 0,
                'idle_before_operations_by_simultaneous_gate_set':dict(idle_sets),'terminal_idle':tail})
        # Reconstruct the lifetimes of renamed on-chip tensors from global times.
        producers=collections.defaultdict(list);consumers=collections.defaultdict(list)
        for op,ts in task['out_tids'].items():
            for tid in ts:producers[tid].append(op)
        for op,ts in task['in_tids'].items():
            for tid in ts:consumers[tid].append(op)
        tensor_events={'L1':collections.defaultdict(int),'UB':collections.defaultdict(int)}
        local_lives=[]
        for tid,tensor in task['tensor_by_id'].items():
            pos=tensor['pos'];size=tensor['size']
            if pos not in tensor_events or not (producers[tid] or consumers[tid]):continue
            born=min((ops[(core,p)]['start'] for p in producers[tid]),default=0)
            dead=max((ops[(core,c)]['end'] for c in consumers[tid]),default=max((ops[(core,p)]['end'] for p in producers[tid]),default=0))
            assert dead>=born
            tensor_events[pos][born]+=size;tensor_events[pos][dead]-=size
            life={'core_id':core,'tensor_id':tid,'logical_tensor_id':tensor.get('logical_tid',tid),'pos':pos,'size_bytes':size,
                'first_producer_start':born,'last_consumer_end':dead,'byte_cycles':size*(dead-born),
                'last_consumer_ops':[c for c in consumers[tid] if ops[(core,c)]['end']==dead]}
            local_lives.append(life)
        peaks={}
        for pos,events in tensor_events.items():
            used=peak=0
            for t,delta in sorted(events.items()):used+=delta;peak=max(peak,used)
            assert used==0 and peak<=result['capacity_bytes'][pos],(core,pos,used,peak)
            peaks[pos]=peak
        memory_lives.append({'core_id':core,'global_trace_peak_bytes':peaks,
            'top_tensor_byte_cycles':sorted(local_lives,key=lambda x:-x['byte_cycles'])[:30],
            'all_tensor_lifetimes':local_lives})
    # One deterministic critical predecessor chain under observed COPY durations.
    terminal=max(ops,key=lambda u:(ops[u]['end'],-u[0],-u[1]));chain=[];cursor=terminal;duration_totals=collections.Counter();edge_counts=collections.Counter();sync_total=0
    rank={'data':0,'memory_reuse':1,'cross_release':2,'pipe':3}
    while cursor is not None:
        core,op=cursor;task=tasks[core];o=ops[cursor];duration=o['duration'];spec=task['op_by_id'][op]
        transfer=_uses_ddr_bandwidth(spec,task['in_tids'],task['out_tids'],task['tensor_by_id'])
        if transfer:
            path=o.get('memory_path','DDR');rate=result.get('cache_bandwidth_bytes_per_cycle',bw) if path=='CACHE_READ' else bw
            solo=_op_duration(spec,task['in_tids'],task['out_tids'],task['tensor_by_id'],rate)
            duration_totals[path+'_solo_cycles']+=solo;duration_totals[path+'_contention_and_rounding_cycles']+=duration-solo
        else:duration_totals['compute_'+o['pipe']]+=duration
        constraints=preds[cursor]
        if constraints:
            parent,lag,cat=min(constraints,key=lambda e:(-(ops[e[0]]['end']+e[1]),rank[e[2]],e[0]))
            slack=o['start']-ops[parent]['end']-lag;duration_totals['unexplained_start_lag']+=slack
            edge_counts[cat]+=1;sync_total+=lag
        else:parent=None;lag=0;cat='origin';duration_totals['unexplained_start_lag']+=o['start']
        chain.append({'core_id':core,'op_id':op,'op':o['op'],'pipe':o['pipe'],'start':o['start'],'end':o['end'],
            'incoming_gate':cat,'lag':lag,'parent':list(parent) if parent else None})
        cursor=parent
    duration_totals['explicit_cross_release_delay']=sync_total
    assert sum(duration_totals.values())==T,(duration_totals,T)
    assert not residual,('trace start reconstruction has residuals',residual[:3])
    links_detail=[]
    for x in result.get('cross_core_transfers',[]):
        d=dict(x);d['post_release_start_gap']=x['copy_in_start']-x['copy_in_release'];assert d['post_release_start_gap']>=0;links_detail.append(d)
    return {'makespan':T,'operation_count':len(ops),'all_start_times_reconstructed':not residual,'unexplained_start_lags':residual,
        'per_pipe':pipe_stats,'operation_wait_sums_not_wall_percentages':dict(opwait),
        'operations':rows,'cross_links_by_post_release_gap':sorted(links_detail,key=lambda d:-d['post_release_start_gap']),
        'one_observed_critical_chain':list(reversed(chain)),'critical_chain_duration_decomposition':dict(duration_totals),
        'critical_chain_edge_counts':dict(edge_counts),'memory_lifetimes':memory_lives,
        'caveats':['COPY durations are observed under this exact schedule, not independent edge weights for optimization.',
                   'Critical chains can be non-unique; deterministic tie order is data, memory_reuse, cross_release, pipe.',
                   'Per-pipe idle intervals and per-operation waits are not additive percentages of global makespan.',
                   'Memory-reuse gate means capacity-credit WAR/WAW ordering; zero Spill does not imply zero such gates.']}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--official',type=Path,required=True);ap.add_argument('--graph',type=Path,required=True)
    ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--result',type=Path,required=True);ap.add_argument('-o','--output',type=Path,required=True)
    a=ap.parse_args();sys.path.insert(0,str(a.official.resolve()/'code'))
    from multicore_cut_evaluate_problem_2 import _build_scene_b_tasks
    from evaluation_validation import read_evaluation_config,validate_execution
    from contest_io import format_scene_a_trace_json
    g=json.loads(a.graph.read_text());plan=json.loads(a.plan.read_text());r=json.loads(a.result.read_text())
    tasks,links,_,movement,_=_build_scene_b_tasks(g,plan,**read_evaluation_config(str(a.official/'data/config.txt')))
    validate_execution(tasks,links);assert movement==r['data_movement_bytes']
    result=attribute(tasks,links,r)
    if r.get('problem')==3:result['fifo']=fifo_audit(r)
    result['evidence']={k:sha(p) for k,p in [('graph_sha256',a.graph),('plan_sha256',a.plan),('result_sha256',a.result)]}
    result['source_files']={'graph':str(a.graph),'plan':str(a.plan),'result':str(a.result)}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    a.output.with_suffix('.perfetto.json').write_text(format_scene_a_trace_json(a.graph.name,r))
    print(json.dumps({'file':str(a.output),'makespan':result['makespan'],'critical':result['critical_chain_duration_decomposition'],
        'gates':result['critical_chain_edge_counts'],'fifo':result.get('fifo',{}).get('requests')},ensure_ascii=False))
if __name__=='__main__':main()
