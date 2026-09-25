"""Controlled re-evaluation of three previously declared B5 failure cases.
No new solver is selected in this script; each intervention is reported separately.
"""
from pathlib import Path
import argparse, json, sys, time
ROOT=Path(__file__).resolve().parents[1]
for d in ('official/code','src','round6_src','round7_src','round10_src'):
    sys.path.insert(0,str(ROOT/d))
from solver import GraphIndex
from optimizer_v2 import check_plan
from heft_baseline import heft
from solve_round6 import execute,write_json,sha
from run_experiments import run_job,source_hash

def chain_plan(blocks,owners,order,n):
    p={'node_to_subgraph':{str(u):b for b,g in enumerate(blocks) for u in g},'core_schedules':[[] for _ in range(n)]}
    for b in order:p['core_schedules'][owners[b]].append(b)
    return p

def op_cores(p):
    co={b:k for k,seq in enumerate(p['core_schedules']) for b in seq}
    return {int(u):co[b] for u,b in p['node_to_subgraph'].items()}

def describe(ix,p):
    owners=op_cores(p);loads=[{'PIPE_M':0,'PIPE_V':0} for _ in p['core_schedules']]
    for u,k in owners.items(): loads[k][ix.ops[u]['pipe']]+=ix.ops[u]['cycles']
    return {'subgraphs':len(set(p['node_to_subgraph'].values())),'active_cores':len(set(owners.values())), 'pipe_loads':loads}

def run(case):
    g=ROOT/'official/data'/(case+'.json');out=ROOT/'round11_results/diagnostic'/case
    if out.exists() and any(out.iterdir()):raise FileExistsError(out)
    out.mkdir(parents=True)
    t=time.perf_counter();cmd=[sys.executable,'-S',str(ROOT/'round10_src/solve_round10.py'),str(g),'-n','5','--scene','B','--budget','600','--out',str(out/'control')]
    proc=execute(cmd,602,out/'control.log');write_json(out/'control_process.json',proc)
    r=json.loads((out/'control/report.json').read_text());assert r['status']=='ok'
    p=json.loads((out/'control/selected_plan.json').read_text());raw=json.loads((out/'control'/r['selected']['raw']).read_text())
    ix=GraphIndex(json.loads(g.read_text()));blocks,bo,pred,succ=ix.chain_blocks();block_topo=ix.topological(list(pred),pred,succ)
    cp=op_cores(p)
    for b,gp in enumerate(blocks):assert len({cp[u] for u in gp})==1,('R10 split a chain block',b)
    cb={b:cp[gp[0]] for b,gp in enumerate(blocks)}
    hp,hm=heft(ix,5,'B');check_plan(ix,hp);hpowners=op_cores(hp);hb={b:hpowners[gp[0]] for b,gp in enumerate(blocks)}
    predh={b:set(v) for b,v in pred.items()};such={b:set(v) for b,v in succ.items()}
    for seq in hp['core_schedules']:
        for a,b in zip(seq,seq[1:]):predh[b].add(a);such[a].add(b)
    common=ix.topological(list(predh),predh,such)
    assert chain_plan(blocks,hb,common,5)==hp
    base_order=[];rank={b:i for i,b in enumerate(block_topo)}
    for seq in p['core_schedules']:
        for sg in seq:
            base_order.extend(sorted({bo[int(u)] for u,s in p['node_to_subgraph'].items() if s==sg},key=rank.get))
    assert len(base_order)==len(set(base_order))==len(blocks)
    depth={}
    for b in block_topo:depth[b]=max((depth[a]+1 for a in pred[b]),default=0)
    layers=sorted(block_topo,key=lambda b:(depth[b],rank[b]))
    proposals=[
        ('H_original',hp,'HEFT-style chain partition / placement / insertion order'),
        ('C_chain_original_order',chain_plan(blocks,cb,base_order,5),'R10 owners and group order retained; only refine each original subgraph into whole chains'),
        ('C_chain_common_order',chain_plan(blocks,cb,common,5),'R10 owners; common chain partition and common global topological sequence'),
        ('H_chain_layer_order',chain_plan(blocks,hb,layers,5),'HEFT owners and chain partition fixed; only core order changes to depth layers'),
    ]
    groups={};m={};qs=[[] for _ in range(5)]
    for b in layers:
        key=(depth[b],hb[b])
        if key not in groups:groups[key]=len(groups);qs[hb[b]].append(groups[key])
        for u in blocks[b]:m[str(u)]=groups[key]
    proposals.append(('H_layer_groups',{'node_to_subgraph':m,'core_schedules':qs},'HEFT owners; groups merged by (depth,core), separately labelled organization intervention'))
    records=[{'variant':'R10_control','status':'ok','makespan':raw['makespan'],'data_movement_bytes':raw['data_movement_bytes'],**describe(ix,p),
              'plan':str((out/'control/selected_plan.json').relative_to(ROOT)),'raw':str((out/'control'/r['selected']['raw']).relative_to(ROOT)),
              'plan_sha':sha(out/'control/selected_plan.json'),'raw_sha':sha(out/'control'/r['selected']['raw'])}]
    official_hash=source_hash(ROOT/'official')
    for name,q,desc in proposals:
        qd=out/name;qd.mkdir();pp=qd/'plan.json';write_json(pp,q)
        try:check_plan(ix,q)
        except Exception as exc:
            records.append({'variant':name,'status':'structural_error','error':repr(exc),'intervention':desc});continue
        row=run_job({'graph':str(g),'plan':str(pp),'mode':'B','variant':name,'cores':5,'output':str(qd/'meta.json')},ROOT/'official',120,False,official_hash,False)
        rec={'variant':name,'status':row['status'],'intervention':desc,'plan':str(pp.relative_to(ROOT)),**describe(ix,q),'plan_sha':sha(pp),'wall_seconds':row['wall_seconds']}
        if row['status']=='ok':
            rp=qd/row['official_result_file'];rr=json.loads(rp.read_text());rec.update(makespan=rr['makespan'],data_movement_bytes=rr['data_movement_bytes'],raw=str(rp.relative_to(ROOT)),raw_sha=sha(rp))
        records.append(rec)
        write_json(out/'summary.json',{'case':case,'scene':'B','cores':5,'records':records,'complete':False})
    for rec in records:
        if rec['status']!='ok' or rec['variant'] not in ('R10_control','H_original','C_chain_common_order','H_chain_layer_order'):continue
        ad=out/(rec['variant']+'_attribution.json')
        cmd=[sys.executable,'-S',str(ROOT/'src/trace_attribution.py'),'--official',str(ROOT/'official'),'--graph',str(g),'--plan',str(ROOT/rec['plan']),'--result',str(ROOT/rec['raw']),'-o',str(ad)]
        pr=execute(cmd,90,out/(rec['variant']+'_attribution.log'));rec['attribution_process']=pr
        if pr['status']=='ok':
            ar=json.loads(ad.read_text());rec['critical_chain']=ar['critical_chain_duration_decomposition'];rec['critical_edge_counts']=ar['critical_chain_edge_counts'];rec['all_start_times_reconstructed']=ar['all_start_times_reconstructed']
    result={'case':case,'scene':'B','cores':5,'records':records,'complete':True,'wall_seconds':time.perf_counter()-t,'controlled_comparisons':[
      'H_original vs H_chain_layer_order: identical chain members and core ownership; order only',
      'C_chain_original_order vs C_chain_common_order: identical chain members and R10 ownership; order only',
      'C_chain_common_order vs H_original: same chain members and a common global topological priority, different owners/projections',
      'H_chain_layer_order vs H_layer_groups: identical owners and depth priority; subgraph aggregation changes']}
    write_json(out/'summary.json',result)
    print(json.dumps({'case':case,'results':[(r['variant'],r.get('makespan'),r['status']) for r in records]},ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);a=ap.parse_args();run(a.case)
