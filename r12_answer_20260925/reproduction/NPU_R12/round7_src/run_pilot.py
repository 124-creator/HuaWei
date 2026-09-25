from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import subprocess,sys,json,time
root=Path(__file__).resolve().parents[1]
cases=['case_005','case_006','case_010','case_016','case_044','case_046','case_086']
def run(c):
 with (root/'round7_reports'/f'pilot_{c}.log').open('w') as log:
  p=subprocess.run([sys.executable,'-S',str(root/'round7_src/pilot.py'),c],stdout=log,stderr=subprocess.STDOUT)
 return c,p.returncode
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(run,c) for c in cases]):print(f.result(),flush=True)
