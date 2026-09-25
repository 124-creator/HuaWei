"""Package code/diagnostics separately from the larger resumable evidence checkpoint."""
from __future__ import annotations
import json,zipfile,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(folder,exclude=()):
 return {p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__'not in p.parts and not any(p.name.endswith(x)for x in exclude)}
def add_reference(s,path):
 p=Path(path);p=p if p.is_absolute()else ROOT/p
 if p.exists() and p.is_file():s.add(p)
 return p

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=ROOT.parent);args=parser.parse_args();DEST=args.output_dir;DEST.mkdir(parents=True,exist_ok=True)
 code=set();evidence=set()
 for f in ['official','src','tests','stage3_selected','selected_plans']:code|=collect(f)
 for f in ['stage3_results/targeted','stage3_results/cache_timing','stage3_results/verification','stage3_results/trace','stage3_results/residency']:code|=collect(f)
 code={p for p in code if not p.name.endswith('_prepared.json')}
 # Necessary inherited control and baseline inventory references, without all old exploration.
 for name in ['reports/original_source_audit.json','reports/baseline_coverage_stage2.json','reports/selected_summary_stage2.json','README_STAGE3.md','第三轮报告.md']:
  add_reference(code,name)
 for f in ['stage3_reports']:
  for p in collect(f):
   if p.suffix=='.py' or p.name.endswith('_live.log') or p.name in ('audit_preflight.log',):continue
   code.add(p)
 for p in (ROOT/'stage3_results/trace').glob('*.json'):
  if p.name.endswith(('.perfetto.json','_prepared.json')):continue
  d=json.loads(p.read_text())
  for path in d.get('source_files',{}).values():
   q=add_reference(code,path)
   if q.name.endswith('.official.json'):add_reference(code,str(q).replace('.official.json','.json'))
 for r in json.loads((ROOT/'stage3_reports/residency_control.json').read_text()):
  for key in ('plan','record'):
   q=add_reference(code,r[key])
   if key=='record':meta=json.loads(q.read_text());add_reference(code,q.with_name(meta['official_result_file']))
 # Full checkpoint and all official fixed baselines referenced by final coverage.
 for f in ['stage3_results/fullgrid','stage3_results/startup_check_normal','stage3_results/baseline']:
  evidence|=collect(f)
 for r in json.loads((ROOT/'stage3_reports/baseline_coverage_stage3.json').read_text())['rows']:
  q=add_reference(evidence,r['_record_file']);add_reference(evidence,q.with_name(r['official_result_file']))
 for name in ['stage3_reports/frozen_coverage.json','stage3_reports/baseline_coverage_stage3.json','stage3_reports/evidence_audit_stage3.json','stage3_reports/fixed_plan_cache_controls.json','README_STAGE3.md','第三轮报告.md']:add_reference(evidence,name)
 outputs=[]
 for label,paths in [('NPU_第三轮代码与Trace诊断包.zip',code),('NPU_第三轮冻结评测检查点与原始结果.zip',evidence)]:
  target=DEST/label;manifest=[]
  with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
   for p in sorted(paths):
    arc='npu_stage3/'+str(p.relative_to(ROOT));z.write(p,arc);manifest.append({'path':arc,'bytes':p.stat().st_size,'sha256':sha(p)})
   z.writestr('npu_stage3/PACKAGE_'+('CODE'if paths is code else 'EVIDENCE')+'_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
  outputs.append({'path':str(target),'bytes':target.stat().st_size,'sha256':sha(target),'files':len(paths)})
  print(json.dumps(outputs[-1],ensure_ascii=False),flush=True)
 (ROOT/'stage3_reports/package_outputs.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2));print('done',flush=True)
if __name__=='__main__':main()
