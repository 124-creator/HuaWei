"""Isolated same-limit comparison of original and indexed candidate construction."""
from pathlib import Path
import sys,json,argparse,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'round11_src'))
from runtime import execute,write_json,sha

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--timeout',type=float,default=30)
 ap.add_argument('--cases',nargs='*',default=['all']);ap.add_argument('--cores',type=int,default=5);ap.add_argument('--scene',default='B');a=ap.parse_args()
 paths=sorted((ROOT/'official/data').glob('case_*.json'))
 if a.cases!=['all']:paths=[p for p in paths if p.stem in a.cases]
 if a.out.exists() and any(a.out.iterdir()):raise FileExistsError('Fresh output required')
 a.out.mkdir(parents=True,exist_ok=True)
 write_json(a.out/'protocol.json',{'scope':'generation only; not solve wall or score','timeout_each':a.timeout,'cores':a.cores,'scene':a.scene,'cases':[p.stem for p in paths],'frozen_files':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'round10_src/heft_baseline.py',ROOT/'round12_src/fast_calendar.py',ROOT/'round12_src/fast_insertion.py']}})
 rows=[];begin=time.perf_counter()
 for i,g in enumerate(paths):
  row={'case':g.stem,'scene':a.scene,'cores':a.cores,'order':['original','fast'] if i%2==0 else ['fast','original']}
  for name in row['order']:
   folder=a.out/g.stem/name
   cmd=[sys.executable,'-S',str(ROOT/'round12_src/fast_insertion.py'),str(g),'-n',str(a.cores),'--scene',a.scene,'--out',str(folder)]
   if name=='original':cmd.append('--reference')
   status=execute(cmd,a.timeout,folder/'driver.log');row[name]=status
   if status['status']=='ok':row[name]['generation']=json.loads((folder/'generation.json').read_text())
  row['same_plan']=None
  if all(row[k]['status']=='ok' for k in ['original','fast']):
   row['same_plan']=row['original']['generation']['plan_sha256']==row['fast']['generation']['plan_sha256']
   if not row['same_plan']:raise AssertionError(f'Candidate drift {g.stem}')
  rows.append(row);write_json(a.out/'summary.json',{'declared':len(paths),'finished':len(rows),'complete':len(rows)==len(paths),'wall_seconds':time.perf_counter()-begin,'rows':rows})
  print(g.stem, row['original']['status'],round(row['original']['wall_seconds'],3),row['fast']['status'],round(row['fast']['wall_seconds'],3),'same',row['same_plan'],flush=True)
if __name__=='__main__':main()
