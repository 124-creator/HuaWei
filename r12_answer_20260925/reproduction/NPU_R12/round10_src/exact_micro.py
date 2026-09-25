"""Complete enumeration of a stated finite 3-operation submission domain.
All set partitions, label permutations, core assignments, within-core orders.
Input key serialization is fixed ascending op id; no arbitrary JSON key order search.
This is NOT a claim of exact solution on formal large inputs.
"""
from pathlib import Path
import sys,itertools,json,time
ROOT=Path(__file__).resolve().parents[1]
for d in ('official/code','src','round6_src','round7_src','round10_src'):sys.path.insert(0,str(ROOT/d))
from solver import GraphIndex
from optimizer_v2 import check_plan
from multicore_cut_evaluate_problem_1 import evaluate_scene_a
from multicore_cut_evaluate_problem_2 import evaluate_scene_b
from multicore_cut_evaluate_problem_3 import evaluate_problem_3
from evaluation_validation import read_evaluation_config
from window_bound import bound,brute
from solve_round6 import write_json,execute,sha
CFG=read_evaluation_config(str(ROOT/'official/data/config.txt'))
EV={'A':(evaluate_scene_a,dict(cross_core_wait=1000,same_core_wait=100)),'B':(evaluate_scene_b,dict(cross_core_copy_delay=500)),'L2':(evaluate_problem_3,dict(cross_core_copy_delay=500,cache_capacity_bytes=1048576,cache_bandwidth_bytes_per_cycle=250))}
def toy(edges,mixed=False):
    tensors=[{'id':10+i,'size':256+128*i,'pos':'UB'} for i in range(3)]
    ops=[{'id':100+i,'op':'ADD','pipe':'PIPE_M' if mixed and i==1 else 'PIPE_V','cycles':c} for i,c in enumerate([701,307,911])]
    es=[{'source':100+i,'target':10+i} for i in range(3)]+[{'source':10+u,'target':100+v} for u,v in edges]
    for i in range(3):
        if not any(v==i for u,v in edges):
            tensors += [{'id':1000+i,'size':128,'pos':'DDR'},{'id':1100+i,'size':128,'pos':'UB'}]
            ops += [{'id':1200+i,'op':'COPY_IN','pipe':'PIPE_MTE2','cycles':1}]
            es += [{'source':1000+i,'target':1200+i},{'source':1200+i,'target':1100+i},{'source':1100+i,'target':100+i}]
        if not any(u==i for u,v in edges):
            tensors += [{'id':2000+i,'size':256+128*i,'pos':'DDR'}];ops += [{'id':2100+i,'op':'COPY_OUT','pipe':'PIPE_MTE3','cycles':1}]
            es += [{'source':10+i,'target':2100+i},{'source':2100+i,'target':2000+i}]
    return {'ops':ops,'tensors':tensors,'edges':es}
def plans(n):
    for labels in itertools.product(range(3),repeat=3):
        k=max(labels)+1
        if set(labels)!=set(range(k)):continue
        for owners in itertools.product(range(n),repeat=k):
            lists=[[i for i in range(k) if owners[i]==j] for j in range(n)]
            for orders in itertools.product(*(list(itertools.permutations(x)) for x in lists)):
                yield {'node_to_subgraph':{str(100+i):labels[i] for i in range(3)},'core_schedules':[list(x) for x in orders]}
def main():
    out=ROOT/'round10_results/micro';out.mkdir(parents=True,exist_ok=True);records=[];begin=time.perf_counter();eval_count=0;reject_count=0
    write_json(out/'protocol.json',{'nodes':3,'forward_edge_patterns':8,'pipe_patterns':['VVV','VMV'],'core_counts':[2,3],'scenes':['A','B','L2'],'domain':'all surjective labels 0..k-1, all owners, all queues; op-key order ascending','comparison':'fresh R10 from graph; evaluator unmodified','source_sha':sha(__file__)})
    all_edges=[(0,1),(0,2),(1,2)]
    for mixed in [False,True]:
      for mask in range(8):
        edges=[e for j,e in enumerate(all_edges) if mask>>j&1];g=toy(edges,mixed);ix=GraphIndex(g);gid=f'micro_{int(mixed)}_{mask}';gp=out/(gid+'.json');write_json(gp,g)
        for n in [2,3]:
          lb=bound(ix,n)['window_lower_bound'];assert lb==brute(ix,n)
          best={s:(float('inf'),None,None) for s in EV};valid={s:0 for s in EV};attempted=0
          for p in plans(n):
            attempted+=1
            try:check_plan(ix,p)
            except (ValueError,RuntimeError):reject_count+=1;continue
            for s,(e,kw) in EV.items():
              try:r=e(g,p,**CFG,**kw)
              except (ValueError,RuntimeError):reject_count+=1;continue
              eval_count+=1;valid[s]+=1;assert lb<=r['makespan']
              if r['makespan']<best[s][0]:best[s]=(r['makespan'],p,r)
          for s in EV:
            ident=f'{gid}_n{n}_{s}';d=out/ident;d.mkdir(exist_ok=True)
            write_json(d/'optimal_plan.json',best[s][1]);write_json(d/'optimal_official.json',best[s][2])
            cmd=[sys.executable,'-S',str(ROOT/'round10_src/solve_round10.py'),str(gp),'-n',str(n),'--scene',s,'--out',str(d/'solver'),'--budget','60']
            proc=execute(cmd,65,d/'solver.log');rp=d/'solver/report.json';r=json.loads(rp.read_text()) if rp.exists() else {}
            actual=r.get('selected',{}).get('makespan');records.append({'id':ident,'edges':edges,'mixed':mixed,'cores':n,'scene':s,'attempted_plans':attempted,'valid_official_plans':valid[s],'enumerated_minimum':best[s][0],'global_window_lower_bound':lb,'solver_status':r.get('status'),'solver_makespan':actual,'solver_matches_domain_optimum':actual==best[s][0],'strict_global_certificate':actual==lb,'process':proc['status']})
            write_json(out/'summary.json',{'declared':96,'records':records,'complete':len(records)==96,'official_evaluations':eval_count,'rejections':reject_count,'seconds':time.perf_counter()-begin})
        print(gid,'finished',len(records),'evaluations',eval_count,flush=True)
if __name__=='__main__':main()
