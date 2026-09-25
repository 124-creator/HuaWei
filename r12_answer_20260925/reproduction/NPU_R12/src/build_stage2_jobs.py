"""Construct and log a fixed set of candidates; no evaluation-based retuning."""
from pathlib import Path
import argparse, hashlib, json, sys, time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'official/code'))
from solver import GraphIndex
from optimizer_v2 import build_candidates
from traffic_model import predict_partition_bytes

def main():
    p=argparse.ArgumentParser();p.add_argument('--cases',nargs='+',required=True)
    p.add_argument('--cores',nargs='+',type=int,default=[4]);p.add_argument('--scenes',nargs='+',default=['A','B'])
    p.add_argument('--name',default='screen');a=p.parse_args()
    plans=ROOT/'plans'/a.name;plans.mkdir(parents=True,exist_ok=True)
    jobs=[];manifest=[];begin=time.perf_counter()
    for case in a.cases:
        graph_path=ROOT/'official/data'/(case+'.json'); graph=json.loads(graph_path.read_text());ix=GraphIndex(graph)
        for n in a.cores:
            for scene in a.scenes:
                start=time.perf_counter(); variants=build_candidates(graph,n,scene,ROOT/'official',ix)
                seen={}
                for name,plan,meta in variants:
                    text=json.dumps(plan,sort_keys=True);sha=hashlib.sha256(text.encode()).hexdigest()
                    dest=plans/f'{case}_n{n}_{scene}_{name}.json'; dest.write_text(text)
                    row={'case':case,'cores':n,'scene':scene,'variant':name,'plan_sha256':sha,
                         'plan_file':str(dest.relative_to(ROOT)), 'meta':meta,
                         'traffic':predict_partition_bytes(graph,plan,scene)}
                    if sha in seen: row['duplicate_of']=seen[sha]
                    else:
                        seen[sha]=name
                        # Baseline variants are evaluated too, except big originals
                        # whose immutable first-stage results remain controls.
                        if name not in ('components','chainwave') or case not in ('case_014','case_016','case_085'):
                            modes=[scene] if scene=='A' else ['B','L2']
                            for mode in modes:
                                out=ROOT/'results'/a.name/f'{case}_n{n}_{scene}_{name}_{mode}.json'
                                jobs.append({'graph':str(graph_path),'plan':str(dest),'mode':mode,'variant':name,
                                             'cores':n,'output':str(out)})
                    manifest.append(row)
                print(case,n,scene,'candidates',len(variants),'unique',len(seen),'seconds',round(time.perf_counter()-start,3),flush=True)
    (ROOT/'reports'/(a.name+'_jobs.json')).write_text(json.dumps(jobs,indent=2))
    (ROOT/'reports'/(a.name+'_manifest.json')).write_text(json.dumps({'rows':manifest,'construction_wall_seconds':time.perf_counter()-begin},indent=2))
    print('jobs',len(jobs),flush=True)
if __name__=='__main__':main()
