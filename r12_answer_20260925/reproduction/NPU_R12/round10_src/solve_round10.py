"""R10: validated R7 incumbent + component-family closure + optional B->L2.
No historical result lookup. Each request owns a single soft wall-clock budget.
"""
from __future__ import annotations
from pathlib import Path
import sys, json, time, shutil, argparse, platform, hashlib
ROOT=Path(__file__).resolve().parents[1]
for d in ('official/code','src','round6_src','round7_src','round10_src'):sys.path.insert(0,str(ROOT/d))
from solve_round6 import execute,write_json,sha
from run_experiments import run_job,source_hash
from solver import GraphIndex,make_plan
from optimizer_v2 import component_batch_plan,canonicalize,check_plan
from advanced import append_idle_cores,placement_bound
from task_frontier import task_lower_bound
from window_bound import bound,times

def semantic_hash(plan):return hashlib.sha256(json.dumps(canonicalize(plan),sort_keys=True).encode()).hexdigest()

def generate(graph,n,scene,incumbent,out):
    t=time.perf_counter();ix=GraphIndex(json.loads(Path(graph).read_text()));pre=times(ix);rows=[];seen=set();log=[]
    for m in range(n,0,-1):
        w=bound(ix,m,pre)
        if w['window_lower_bound']>incumbent:
            log.append({'active_limit':m,'status':'global_window_pruned','bound':w});continue
        seed,_=make_plan(ix.graph,m,'components',scene,ROOT/'official',ix)
        variants=[('components',seed)]
        if len(ix.components())>1:
            for target in (0,512,2048):
                p,_=component_batch_plan(ix,seed,target,'residency',{'L1':524288,'UB':131072})
                variants.append((f'ordered_{target}',p))
        for name,p in variants:
            p=append_idle_cores(p,n);finger=semantic_hash(p)
            if finger in seen:continue
            seen.add(finger);lb=task_lower_bound(ix,p) if scene=='A' else placement_bound(ix,p,scene)
            lb['global_window']=w['window_lower_bound'];lb['lower_bound_cycles']=max(lb['lower_bound_cycles'],w['window_lower_bound'])
            name=f'm{m}_{name}';path=Path(out)/(name+'_plan.json');write_json(path,p)
            rows.append({'name':name,'active_limit':m,'plan_file':path.name,'bound':lb,'semantic_sha':finger})
    rows.sort(key=lambda r:(r['bound']['lower_bound_cycles'],r['bound']['pre_spill_traffic']['pre_spill_copy_bytes'],r['name']))
    chosen=[];ms=set()
    for r in rows:
        if r['active_limit'] not in ms:chosen.append(r);ms.add(r['active_limit'])
    for r in rows:
        if r not in chosen:chosen.append(r)
    write_json(Path(out)/'proposals.json',{'rows':chosen,'log':log,'generation_seconds':time.perf_counter()-t,'global_window':bound(ix,n,pre)})

def solve(graph,n,scene,out,budget=600,profile='full'):
    graph=Path(graph).resolve();out=Path(out).resolve();t=time.perf_counter()
    if n<1 or scene not in ('A','B','L2') or budget<=0:raise ValueError('Invalid input')
    if out.exists() and any(out.iterdir()):raise FileExistsError('Output must be new or empty')
    out.mkdir(parents=True,exist_ok=True);remaining=lambda:max(0,budget-(time.perf_counter()-t))
    report={'protocol':'R10.1','case':graph.stem,'scene':scene,'cores':n,'profile':profile,'budget':budget,'status':'running',
      'graph_sha256':sha(graph),'config_sha256':sha(ROOT/'official/data/config.txt'),'official_source_sha256':source_hash(ROOT/'official'),
      'sources':{str(p.relative_to(ROOT)):sha(p) for d in ('src','round6_src','round7_src','round10_src') for p in sorted((ROOT/d).glob('*.py'))},
      'environment':{'python':sys.version,'platform':platform.platform()},'stages':[],'input_policy':'original graph/config/code only; no historical winners'}
    write_json(out/'report.json',report)
    cmd=[sys.executable,'-S',str(ROOT/'round7_src/solve_round7.py'),str(graph),'-n',str(n),'--scene',scene,'--budget',str(max(.1,remaining()-.5)),'--out',str(out/'r7')]
    report['control_process']=execute(cmd,max(.1,remaining()),out/'r7.log')
    rp=out/'r7/report.json'
    if not rp.exists() or json.loads(rp.read_text()).get('status')!='ok':
        report.update(status='no_valid_control',wall_seconds=time.perf_counter()-t);write_json(out/'report.json',report);return report
    control=json.loads(rp.read_text());best={**control['selected'],'plan':out/'r7'/control['selected']['plan'],'raw':out/'r7'/control['selected']['raw']}
    snap=lambda x:{k:str(v.relative_to(out)) if isinstance(v,Path) else v for k,v in x.items()}
    report['control']=snap(best);report['after_components']=snap(best)
    seen=set()
    for pp in (out/'r7').rglob('*plan.json'):
        try:seen.add(semantic_hash(json.loads(pp.read_text())))
        except (KeyError,ValueError):pass
    seen.add(semantic_hash(json.loads(best['plan'].read_text())))
    ix=GraphIndex(json.loads(graph.read_text()));wb=bound(ix,n);report['global_window']=wb
    def evaluate(name,pp,stage,limit=30):
        nonlocal best
        if remaining()<.2:stage.append({'name':name,'status':'budget_exhausted'});return
        meta_path=out/'extra'/(name+'.json');meta_path.parent.mkdir(exist_ok=True)
        row=run_job({'graph':str(graph),'plan':str(pp),'mode':scene,'variant':name,'cores':n,'output':str(meta_path)},ROOT/'official',min(limit,remaining()),False,report['official_source_sha256'],False)
        stage.append({'name':name,'status':row['status'],'metadata':str(meta_path.relative_to(out)),'makespan':row.get('makespan'),'wall_seconds':row['wall_seconds']})
        if row['status']=='ok':
            if row['makespan']<wb['window_lower_bound']:raise AssertionError('Global window bound violated')
            candidate={'name':name,'makespan':row['makespan'],'added_copy_bytes':row['data_movement_bytes']['added_copy_bytes'],'plan':pp,'raw':meta_path.parent/row['official_result_file']}
            if (candidate['makespan'],candidate['added_copy_bytes'],name)<(best['makespan'],best['added_copy_bytes'],best['name']):best=candidate
    if profile!='control' and best['makespan']>1.03*wb['window_lower_bound'] and remaining()>1:
        d=out/'families';d.mkdir(exist_ok=True)
        cmd=[sys.executable,'-S',__file__,'--generate',str(graph),'-n',str(n),'--scene',scene,'--incumbent',str(best['makespan']),'--out',str(d)]
        st={'kind':'component_family_closure','evaluations':[]};st['generation_process']=execute(cmd,min(40,remaining()),d/'generation.log')
        if st['generation_process']['status']=='ok' and (d/'proposals.json').exists():
            proposals=json.loads((d/'proposals.json').read_text());attempts=0
            for item in proposals['rows']:
                if attempts>=6:break
                if item['semantic_sha'] in seen:continue
                seen.add(item['semantic_sha'])
                if item['bound']['lower_bound_cycles']>best['makespan']:
                    st['evaluations'].append({'name':item['name'],'status':'bound_pruned'});continue
                evaluate(item['name'],d/item['plan_file'],st['evaluations']);attempts+=1
        report['stages'].append(st);report['after_components']=snap(best)
    if profile=='full' and scene=='L2' and remaining()>3 and best['makespan']>1.03*wb['window_lower_bound']:
        # This independent B solve is charged to the same request, never cached from another run.
        d=out/'B_reference';limit=min(180,max(.1,remaining()-min(40,remaining()/3)))
        cmd=[sys.executable,'-S',str(ROOT/'round7_src/solve_round7.py'),str(graph),'-n',str(n),'--scene','B','--budget',str(limit),'--out',str(d)]
        st={'kind':'same_core_B_plan_under_L2','evaluations':[],'generation_process':execute(cmd,limit+.1,out/'B_reference.log')}
        rp=d/'report.json'
        if rp.exists() and json.loads(rp.read_text()).get('status')=='ok':
            pp=d/'selected_plan.json';fp=semantic_hash(json.loads(pp.read_text()))
            if fp not in seen:evaluate('B_plan_evaluated_in_L2',pp,st['evaluations'],40)
            else:st['evaluations'].append({'name':'B_plan_evaluated_in_L2','status':'duplicate_plan'})
        report['stages'].append(st)
    shutil.copy2(best['plan'],out/'selected_plan.json');report['selected']=snap(best)
    report.update(status='ok',selected_plan_sha256=sha(out/'selected_plan.json'),selected_raw_sha256=sha(best['raw']),wall_seconds=time.perf_counter()-t)
    report['budget_exceeded']=report['wall_seconds']>budget;write_json(out/'report.json',report);return report

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('graph',type=Path);ap.add_argument('-n','--cores',type=int,required=True);ap.add_argument('--scene',choices=['A','B','L2'],required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--budget',type=float,default=600);ap.add_argument('--profile',choices=['control','component','full'],default='full');ap.add_argument('--generate',action='store_true');ap.add_argument('--incumbent',type=int)
    a=ap.parse_args()
    if a.generate:generate(a.graph,a.cores,a.scene,a.incumbent,a.out)
    else:
        r=solve(a.graph,a.cores,a.scene,a.out,a.budget,a.profile);print(json.dumps({k:r.get(k) for k in ('status','case','scene','control','selected','wall_seconds')},ensure_ascii=False))
        raise SystemExit(0 if r['status']=='ok' else 2)
