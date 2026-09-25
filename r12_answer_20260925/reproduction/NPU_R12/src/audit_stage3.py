"""Audit a stopped stage-3 run and write coverage without incomplete averages."""
from __future__ import annotations
import collections,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'official/code'))
from solver import GraphIndex
from bounds import candidate_lower_bound
from run_experiments import source_hash

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def rel(p):return str(Path(p).relative_to(ROOT))

def main():
 report=ROOT/'stage3_reports';out=ROOT/'stage3_results';checks=[];counts=collections.Counter();plans={};idx={};bounds_checked=0;bounds_reused=0
 oldpath=ROOT/'stage3_reports/evidence_audit_stage3.json'
 prior_checks={x['metadata']:x for x in read(oldpath).get('checks',[])} if oldpath.exists() else {}
 originals=read(ROOT/'reports/original_source_audit.json')['files']
 for x in originals:assert sha(ROOT/'official'/x['path'])==x['sha256']
 prot=read(out/'fullgrid/protocol.json')
 for name,h in prot['solver_hashes'].items():assert sha(ROOT/'src'/name)==h
 snapshot=list(out.rglob('*.json'));status_snapshot={str(p):read(p) for p in snapshot if p.name=='status.json'}
 for p in snapshot:
  if p.name=='plan.json' or p.name.endswith('_plan.json') or p.parent.name=='one_core_plans':
   x=read(p)
   if isinstance(x,dict) and set(x)=={'node_to_subgraph','core_schedules'}:plans[sha(p)]=(p,x)
 cfg=sha(ROOT/'official/data/config.txt');code=source_hash(ROOT/'official');success=[]
 for p in snapshot:
  if p.name.endswith(('.official.json','.trace.json','.perfetto.json','.selection.json')):continue
  if p.parent.name=='trace':continue
  d=read(p)
  if not isinstance(d,dict) or not all(k in d for k in ('status','mode','graph_sha256')):continue
  counts[d['status']]+=1
  if d['status']!='ok':continue
  rp=p.with_name(d['official_result_file']);assert sha(rp)==d['official_result_sha256'],str(p)
  raw=read(rp);gp=ROOT/'official/data'/f"{d['case']}.json";assert sha(gp)==d['graph_sha256'] and cfg==d['config_sha256']
  if 'official_code_sha256' in d:assert code==d['official_code_sha256']
  assert raw['makespan']==d['makespan'];assert max(o['end'] for c in raw['per_core_timeline'] for o in c['ops'])==raw['makespan']
  m=raw['data_movement_bytes'];assert m==d['data_movement_bytes'];assert m['original_graph_copy_bytes']+m['added_copy_bytes']==m['scheduled_copy_bytes'];assert m['partition_added_copy_bytes']+m['spill_added_copy_bytes']==m['added_copy_bytes']
  for mem in (raw.get('memory_peak_by_core')or{}).values():
   for k,cap in [('L1',524288),('UB',131072)]:assert mem[k]<=cap
  if raw.get('cache_stats'):
   c=raw['cache_stats'];assert abs(c['hit_rate']-c['hit_bytes']/(c['hit_bytes']+c['miss_bytes']))<1e-12
  item={'metadata':rel(p),'raw_result':rel(rp),'raw_sha256':sha(rp),'makespan':d['makespan'],'status':'pass'}
  if d['mode']!='single':
   pp,plan=plans[d['plan_sha256']];case=d['case']
   old=prior_checks.get(rel(p),{})
   if old.get('raw_sha256')==sha(rp) and old.get('plan')==rel(pp) and old.get('makespan')==d['makespan'] and 'lower_bound'in old:
    lb=old['lower_bound'];bounds_reused+=1
   else:
    if case not in idx:idx[case]=GraphIndex(read(gp))
    b=candidate_lower_bound(idx[case],plan,d['mode'],60);lb=b['lower_bound_cycles'];assert b['pre_spill_traffic']['predicted_partition_added_copy_bytes']==m['partition_added_copy_bytes']
   assert lb<=d['makespan']
   item.update(plan=rel(pp),lower_bound=lb);bounds_checked+=1
  checks.append(item);success.append((p,d))
 # Inherited fixed baselines, each raw file explicitly checked.
 baseline={}
 for row in read(ROOT/'reports/baseline_coverage_stage2.json')['rows']:
  if row['status']!='ok':continue
  p=ROOT/row['_record_file'];r=p.with_name(row['official_result_file']);assert sha(r)==row['official_result_sha256'];assert read(r)['makespan']==row['makespan'];baseline[row['case']]=row
 for p,d in success:
  if d['mode']=='single':
   if d['case'] in baseline:assert baseline[d['case']]['makespan']==d['makespan']
   baseline[d['case']]={**d,'_record_file':rel(p)}
 missing=[f'case_{i:03d}' for i in range(1,101) if f'case_{i:03d}' not in baseline]
 write(report/'baseline_coverage_stage3.json',{'successful':len(baseline),'missing':missing,'rows':[baseline[c] for c in sorted(baseline)]})
 # Official declared matrix, no missing-result imputation.
 manifest=read(out/'fullgrid/matrix_manifest.json');matrix=[];cells={};bycase=collections.Counter();bysetting=collections.defaultdict(collections.Counter)
 for j in manifest:
  cell=out/'fullgrid'/j['id'];st=cell/'status.json'
  row={k:j[k] for k in ('id','case','cores','scene')};s=status_snapshot.get(str(st),{'status':'pending'});row.update(status=s['status'])
  if s['status']=='ok':
   result=ROOT/j['result'];assert sha(result)==s['result_sha256'];d=read(result)
   if j['cores']==1:metapath=result;meta=d;pp=out/'fullgrid/one_core_plans'/f"{j['case']}.json"
   else:
    pp=cell/'plan.json';assert sha(pp)==d['plan_sha256'];metapath=cell/'candidates'/f"{d['selected_variant']}_result.json";meta=read(metapath);assert meta['makespan']==d['makespan'] and meta['plan_sha256']==d['plan_sha256']
   row.update(makespan=d['makespan'],added_copy_bytes=meta['data_movement_bytes']['added_copy_bytes'],cache_stats=meta.get('cache_stats'),plan=rel(pp),plan_sha256=sha(pp),metadata=rel(metapath),raw=rel(metapath.with_name(meta['official_result_file'])),driver_wall_seconds=s['driver_wall_seconds'])
   bycase[j['case']]+=1;cells[(j['case'],j['cores'],j['scene'])]=row
   if j['case'] in baseline:row['fixed_singlecore_speedup']=baseline[j['case']]['makespan']/d['makespan']
  matrix.append(row);bysetting[f"{j['cores']}_{j['scene']}"][s['status']]+=1
 coverage={'total_cells':len(matrix),'counts':dict(collections.Counter(r['status'] for r in matrix)), 'cases_with_any_completed':len(bycase),'cases_with_all_14_completed':sum(v==14 for v in bycase.values()),'complete_cases':sorted(k for k,v in bycase.items() if v==14),'by_setting':{k:dict(v) for k,v in bysetting.items()},'formal_100_case_average_available':len(baseline)==100 and all(r['status']=='ok' for r in matrix),'sorting':'graph file size ascending; incomplete subset is not representative','rows':matrix}
 write(report/'frozen_coverage.json',coverage)
 # Same-plan control may be found in nonselected L2 candidates; do not confuse independent optima.
 fixed=[]
 for (case,n,scene),b in cells.items():
  if scene!='B' or (case,n,'L2') not in cells:continue
  lcell=out/'fullgrid'/f'{case}_n{n}_L2';available=[lcell/'evaluation.json'] if n==1 else list((lcell/'candidates').glob('*_result.json'))
  match=[]
  for p in available:
   d=read(p)
   if d.get('status')=='ok' and d.get('plan_sha256')==b['plan_sha256']:match.append((p,d))
  if not match:fixed.append({'case':case,'cores':n,'status':'same_B_plan_L2_not_evaluated'});continue
  p,d=match[0];fixed.append({'case':case,'cores':n,'status':'ok','plan_sha256':b['plan_sha256'],'B':b['makespan'],'same_plan_L2':d['makespan'],'ratio':b['makespan']/d['makespan'],'L2_metadata':rel(p)})
 write(report/'fixed_plan_cache_controls.json',{'rows':fixed,'counts':dict(collections.Counter(r['status'] for r in fixed))})
 # -S versus normal-site experiment: compare same case and plan, not just main score.
 startup=[]
 for p in (out/'startup_check_normal').glob('case_*/status.json'):
  st=read(p);other=out/'fullgrid'/p.parent.name/'status.json'
  if st.get('status')!='ok' or not other.exists() or read(other).get('status')!='ok':continue
  normal=p.parent/('evaluation.json' if '_n1_' in p.parent.name else 'plan.selection.json');optimized=other.parent/normal.name;a=read(normal);b=read(optimized)
  assert a['makespan']==b['makespan'];assert a.get('plan_sha256')==b.get('plan_sha256')
  startup.append({'cell':p.parent.name,'identical_selected_plan_and_makespan':True,'normal_driver_seconds':st['driver_wall_seconds'],'no_site_driver_seconds':read(other)['driver_wall_seconds']})
 write(report/'runtime_flag_check.json',startup)
 # Diagnostics all zero unexplained start residuals and critical sum equal T.
 traces=[]
 for p in (out/'trace').glob('*.json'):
  if p.name.endswith('.perfetto.json') or p.name.endswith('_prepared.json'):continue
  d=read(p)
  if not isinstance(d,dict) or 'critical_chain_duration_decomposition'not in d:continue
  assert not d['unexplained_start_lags'];assert sum(d['critical_chain_duration_decomposition'].values())==d['makespan']
  traces.append({'file':rel(p),'makespan':d['makespan'],'reconstructed_ops':d['operation_count'],'critical':d['critical_chain_duration_decomposition'],'fifo':{k:d['fifo'][k] for k in ('requests','bytes','eviction_count')}if 'fifo'in d else None})
 write(report/'trace_summary.json',traces)
 write(report/'evidence_audit_stage3.json',{'original_files_unchanged':len(originals),'records_by_status':dict(counts),'successful_official_records_audited':len(checks),'distinct_raw_hashes':len({r['raw_sha256']for r in checks}),'tensor_traffic_and_lower_bound_checks':bounds_checked,'immutable_checks_reused_from_this_turn':bounds_reused,'fixed_baselines':len(baseline),'missing_baselines':missing,'frozen_matrix':{k:v for k,v in coverage.items()if k!='rows'},'diagnostic_records':len(traces),'startup_matches':len(startup),'checks':checks,'scope':'All counts are recorded cells/evaluations, not independent algorithms or globally optimal solutions. Partial matrix receives no formal 100-case average.'})
 print(json.dumps({'baseline':len(baseline),'coverage':{k:v for k,v in coverage.items()if k not in ('rows','complete_cases','by_setting')},'evaluations_audited':len(checks),'traces':len(traces)},ensure_ascii=False))
if __name__=='__main__':main()
