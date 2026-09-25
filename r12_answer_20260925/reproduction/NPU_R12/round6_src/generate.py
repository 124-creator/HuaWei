"""Timeout-isolated candidate generator, called by solve_round6.py."""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
from advanced import ROOT,GraphIndex,core_candidates,critical_candidates,plan_hash

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True)
    ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--raw',type=Path,required=True)
    ap.add_argument('--scene',choices=['A','B','L2'],required=True)
    ap.add_argument('--kind',choices=['core','critical'],required=True)
    ap.add_argument('--limit',type=int,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
    graph=json.loads(a.graph.read_text(encoding='utf-8'));index=GraphIndex(graph)
    plan=json.loads(a.plan.read_text(encoding='utf-8'));raw=json.loads(a.raw.read_text(encoding='utf-8'))
    if a.kind=='core':
        proposals,meta=core_candidates(index,len(plan['core_schedules']),a.scene,raw['makespan'],ROOT/'official',a.limit)
    else:
        if a.scene=='A' or len(index.ids)>10000:
            proposals,meta=[],{'status':'skipped_scope','max_ops_for_trace':10000}
        else:
            from multicore_cut_evaluate_problem_2 import _build_scene_b_tasks
            from evaluation_validation import read_evaluation_config,validate_execution
            from trace_attribution import attribute,fifo_audit
            tasks,links,_,movement,_=_build_scene_b_tasks(graph,plan,**read_evaluation_config(str(ROOT/'official/data/config.txt')))
            validate_execution(tasks,links)
            if movement!=raw['data_movement_bytes']:raise AssertionError('prepared task movement does not match official result')
            analysis=attribute(tasks,links,raw)
            if a.scene=='L2':analysis['fifo']=fifo_audit(raw)
            (a.out/'trace_analysis.json').write_text(json.dumps(analysis,ensure_ascii=False),encoding='utf-8')
            proposals,meta=critical_candidates(index,plan,analysis,a.scene,a.limit)
            meta['critical_chain_decomposition']=analysis['critical_chain_duration_decomposition']
    rows=[]
    for p,m in proposals:
        pp=a.out/(m['name']+'_plan.json');pp.write_text(json.dumps(p,sort_keys=True),encoding='utf-8')
        rows.append({'plan_file':pp.name,'meta':m,'plan_sha256':plan_hash(p)})
    (a.out/'proposals.json').write_text(json.dumps({'rows':rows,'metadata':meta,'wall_seconds':time.perf_counter()-start},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
