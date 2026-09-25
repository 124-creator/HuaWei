"""Audit archived stage-2 evidence and assemble four-core development comparisons.

No evaluation is rerun, and no official inputs or outputs are edited. The audit
checks hashes, byte accounting, capacities, cache fractions, and proved resource
bounds against recorded successful official evaluations.
"""
from __future__ import annotations
import hashlib,json,shutil,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'official/code'))
from solver import GraphIndex
from bounds import candidate_lower_bound,global_compute_lower_bound
from traffic_model import predict_partition_bytes
from evaluation_validation import read_evaluation_config
from run_experiments import source_hash


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def rel(path):return str(path.relative_to(ROOT))
def records(folder):
    for p in folder.rglob('*.json'):
        if p.name.endswith(('.official.json','.trace.json','.selection.json')):continue
        d=json.loads(p.read_text(encoding='utf-8'))
        if isinstance(d,dict) and all(k in d for k in ('status','mode','graph_sha256')):
            d=dict(d);d['_record_file']=rel(p);yield p,d


def main():
    cfg=read_evaluation_config(str(ROOT/'official/data/config.txt'));config_hash=sha(ROOT/'official/data/config.txt')
    code_hash=source_hash(ROOT/'official');worker_hash=sha(ROOT/'src/eval_worker.py')
    plans={}
    for folder in ('plans','prior_evidence/control_plans','results'):
        for p in (ROOT/folder).rglob('*.json'):
            if folder=='results' and not (p.name.endswith('_plan.json') or p.name=='plan.json'):continue
            d=json.loads(p.read_text(encoding='utf-8'))
            if isinstance(d,dict) and set(d)=={'node_to_subgraph','core_schedules'}:plans[sha(p)]=(p,d)
    all_records=list(records(ROOT/'results'))+list(records(ROOT/'prior_evidence/controls'))+list(records(ROOT/'prior_evidence/singlecore_metadata'))
    indices={};checks=[];counts=Counter();prediction_n=0;bound_n=0;missing_plans=[]
    for path,row in all_records:
        counts[row['status']]+=1
        if row['status']!='ok':continue
        case=row['case'];gp=ROOT/'official/data'/f'{case}.json'
        assert sha(gp)==row['graph_sha256'],('graph',path)
        assert config_hash==row['config_sha256'],('config',path)
        assert code_hash==row['official_code_sha256'],('official code',path)
        assert worker_hash==row['worker_sha256'],('worker',path)
        rp=path.with_name(row['official_result_file']);assert sha(rp)==row['official_result_sha256'],('raw',path)
        raw=json.loads(rp.read_text(encoding='utf-8'));assert raw['makespan']==row['makespan'],('time',path)
        m=row['data_movement_bytes'];assert m['scheduled_copy_bytes']==m['original_graph_copy_bytes']+m['added_copy_bytes']
        assert m['added_copy_bytes']==m['partition_added_copy_bytes']+m['spill_added_copy_bytes']
        for mem in (row.get('memory_peak_by_core') or {}).values():
            for kind,cap in cfg['capacity'].items():assert mem[kind]<=cap,('capacity',path)
        cache=row.get('cache_stats')
        if cache:
            den=cache['hit_bytes']+cache['miss_bytes'];rate=cache['hit_bytes']/den if den else 0
            assert abs(rate-cache['hit_rate'])<1e-12,('cache',path)
        item={'record':rel(path),'status':'pass'}
        if row['mode']!='single':
            ph=row['plan_sha256']
            if ph not in plans:missing_plans.append(rel(path));continue
            pp,plan=plans[ph]
            if case not in indices:indices[case]=GraphIndex(json.loads(gp.read_text(encoding='utf-8')))
            ix=indices[case];b=candidate_lower_bound(ix,plan,row['mode'],cfg['bandwidth'])
            assert b['pre_spill_traffic']['predicted_partition_added_copy_bytes']==m['partition_added_copy_bytes'],('traffic',path)
            assert b['lower_bound_cycles']<=row['makespan'],('bound',path,b['lower_bound_cycles'],row['makespan'])
            gb=global_compute_lower_bound(ix,row['num_cores']);assert gb['global_lower_bound_cycles']<=row['makespan']
            item.update(plan=rel(pp),candidate_lower_bound_cycles=b['lower_bound_cycles'],global_lower_bound_cycles=gb['global_lower_bound_cycles'])
            prediction_n+=1;bound_n+=1
        checks.append(item)
    assert not missing_plans,missing_plans
    # Verify every original source file against the initial ZIP comparison.
    originals=json.loads((ROOT/'reports/original_source_audit.json').read_text())
    for item in originals['files']:assert item['unchanged'] and sha(ROOT/'official'/item['path'])==item['sha256']
    main_batches={name:list(records(ROOT/'results'/name)) for name in ('screen','frontier','affinity','migration')}
    main_counts={name:dict(Counter(d['status'] for _,d in rs)) for name,rs in main_batches.items()}
    report={'original_files_unchanged':len(originals['files']),'records_by_status_including_prior_and_cli':dict(counts),
            'successful_records_audited':len(checks),'pre_spill_predictions_and_bounds_checked':prediction_n,
            'distinct_plan_hashes_available':len(plans),'main_development_batches':main_counts,
            'missing_plan_evidence':missing_plans,'checks':checks,
            'scope':'Recorded simulations and arithmetic/hash checks. Includes inherited controls and duplicate smoke results. Not 100-case performance completion or hardware measurements.'}
    write(ROOT/'reports/evidence_audit_stage2.json',report)
    # Controlled comparisons: prior stage + four planned development batches only.
    prior=[d for _,d in records(ROOT/'prior_evidence/controls') if d['status']=='ok']
    new=[d for rs in main_batches.values() for _,d in rs if d['status']=='ok']
    cases=sorted({d['case'] for d in prior+new});summary=[]
    key=lambda d:(d['makespan'],d['data_movement_bytes']['added_copy_bytes'],d['variant'],d['_record_file'])
    selected=ROOT/'selected_plans';selected.mkdir(exist_ok=True)
    for case in cases:
        old={};best={}
        for mode in ('A','B','L2'):
            olds=[d for d in prior if d['case']==case and d['mode']==mode];alls=olds+[d for d in new if d['case']==case and d['mode']==mode]
            old[mode]=min(olds,key=key) if olds else None;best[mode]=min(alls,key=key) if alls else None
            if best[mode]:shutil.copy2(plans[best[mode]['plan_sha256']][0],selected/f'{case}_n4_{mode}.json')
        bp=best['B'];same=[d for d in prior+new if d['case']==case and d['mode']=='L2' and bp and d['plan_sha256']==bp['plan_sha256']]
        if bp:
            ix=indices[case];gb=global_compute_lower_bound(ix,4);bound=gb['global_lower_bound_cycles'];gap=bp['makespan']/bound-1 if bound else None
        else:gb={};gap=None
        def compact(d):
            if not d:return None
            return {k:d[k] for k in ('makespan','variant','plan_sha256','data_movement_bytes','cache_stats','_record_file')}
        row={'case':case,'old':{m:compact(old[m]) for m in old},'best':{m:compact(best[m]) for m in best},
             'same_best_B_plan_L2':compact(min(same,key=key)) if same else None,'global_compute_bound':gb,
             'B_optimality_gap_upper_bound':gap,'B_time_reduction_fraction':(old['B']['makespan']-best['B']['makespan'])/old['B']['makespan'] if old['B'] and best['B'] else None}
        summary.append(row)
    write(ROOT/'reports/selected_summary_stage2.json',summary)
    # Original 100 single-core metadata, overlaid only by newly completed success.
    bases={d['case']:d for _,d in records(ROOT/'prior_evidence/singlecore_metadata')}
    newbases=[d for _,d in records(ROOT/'results') if d['mode']=='single' and d['status']=='ok']
    for d in newbases:bases[d['case']]=d
    missing=sorted(c for c,d in bases.items() if d['status']!='ok')
    write(ROOT/'reports/baseline_coverage_stage2.json',{'cases':len(bases),'successful':len(bases)-len(missing),'missing':missing,'rows':[bases[c] for c in sorted(bases)],'note':'Retried failures do not replace successful fixed baselines. Missing entries are not imputed as 1x speedup.'})
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))
    print('BASELINES',len(bases)-len(missing),'/',len(bases))
    for r in summary:print(r['case'],{m:(r['old'][m]['makespan'] if r['old'][m] else None,r['best'][m]['makespan'] if r['best'][m] else None) for m in ('A','B','L2')},r['B_time_reduction_fraction'])

if __name__=='__main__':main()
