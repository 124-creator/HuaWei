"""v0.2: bounded portfolio, exact pre-spill bounds, official evaluated incumbent.

Exploratory contractions/frontier variants are NOT deployed by default: the
controlled tests found frequent regressions. Defaults retain original baselines
and test whole-component ordering/batching plus bounded exact-byte migrations.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, sys, time
from copy import deepcopy


def main():
    p=argparse.ArgumentParser()
    p.add_argument('graph',type=Path);p.add_argument('--official',required=True,type=Path)
    p.add_argument('-n','--cores',required=True,type=int);p.add_argument('--scene',choices=['A','B','L2'],required=True)
    p.add_argument('-o','--output',required=True,type=Path);p.add_argument('--budget',type=float,default=600)
    p.add_argument('--per-eval-timeout',type=float,default=120);p.add_argument('--workdir',type=Path)
    p.add_argument('--relative-gap-stop',type=float,default=0,help='Optional certified global compute-bound gap; 0 disables early stopping')
    p.add_argument('--resume',action='store_true');p.add_argument('--exploratory',action='store_true')
    a=p.parse_args()
    if a.cores<1 or a.budget<=0 or a.per_eval_timeout<=0 or a.relative_gap_stop<0:p.error('positive core count and time budgets required')
    if a.output.exists():p.error('Output exists; choose a fresh path to avoid stale-result confusion')
    official=a.official.resolve();sys.path.insert(0,str(official/'code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_3 import read_cache_config
    from solver import GraphIndex,make_plan
    from optimizer_v2 import component_batch_plan,affinity_components,contract_adjacent,frontier_plan
    from bounds import candidate_lower_bound, global_compute_lower_bound
    from migration import migrate_blocks
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    from run_experiments import run_job,source_hash
    start=time.perf_counter();graph_path=a.graph.resolve();g=json.loads(graph_path.read_text(encoding='utf-8'));ix=GraphIndex(g)
    cfg=read_evaluation_config(str(official/'data/config.txt'))
    cbw=read_cache_config(str(official/'data/config.txt'))['cache_bandwidth_bytes_per_cycle']
    global_bound=global_compute_lower_bound(ix,a.cores)
    work=a.workdir.resolve() if a.workdir else a.output.resolve().parent/(a.output.stem+'_work')
    work.mkdir(parents=True,exist_ok=True)
    comp,cm=make_plan(g,a.cores,'components',a.scene,official,ix)
    chain,chm=make_plan(g,a.cores,'chainwave',a.scene,official,ix)
    variants=[('components',comp,cm),('chainwave',chain,chm)]
    multi=len(ix.components())>1
    if multi:
        for target in ([512,2048] if a.scene=='A' else [0,512]):
            plan,meta=component_batch_plan(ix,comp,target,'residency',cfg['capacity'])
            variants.append(('component_ordered' if target==0 else f'component_batch{target}',plan,meta))
        if a.scene!='A' and a.exploratory:
            for w in (0.5,2.0):
                base,bmeta=affinity_components(ix,a.cores,cfg['bandwidth'],w)
                plan,meta=component_batch_plan(ix,base,512,'residency',cfg['capacity']);meta['packing']=bmeta
                variants.append((f'affinity{w:g}_batch512',plan,meta))
    if a.scene!='A':
        delay=read_scene_b_config(str(official/'data/config.txt'))['cross_core_copy_delay_cycles']
        for weight in (0.0,0.2):
            plan,meta=migrate_blocks(ix,chain,cfg['bandwidth'],delay,weight)
            variants.append((f'migrate{weight:g}',plan,meta))
    if a.exploratory:
        for rounds in (1,4):
            plan,meta=contract_adjacent(ix,chain,rounds);variants.append((f'chainmerge{rounds}',plan,meta))
        if a.scene!='A':
            plan,meta=frontier_plan(ix,chain,cfg['capacity']);variants.append(('chainfrontier',plan,meta))
    # Large scene-A tasks can be very expensive in the unmodified evaluator.
    # Evaluate the small-Task construction first to obtain a feasible incumbent.
    if a.scene=='A' and multi and len(ix.ids)>10000:
        variants.sort(key=lambda x:(x[0]!='component_batch512',x[0]!='components'))
    seen={};candidates=[];aliases=[]
    for name,plan,meta in variants:
        text=json.dumps(plan,sort_keys=True);fp=hashlib.sha256(text.encode()).hexdigest()
        if fp in seen:aliases.append({'name':name,'same_plan_as':seen[fp]});continue
        seen[fp]=name;path=work/(name+'_plan.json');path.write_text(text,encoding='utf-8')
        bound=candidate_lower_bound(ix,plan,a.scene,cfg['bandwidth'],cbw)
        candidates.append((name,path,meta,bound))
    generation_seconds=time.perf_counter()-start
    results=[];best=None;code_hash=source_hash(official)
    for i,(name,path,meta,bound) in enumerate(candidates):
        if best and a.relative_gap_stop>0 and global_bound['global_lower_bound_cycles']>0 and best['makespan'] <= (1+a.relative_gap_stop)*global_bound['global_lower_bound_cycles']:
            results.append({'variant':name,'status':'certified_gap_stop','global_bound':global_bound});continue
        if best and bound['lower_bound_cycles']>best['makespan']:
            results.append({'variant':name,'status':'bound_pruned','bound':bound,'incumbent_makespan':best['makespan']});continue
        remain=a.budget-(time.perf_counter()-start)
        if remain<=0:
            results.append({'variant':name,'status':'budget_skipped','bound':bound});continue
        timeout=min(a.per_eval_timeout,max(.1,remain/(len(candidates)-i)))
        row=run_job({'graph':str(graph_path),'plan':str(path),'mode':a.scene,'variant':name,'cores':a.cores,
                     'output':str(work/(name+'_result.json'))},official,timeout,a.resume,code_hash,False)
        row['bound']=bound;row['construction']=meta;results.append(row)
        if row['status']=='ok':
            if row['makespan']<bound['lower_bound_cycles']:raise AssertionError('lower bound contradicted by official result')
            if best is None or (row['makespan'],row['data_movement_bytes']['added_copy_bytes'],name)<(best['makespan'],best['data_movement_bytes']['added_copy_bytes'],best['variant']):best=row
    report={'algorithm':'v0.2 bounded portfolio with resource-bound pruning','status':'ok' if best else 'no_evaluated_feasible_plan',
            'case':graph_path.stem,'scene':a.scene,'cores':a.cores,'global_compute_bound':global_bound,'relative_gap_stop':a.relative_gap_stop,
            'solver_source_sha256':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('solve_case_v2.py','optimizer_v2.py','migration.py','bounds.py','solver.py','traffic_model.py','run_experiments.py','eval_worker.py')},'soft_budget_seconds':a.budget,
            'generation_and_bound_seconds':generation_seconds,'wall_seconds':time.perf_counter()-start,
            'aliases':aliases,'evaluations':results,'selected_variant':best['variant'] if best else None}
    if best:
        a.output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(work/(best['variant']+'_plan.json'),a.output)
        report.update(makespan=best['makespan'],added_copy_bytes=best['data_movement_bytes']['added_copy_bytes'],
                      plan_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())
    a.output.with_suffix('.selection.json').parent.mkdir(parents=True,exist_ok=True)
    a.output.with_suffix('.selection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('aliases','evaluations')},indent=2))
    return 0 if best else 2
if __name__=='__main__':raise SystemExit(main())
