"""Documented HEFT-style adaptation, not a claim of unmodified original HEFT.
Shared preprocessing: nonbranching chain contraction only. Upward rank + insertion
on N homogeneous virtual processors. Duration proxy=max(M,V,internal CP,IO/60).
Communication proxy is edge tensor volume/60 twice + scene synchronization.
Final score is the unchanged official model, with its dual Pipes and memory.
"""
from pathlib import Path
import sys,json,time,heapq,bisect
ROOT=Path(__file__).resolve().parents[1]
for d in ('src','round6_src','round7_src','official/code'):sys.path.insert(0,str(ROOT/d))
from solver import GraphIndex
from task_frontier import task_features,duration_floor
from optimizer_v2 import check_plan
from solve_round6 import write_json,sha
from run_experiments import run_job,source_hash

def heft(index,n,scene):
    groups,bo,_,_=index.chain_blocks();f=task_features(index,groups);pred=f['pred'];succ=f['succ'];dur={i:max(1,duration_floor(f,i)) for i in pred}
    edgebytes={}
    for t in index.tensors:
        ps={bo[u] for u in index.producers[t]};cs={bo[u] for u in index.consumers[t]}
        for a in ps:
            for b in cs-{a}:edgebytes[(a,b)]=edgebytes.get((a,b),0)+index.tensors[t]['size']
    sync=1000 if scene=='A' else 500
    rank={}
    for u in reversed(f['topo']):rank[u]=dur[u]+max((sync+2*edgebytes.get((u,v),0)/60+rank[v] for v in succ[u]),default=0)
    degree={u:len(pred[u]) for u in pred};ready=[(-rank[u],u) for u in pred if degree[u]==0];heapq.heapify(ready)
    calendars=[[] for _ in range(n)];owners={};finish={};starts={}
    while ready:
        _,u=heapq.heappop(ready);slots=[]
        for k in range(n):
            r=max((finish[p]+(sync+2*edgebytes.get((p,u),0)/60 if owners[p]!=k else 0) for p in pred[u]),default=0)
            t=r;gap=100 if scene=='A' else 0
            for a,b,j in calendars[k]:
                if t+dur[u]+gap<=a:break
                if t<b+gap:t=b+gap
            slots.append((t+dur[u],t,k))
        end,start,k=min(slots);owners[u]=k;finish[u]=end;starts[u]=start;bisect.insort(calendars[k],(start,end,u))
        for v in sorted(succ[u]):
            degree[v]-=1
            if degree[v]==0:heapq.heappush(ready,(-rank[v],v))
    plan={'node_to_subgraph':{str(u):b for b,g in enumerate(groups) for u in g},'core_schedules':[[u for a,b,u in cal] for cal in calendars]}
    check_plan(index,plan)
    return plan,{'variant':'HEFT_style_chain_adaptation','duration_proxy':'max(M,V,internalCP,local pre-spill IO/60), >=1','insertion':True,'shared_preprocessing':'nonbranching chain blocks','not_original_HEFT_hardware_model':True,'groups':len(groups)}

def main():
    data=sorted((ROOT/'official/data').glob('case_*.json'))
    sized=sorted([(sum(o['op'] not in ('COPY_IN','COPY_OUT') for o in json.loads(p.read_text())['ops']),p) for p in data])
    chosen=[sized[i][1] for i in range(2,100,5)];out=ROOT/'round10_results/heft';out.mkdir(parents=True,exist_ok=True)
    write_json(out/'protocol.json',{'cases':[p.stem for p in chosen],'selection':'20 equal-size-rank strata; index 2,7,...97 in (non-COPY count, filename) sort','cores':5,'scene':'B','total_request_soft_budget':600,'official_evaluation_timeout':120,'source_sha':sha(__file__),'independent':True})
    rows=[]
    for g in chosen:
        t=time.perf_counter();d=out/g.stem;d.mkdir(exist_ok=True);ix=GraphIndex(json.loads(g.read_text()));plan,meta=heft(ix,5,'B');write_json(d/'plan.json',plan)
        row=run_job({'graph':str(g),'plan':str(d/'plan.json'),'mode':'B','variant':'heft_adapted','cores':5,'output':str(d/'result.json')},ROOT/'official',min(120,max(.1,600-(time.perf_counter()-t))),False,source_hash(ROOT/'official'),False)
        rows.append({'case':g.stem,'status':row['status'],'makespan':row.get('makespan'),'generation_and_evaluation_wall':time.perf_counter()-t,'meta':meta,'plan_sha':sha(d/'plan.json'),'result_meta':str((d/'result.json').relative_to(ROOT))})
        write_json(out/'summary.json',{'declared':20,'records':rows,'complete':len(rows)==20})
if __name__=='__main__':main()
