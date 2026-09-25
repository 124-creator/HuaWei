from __future__ import annotations
from task_frontier import *
import argparse,json,time,hashlib

def generate(ix,n,plan,raw,kind):
 rows=[];seen=set()
 if kind=='bands':
  for width in (4,8,2,16):
   groups,meta=band_components(ix,width,2048);p,pm=list_assign(ix,groups,n)
   rows.append((f'band{width}',p,{**meta,**pm}))
 elif kind=='reassign':
  ids=sorted(set(plan['node_to_subgraph'].values()));of={s:i for i,s in enumerate(ids)};groups=[[] for _ in ids]
  for u,s in plan['node_to_subgraph'].items():groups[of[s]].append(int(u))
  observed={t['task_id']:t['duration'] for c in raw['per_core_timeline'] for t in c['tasks']}
  for mode in ('local','observed'):
   durations={of[s]:(raw['step3_by_task'][str(s)]['local_makespan'] if mode=='local' else observed[s]) for s in ids}
   p,meta=list_assign(ix,groups,n,durations=durations)
   rows.append((f'reassign_{mode}',p,{**meta,'construction':'fixed membership, Task-list assignment','duration_source':mode,'counterfactual_exact':False}))
 else:raise ValueError('Unknown stage')
 output=[]
 for name,p,m in rows:
  text=json.dumps(p,sort_keys=True);fp=hashlib.sha256(text.encode()).hexdigest()
  if fp in seen:continue
  seen.add(fp);m.update(bound=task_lower_bound(ix,p),name=name,plan_fingerprint=fp);output.append((name,p,m))
 return output

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--raw',type=Path,required=True)
 ap.add_argument('--kind',choices=['bands','reassign'],required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();start=time.perf_counter()
 ix=GraphIndex(json.loads(a.graph.read_text()));plan=json.loads(a.plan.read_text());raw=json.loads(a.raw.read_text());a.out.mkdir(parents=True,exist_ok=True)
 rows=[]
 for name,p,m in generate(ix,len(plan['core_schedules']),plan,raw,a.kind):
  dest=a.out/f'{name}_plan.json';dest.write_text(json.dumps(p,sort_keys=True),encoding='utf-8');rows.append({'name':name,'plan_file':dest.name,'meta':m})
 (a.out/'proposals.json').write_text(json.dumps({'rows':rows,'generation_seconds':time.perf_counter()-start},indent=2),encoding='utf-8')
if __name__=='__main__':main()
