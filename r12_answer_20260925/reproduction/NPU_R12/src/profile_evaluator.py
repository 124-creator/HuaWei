"""Diagnostic-only cProfile wrapper; source/config are never modified.
Profiling overhead means these times are not official runtime benchmarks.
"""
from pathlib import Path
import argparse,cProfile,json,pstats,signal,sys,time,io
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'official/code'))
class ProfileTimeout(Exception):pass

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',default='case_014');p.add_argument('--seconds',type=int,default=45);a=p.parse_args()
    from singlecore_evaluate import evaluate_singlecore
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    from evaluation_validation import read_evaluation_config
    g=json.loads((ROOT/'official/data'/(a.case+'.json')).read_text());cfg=str(ROOT/'official/data/config.txt')
    settings=read_evaluation_config(cfg);wait=read_scene_a_config(cfg)
    def stop(sig,frame):raise ProfileTimeout('Diagnostic cutoff, not a feasibility result')
    signal.signal(signal.SIGALRM,stop);signal.alarm(a.seconds)
    prof=cProfile.Profile();t=time.perf_counter();status='complete'
    try:
        prof.enable()
        r=evaluate_singlecore(g,**settings,cross_core_wait=wait['task_cross_core_wait_cycles'],same_core_wait=wait['task_same_core_wait_cycles'])
    except ProfileTimeout:status='diagnostic_cutoff'
    finally:
        prof.disable();signal.alarm(0)
        path=ROOT/'reports'/(a.case+'_profile');prof.dump_stats(str(path)+'.prof')
        stream=io.StringIO();s=pstats.Stats(prof,stream=stream).strip_dirs().sort_stats('cumulative');s.print_stats(35)
        path.with_suffix('.txt').write_text(stream.getvalue())
        funcs=[]
        for (file,line,name),(cc,nc,tt,ct,_) in s.stats.items():
            funcs.append({'file':file,'line':line,'name':name,'calls':nc,'self_seconds':tt,'cumulative_seconds':ct})
        path.with_suffix('.json').write_text(json.dumps({'status':status,'wall_seconds':time.perf_counter()-t,
            'warning':'Instrumented partial profile; no makespan/feasibility or independent runtime conclusion',
            'functions':sorted(funcs,key=lambda x:-x['cumulative_seconds'])[:60]},indent=2))
if __name__=='__main__':main()
