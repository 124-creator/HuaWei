"""Spill-triggered, bounded-window operation microbatching for B/L2.
Split only selected original subgraphs, retain the original core assignments,
and stable-toposort a <=128-operation window by reuse of large external inputs.
Never declare the affinity proxy a physical capacity check. Official evaluation
is mandatory. There are two fixed window widths, not per-case parameter fitting.
"""
from __future__ import annotations
from pathlib import Path
import sys,json,copy,time,argparse
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[1]
for d in ('official/code','src','round6_src','round7_src','round10_src','round11_src','round12_src'):sys.path.insert(0,str(ROOT/d))
from solver import GraphIndex
from optimizer_v2 import check_plan
from runtime import write_json,sha
from residency_moves import capture_spills
from traffic_model import predict_partition_bytes

CAP={'L1':524288,'UB':131072}

def affinity_order(ix,ids):
    """Stable Kahn order. Soft primary score reuses last large input per storage."""
    members=set(ids);rank={u:i for i,u in enumerate(ids)}
    if len(members)!=len(ids):raise ValueError('Repeated operation')
    pred={u:ix.pred[u]&members for u in ids};succ={u:ix.succ[u]&members for u in ids}
    anchors={u:{t for t in ix.op_inputs[u] if not ix.producers[t] and ix.tensors[t]['size']>=CAP.get(ix.tensors[t]['pos'],131072)//4} for u in ids}
    remaining={u:len(pred[u]) for u in ids};ready={u for u in ids if not pred[u]};recent={'L1':set(),'UB':set(),'DDR':set()};ordered=[]
    while ready:
        def key(u):
            fresh=sum(ix.tensors[t]['size'] for t in anchors[u] if t not in recent[ix.tensors[t]['pos']])
            return fresh,rank[u],u
        u=min(ready,key=key);ready.remove(u);ordered.append(u)
        for pos in recent:
            used={t for t in anchors[u] if ix.tensors[t]['pos']==pos}
            if used:recent[pos]=used
        for v in succ[u]:
            remaining[v]-=1
            if remaining[v]==0:ready.add(v)
    if len(ordered)!=len(ids):raise ValueError('Window DAG cycle')
    return ordered

def candidates(ix,base,raw,limit_windows=16,max_ops=128):
    start=time.perf_counter();view=check_plan(ix,base)
    if raw['data_movement_bytes']['spill_added_copy_bytes']<=0:
        return [],{'status':'no_observed_spill','windows':[]}
    tasks,spills,traffic=capture_spills(ix.graph,base)
    if traffic!=raw['data_movement_bytes']:raise AssertionError('Unchanged diagnostic differs from scored result')
    groupops=defaultdict(list)
    for u in ix.topo:groupops[base['node_to_subgraph'][str(u)]].append(u)
    events={};detail={}
    for k,rs in spills.items():
        seq=base['core_schedules'][k];pos={s:i for i,s in enumerate(seq)};priority=Counter();ds={}
        for r in rs:
            if r['size']<CAP.get(r['pos'],131072)//4:continue
            a=tasks[k]['op_subgraph'].get(r['prev_use_op']);b=tasks[k]['op_subgraph'].get(r['next_use_op'])
            if a not in pos or b not in pos:continue
            # Focus on oscillating, nearby large-input usage, not far arbitrary jumps.
            i,j=pos[a],pos[b]
            if not(0<=j-i<=8):continue
            priority[i]+=r['size']*(1+int(r['spill_out_copies_data']));ds[i]=r
        events[k]=sorted(priority,key=lambda i:(-priority[i],i));detail[k]=ds
    rows=[];rejections=[]
    for width in (4,8):
        p=copy.deepcopy(base);edits={k:[] for k in events};used={k:set() for k in events};windows=[]
        cursors={k:0 for k in events};total=0;more=True
        while more and total<limit_windows:
            more=False
            for k in sorted(events):
                while cursors[k]<len(events[k]):
                    i=events[k][cursors[k]];cursors[k]+=1
                    seq=base['core_schedules'][k];j=min(len(seq),i+width)
                    if j-i<2 or set(range(i,j))&used[k]:continue
                    ids=[u for sg in seq[i:j] for u in groupops[sg]]
                    if len(ids)>max_ops:continue
                    new=affinity_order(ix,ids)
                    if new==ids:continue
                    edits[k].append((i,j,new));used[k].update(range(i,j));r=detail[k][i]
                    windows.append({'core':k,'group_start_index':i,'group_end_index':j,'ops':len(ids),'trigger_tensor':r['logical_tid'],'trigger_size':r['size'],'old_order':ids,'new_order':new})
                    total+=1;more=True;break
                if total>=limit_windows:break
        nextsg=max(base['node_to_subgraph'].values(),default=-1)+1
        for k,local in edits.items():
            q=[];last=0;seq=base['core_schedules'][k]
            for i,j,us in sorted(local):
                q.extend(seq[last:i])
                for u in us:
                    sg=nextsg;nextsg+=1;p['node_to_subgraph'][str(u)]=sg;q.append(sg)
                last=j
            q.extend(seq[last:]);p['core_schedules'][k]=q
        if not windows:continue
        try:
            newview=check_plan(ix,p)
            for u in ix.ids:
                before=view['core_by_subgraph'][base['node_to_subgraph'][str(u)]]
                after=newview['core_by_subgraph'][p['node_to_subgraph'][str(u)]]
                if before!=after:raise AssertionError('Changed core')
            oldtr=predict_partition_bytes(ix.graph,base,'B');newtr=predict_partition_bytes(ix.graph,p,'B')
            if oldtr!=newtr:raise AssertionError('B partition COPY changed')
        except (ValueError,RuntimeError) as e:
            rejections.append({'width':width,'status':'structural_rejection','error':str(e)[:500]});continue
        rows.append((p,{'name':f'affinity_window{width}','width':width,'windows':windows,'core_assignment_unchanged':True,'B_partition_traffic_unchanged':True,'pre_spill_traffic':newtr}))
    return rows,{'status':'ok','captured_spill_events':sum(map(len,spills.values())),'large_local_event_positions':sum(map(len,events.values())),'base_traffic':traffic,'proposed':len(rows),'rejections':rejections,'window_limit':limit_windows,'max_ops_per_window':max_ops,'seconds':time.perf_counter()-start,'scope':'local refinement + queue changes, original core preserved; hardware cache behavior still exact official'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('graph',type=Path);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--raw',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 ix=GraphIndex(json.loads(a.graph.read_text()));base=json.loads(a.plan.read_text());raw=json.loads(a.raw.read_text())
 if raw['scene']=='A':raise ValueError('B/L2 only')
 rows,diagnostic=candidates(ix,base,raw);a.out.mkdir(parents=True,exist_ok=True);items=[]
 for p,m in rows:
  name=m['name'];write_json(a.out/(name+'.plan.json'),p);items.append({'name':name,'plan':name+'.plan.json','sha256':sha(a.out/(name+'.plan.json')),'meta':m})
 write_json(a.out/'proposals.json',{'candidates':items,'diagnostic':diagnostic})
if __name__=='__main__':main()
