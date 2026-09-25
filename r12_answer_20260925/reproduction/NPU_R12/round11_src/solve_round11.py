"""R11.0: unchanged R10 plus ONE budgeted HEFT-style insertion-list candidate.
This is an explicit candidate-portfolio closure, not a claim to invent HEFT.
All stages share one soft wall-clock budget. Only graph/config/source inputs;
never loads historical scores/plans. Extra candidate is optional on timeout.
"""
from __future__ import annotations
from pathlib import Path
import argparse,json,platform,shutil,sys,time
ROOT=Path(__file__).resolve().parents[1]
for d in ('official/code','src','round6_src','round7_src','round10_src','round11_src'):
    sys.path.insert(0,str(ROOT/d))
from runtime import execute,write_json,sha
from run_experiments import source_hash,run_job
from solver import GraphIndex
from optimizer_v2 import check_plan
from heft_baseline import heft
from window_bound import bound
from bounds import candidate_lower_bound

def sources():
    return {str(p.relative_to(ROOT)):sha(p) for d in ('official/code','src','round6_src','round7_src','round10_src','round11_src') for p in sorted((ROOT/d).glob('*.py'))}

def generate(graph: Path,n: int,scene: str,out: Path) -> None:
    t=time.perf_counter();ix=GraphIndex(json.loads(graph.read_text(encoding='utf-8')))
    p,m=heft(ix,n,scene);check_plan(ix,p)
    write_json(out/'plan.json',p)
    # Conservative resource bound only; no proxy duration/rank is a pruning proof.
    lb=candidate_lower_bound(ix,p,scene,60)
    write_json(out/'proposal.json',{'generator':'unchanged round10_src.heft_baseline.heft',
        'plan_sha256':sha(out/'plan.json'),'meta':m,'resource_lower_bound':lb,
        'global_window':bound(ix,n),'generation_seconds':time.perf_counter()-t})

def read_candidate(report_path: Path) -> dict | None:
    if not report_path.is_file():return None
    r=json.loads(report_path.read_text(encoding='utf-8'))
    if r.get('status')!='ok':return None
    selection=r['selected'];base=report_path.parent
    p=base/selection['plan'];raw=base/selection['raw']
    if not p.is_file() or not raw.is_file():raise ValueError('Control selected files missing')
    if sha(raw)!=r['selected_raw_sha256']:raise ValueError('Control raw digest mismatch')
    if sha(p)!=r['selected_plan_sha256']:raise ValueError('Control selected plan digest mismatch')
    original=json.loads(raw.read_text(encoding='utf-8'))
    if original['makespan']!=selection['makespan']:raise ValueError('Control result value mismatch')
    return {'name':'R10:'+selection['name'],'makespan':original['makespan'],
        'added_copy_bytes':original['data_movement_bytes']['added_copy_bytes'],'plan':p,'raw':raw}

def solve(graph:Path,n:int,scene:str,out:Path,budget:float=600,profile:str='full') -> dict:
    if n<1 or scene not in ('A','B','L2') or budget<=0 or profile not in ('full','control','insertion_only'):
        raise ValueError('Invalid request')
    graph=graph.resolve();out=out.resolve();t=time.perf_counter()
    if out.exists() and any(out.iterdir()):raise FileExistsError('Output must be empty/new; no stale result reuse')
    out.mkdir(parents=True,exist_ok=True)
    remaining=lambda:max(0.0,budget-(time.perf_counter()-t))
    r={'protocol':'R11.0','case':graph.stem,'cores':n,'scene':scene,'profile':profile,'budget_seconds':budget,
       'status':'running','input_policy':'original graph, config, immutable source; no historical plans or scores',
       'graph_sha256':sha(graph),'config_sha256':sha(ROOT/'official/data/config.txt'),
       'official_source_sha256':source_hash(ROOT/'official'),'source_files':sources(),
       'environment':{'python':sys.version,'platform':platform.platform()},'stages':[]}
    write_json(out/'report.json',r)
    def snap(c):
        if c is None:return None
        return {k:str(v.relative_to(out)) if isinstance(v,Path) else v for k,v in c.items()}
    best=None
    if profile!='insertion_only':
        cmd=[sys.executable,'-S',str(ROOT/'round10_src/solve_round10.py'),str(graph),'-n',str(n),'--scene',scene,
             '--budget',str(max(.1,remaining()-.5)),'--out',str(out/'control')]
        r['control_process']=execute(cmd,max(.1,remaining()),out/'control.log')
        best=read_candidate(out/'control/report.json')
    r['control']=snap(best);write_json(out/'report.json',r)
    if profile!='control' and remaining()>.5:
        folder=out/'insertion';folder.mkdir()
        cmd=[sys.executable,'-S',__file__,str(graph),'-n',str(n),'--scene',scene,'--out',str(folder),'--generate']
        stage={'kind':'insertion_chain_candidate','generation':execute(cmd,min(30,remaining()),folder/'generation.log')}
        pp=folder/'plan.json';info=folder/'proposal.json'
        if stage['generation']['status']=='ok' and pp.is_file() and info.is_file():
            proposal=json.loads(info.read_text(encoding='utf-8'));stage['proposal']=proposal
            plan=json.loads(pp.read_text(encoding='utf-8'))
            duplicate=(best is not None and plan==json.loads(best['plan'].read_text(encoding='utf-8')))
            lb=proposal['resource_lower_bound']['lower_bound_cycles']
            if duplicate:stage['status']='duplicate_plan'
            elif best is not None and lb>best['makespan']:stage['status']='resource_bound_pruned'
            elif remaining()<=.2:stage['status']='budget_exhausted'
            else:
                result=run_job({'graph':str(graph),'plan':str(pp),'mode':scene,'variant':'insertion_chain',
                    'cores':n,'output':str(folder/'meta.json')},ROOT/'official',min(120,remaining()),False,r['official_source_sha256'],False)
                stage.update(status=result['status'],evaluation_metadata='insertion/meta.json',evaluation_wall_seconds=result['wall_seconds'])
                if result['status']=='ok':
                    rp=folder/result['official_result_file'];raw=json.loads(rp.read_text(encoding='utf-8'))
                    if raw['makespan']<proposal['global_window']['window_lower_bound']:
                        raise AssertionError('Candidate violates independently derived global bound')
                    cand={'name':'insertion_chain','makespan':raw['makespan'],
                          'added_copy_bytes':raw['data_movement_bytes']['added_copy_bytes'],'plan':pp,'raw':rp}
                    stage['candidate']=snap(cand)
                    if best is None or (cand['makespan'],cand['added_copy_bytes'],cand['name'])<(best['makespan'],best['added_copy_bytes'],best['name']):best=cand
        else:stage['status']='generation_'+stage['generation']['status']
        r['stages'].append(stage)
    elif profile!='control':r['stages'].append({'kind':'insertion_chain_candidate','status':'budget_exhausted'})
    if best is None:
        r.update(status='no_valid_solution',wall_seconds=time.perf_counter()-t)
    else:
        shutil.copy2(best['plan'],out/'selected_plan.json')
        r.update(status='ok',selected=snap(best),selected_plan_sha256=sha(out/'selected_plan.json'),
                 selected_raw_sha256=sha(best['raw']),wall_seconds=time.perf_counter()-t)
    r['budget_exceeded']=r['wall_seconds']>budget
    write_json(out/'report.json',r);return r

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('graph',type=Path);ap.add_argument('-n','--cores',type=int,required=True)
    ap.add_argument('--scene',choices=['A','B','L2'],required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--budget',type=float,default=600);ap.add_argument('--profile',choices=['full','control','insertion_only'],default='full');ap.add_argument('--generate',action='store_true')
    a=ap.parse_args()
    if a.generate:
        a.out.mkdir(parents=True,exist_ok=True);generate(a.graph,a.cores,a.scene,a.out)
    else:
        r=solve(a.graph,a.cores,a.scene,a.out,a.budget,a.profile)
        print(json.dumps({k:r.get(k) for k in ('status','case','scene','cores','control','selected','wall_seconds')},ensure_ascii=False),flush=True)
        raise SystemExit(0 if r['status']=='ok' else 2)
