from pathlib import Path
import json,sys,subprocess,time
ROOT=Path(__file__).resolve().parents[1];rows=[]
# Chosen before running these checks; not used to retune prototype constants.
for case,n,scene,gap in [('case_001',4,'B',0.03),('case_003',2,'A',0),('case_007',3,'B',0),('case_008',5,'L2',0)]:
 out=ROOT/'results/cli_checks'/(case+'_'+scene+'_plan.json');out.parent.mkdir(parents=True,exist_ok=True)
 cmd=[sys.executable,str(ROOT/'src/solve_case_v2.py'),str(ROOT/'official/data'/(case+'.json')),'--official',str(ROOT/'official'),'-n',str(n),'--scene',scene,'--budget','90','--per-eval-timeout','20','--relative-gap-stop',str(gap),'-o',str(out)]
 start=time.perf_counter()
 try:
  r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=110)
  out.with_suffix('.console.txt').write_text(r.stdout);rows.append({'case':case,'cores':n,'scene':scene,'returncode':r.returncode,'wall_seconds':time.perf_counter()-start})
 except subprocess.TimeoutExpired as exc: rows.append({'case':case,'status':'cli_timeout','wall_seconds':time.perf_counter()-start})
 (ROOT/'reports/cli_checks.json').write_text(json.dumps(rows,indent=2));print(rows[-1],flush=True)
