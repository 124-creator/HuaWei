"""R12 exact-calendar acceleration of the supplied HEFT-style constructor.
The same ranks, duration proxy, cores, and tie rules are retained. A fast plan is
claimed equivalent only on independently compared configurations, not by name.
"""
from __future__ import annotations
import sys,heapq,time,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for d in ('official/code','src','round6_src','round7_src','round10_src','round11_src','round12_src'):
    sys.path.insert(0,str(ROOT/d))
from solver import GraphIndex
from task_frontier import task_features,duration_floor
from optimizer_v2 import check_plan
from fast_calendar import GapCalendar
from runtime import write_json,sha

def fast_heft(index,n,scene):
    if n<1 or scene not in ('A','B','L2'):raise ValueError('Invalid core count or scene')
    t0=time.perf_counter();groups,bo,_,_=index.chain_blocks()
    f=task_features(index,groups);pred=f['pred'];succ=f['succ'];dur={i:max(1,duration_floor(f,i)) for i in pred}
    edgebytes={}
    for t in index.tensors:
        ps={bo[u] for u in index.producers[t]};cs={bo[u] for u in index.consumers[t]}
        for a in ps:
            for b in cs-{a}:edgebytes[(a,b)]=edgebytes.get((a,b),0)+index.tensors[t]['size']
    sync=1000 if scene=='A' else 500
    rank={}
    for u in reversed(f['topo']):rank[u]=dur[u]+max((sync+2*edgebytes.get((u,v),0)/60+rank[v] for v in succ[u]),default=0)
    degree={u:len(pred[u]) for u in pred};ready=[(-rank[u],u) for u in pred if degree[u]==0];heapq.heapify(ready)
    pre_seconds=time.perf_counter()-t0;tcal=time.perf_counter()
    calendars=[GapCalendar(100 if scene=='A' else 0) for _ in range(n)];owners={};finish={}
    while ready:
        _,u=heapq.heappop(ready);slots=[];keys=[]
        for k in range(n):
            r=max((finish[p]+(sync+2*edgebytes.get((p,u),0)/60 if owners[p]!=k else 0) for p in pred[u]),default=0)
            start,key=calendars[k].find(r,dur[u]);slots.append((start+dur[u],start,k));keys.append(key)
        end,start,k=min(slots);owners[u]=k;finish[u]=end
        calendars[k].occupy(keys[k],start,dur[u],u)
        for v in sorted(succ[u]):
            degree[v]-=1
            if degree[v]==0:heapq.heappush(ready,(-rank[v],v))
    cal_seconds=time.perf_counter()-tcal;tv=time.perf_counter()
    plan={'node_to_subgraph':{str(u):b for b,g in enumerate(groups) for u in g},
          'core_schedules':[[u for a,b,u in cal.ordered_tasks()] for cal in calendars]}
    check_plan(index,plan)
    return plan,{'variant':'indexed_HEFT_style_chain','groups':len(groups),'query_node_visits':sum(c.query_visits for c in calendars),
        'feature_seconds':pre_seconds,'calendar_seconds':cal_seconds,'validation_seconds':time.perf_counter()-tv,
        'seconds':time.perf_counter()-t0,'official_code_changed':False,'deterministic_index':True}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('graph',type=Path);ap.add_argument('-n',type=int,required=True)
    ap.add_argument('--scene',choices=['A','B','L2'],default='B');ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--reference',action='store_true');a=ap.parse_args();start=time.perf_counter()
    ix=GraphIndex(json.loads(a.graph.read_text(encoding='utf-8')))
    if a.reference:
        from heft_baseline import heft
        p,m=heft(ix,a.n,a.scene)
    else:p,m=fast_heft(ix,a.n,a.scene)
    a.out.mkdir(parents=True,exist_ok=True);write_json(a.out/'plan.json',p)
    write_json(a.out/'generation.json',{'status':'ok','reference':a.reference,'case':a.graph.stem,'scene':a.scene,'cores':a.n,'plan_sha256':sha(a.out/'plan.json'),'meta':m,'total_seconds':time.perf_counter()-start})
if __name__=='__main__':main()
