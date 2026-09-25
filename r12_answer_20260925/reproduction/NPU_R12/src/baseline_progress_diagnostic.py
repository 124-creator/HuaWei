"""Observational profiler for unmodified official baseline; never emits a score.
Aborts only this diagnostic when repeated step3 state makes no progress.
"""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path

class DiagnosticStop(Exception):pass

def main():
 p=argparse.ArgumentParser();p.add_argument('--official',type=Path,required=True);p.add_argument('--graph',type=Path,required=True);p.add_argument('-o',type=Path,required=True);p.add_argument('--seconds',type=float,default=80);a=p.parse_args()
 sys.path.insert(0,str(a.official.resolve()/'code'))
 from singlecore_evaluate import evaluate_singlecore
 from evaluation_validation import read_evaluation_config
 from multicore_cut_evaluate_problem_1 import read_scene_a_config
 g=json.loads(a.graph.read_text());settings=read_evaluation_config(str(a.official/'data/config.txt'));waits=read_scene_a_config(str(a.official/'data/config.txt'))
 snapshots=[];last=None;same=0;st=time.perf_counter();status='time_limit';detail={};last_emit=0
 def profile(frame,event,arg):
  nonlocal last,same,last_emit,status,detail
  if event=='return' and frame.f_code.co_name=='retire_step' and frame.f_code.co_filename.endswith('schedule_step3.py'):
   outer=frame.f_back.f_locals;now=outer.get('t_now');iteration=outer.get('iteration');issued=len(outer.get('op_start',{}));key=(now,issued)
   same=same+1 if key==last else 0;last=key
   if iteration<=12 or iteration%1000==0 or same==32:
    snap={'iteration':iteration,'time':now,'issued':issued,'total_ops':len(outer.get('op_status',{})),'wall_seconds':time.perf_counter()-st,'consecutive_equal_state':same,'executors':outer.get('executors')}
    snapshots.append(json.loads(json.dumps(snap)));a.o.parent.mkdir(parents=True,exist_ok=True);a.o.write_text(json.dumps({'status':'running','snapshots':snapshots},indent=2))
   if same>=32:
    status='repeated_time_and_issued_state';detail={'ddr_remaining_work':outer.get('ddr_remaining_work'), 'ddr_last_update':outer.get('ddr_last_update'), 'status_counts':{s:list(outer.get('op_status',{}).values()).count(s) for s in ('done','running','pending','ready')},'memory_used':outer.get('memory_used')};raise DiagnosticStop(status)
  if time.perf_counter()-st>a.seconds:raise DiagnosticStop('diagnostic_time_limit')
 try:
  sys.setprofile(profile)
  r=evaluate_singlecore(g,**settings,cross_core_wait=waits['task_cross_core_wait_cycles'],same_core_wait=waits['task_same_core_wait_cycles'])
  status='diagnostic_completed_not_a_timing_benchmark';detail={'observed_makespan':r['makespan']}
 except DiagnosticStop as e:detail['stop_reason']=str(e)
 finally:sys.setprofile(None)
 out={'case':a.graph.stem,'status':status,'profiled_wall_seconds':time.perf_counter()-st,'snapshots':snapshots,'detail':detail,'score_eligible':False}
 a.o.write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='snapshots'}))
if __name__=='__main__':main()
