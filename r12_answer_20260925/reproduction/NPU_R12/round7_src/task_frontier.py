"""A: closed-cone grouping, locality windows and Task-aware assignment.
All heuristics are proxies; only task_lower_bound is certified for the fixed plan.
"""
from __future__ import annotations
import sys, heapq
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for folder in ('src','official/code','round6_src'):
 p=str(ROOT/folder)
 if p not in sys.path:sys.path.insert(0,p)
from solver import GraphIndex
from optimizer_v2 import check_plan, canonicalize
from bounds import candidate_lower_bound

def task_features(ix,groups):
 owner={u:i for i,g in enumerate(groups) for u in g}
 if set(owner)!=set(ix.ids) or sum(map(len,groups))!=len(ix.ids):raise ValueError('Groups do not exactly cover operations')
 pred={i:set() for i in range(len(groups))};succ={i:set() for i in pred}
 reads=defaultdict(int);writes=defaultdict(int);weights={i:[0,0] for i in pred}
 rawops={o['id']:o for o in ix.graph['ops']};final=set()
 for e in ix.graph['edges']:
  if e['source'] in ix.tensors and e['target'] in rawops and rawops[e['target']]['op']=='COPY_OUT':final.add(e['source'])
 for t,tensor in ix.tensors.items():
  ps={owner[u] for u in ix.producers[t]};cs={owner[u] for u in ix.consumers[t]};s=tensor['size']
  for c in cs-ps:reads[c]+=s
  for p in ps:
   if t in final or not cs or cs-{p}:writes[p]+=s
   for c in cs-{p}:succ[p].add(c);pred[c].add(p)
 length={};internal_cp=defaultdict(int)
 for u in ix.topo:
  a=owner[u];o=ix.ops[u]
  if o['pipe']=='PIPE_M':weights[a][0]+=o['cycles']
  if o['pipe']=='PIPE_V':weights[a][1]+=o['cycles']
  length[u]=o['cycles']+max((length[v] for v in ix.pred[u] if owner[v]==a),default=0)
  internal_cp[a]=max(internal_cp[a],length[u])
 for u in ix.ids:
  a=owner[u]
  for v in ix.succ[u]:
   b=owner[v]
   if a!=b:succ[a].add(b);pred[b].add(a)
 topo=ix.topological(list(pred),pred,succ)
 return dict(owner=owner,pred=pred,succ=succ,topo=topo,reads=reads,writes=writes,weights=weights,internal_cp=internal_cp,groups=groups)

def duration_floor(f,i):return max(*f['weights'][i],f['internal_cp'][i],(f['reads'][i]+f['writes'][i]+59)//60)

def list_assign(ix,groups,n,io_factor=1.0,durations=None):
 """Ready-set bottom-level priority, full-Task activation gates, no global barrier.
 Append order follows a common topological order, so core queues cannot cycle.
 """
 f=task_features(ix,groups);pred=f['pred'];succ=f['succ']
 duration={i:max(*f['weights'][i],f['internal_cp'][i],io_factor*(f['reads'][i]+f['writes'][i])/60) for i in pred}
 if durations is not None:duration={i:max(duration_floor(f,i),durations[i]) for i in pred}
 tail={}
 for i in reversed(f['topo']):tail[i]=duration[i]+max((1000+tail[j] for j in succ[i]),default=0)
 degree={i:len(pred[i]) for i in pred}
 ready=[(-tail[i],-duration[i],i) for i,d in degree.items() if d==0];heapq.heapify(ready)
 finish={};owner={};loads=[0.0]*n;orders=[[] for _ in range(n)];mapping={}
 while ready:
  _,_,i=heapq.heappop(ready)
  def estimate(k):
   begin=max(loads[k]+(100 if orders[k] else 0),max((finish[j]+(1000 if owner[j]!=k else 0) for j in pred[i]),default=0))
   return begin+duration[i],begin
  k=min(range(n),key=lambda k:(estimate(k)[0],loads[k],k))
  finish[i],_=estimate(k);owner[i]=k;loads[k]=finish[i];orders[k].append(i)
  for u in groups[i]:mapping[str(u)]=i
  for j in sorted(succ[i]):
   degree[j]-=1
   if degree[j]==0:heapq.heappush(ready,(-tail[j],-duration[j],j))
 plan=canonicalize({'node_to_subgraph':mapping,'core_schedules':orders});check_plan(ix,plan)
 return plan,dict(task_count=len(groups),proxy_finish=max(loads,default=0),io_factor=io_factor,
  proxy_scope='Task duration proxy, not official Makespan; ignores spill and dynamic contention')

def chain_data(ix):
 blocks,bo,pred,succ=ix.chain_blocks();topo=ix.topological(list(pred),pred,succ);w={i:sum(ix.weight(b)) for i,b in enumerate(blocks)}
 return blocks,bo,pred,succ,topo,w

def closed_cones(ix,n,scale=.5,max_ops=2048):
 """All-predecessor closure. Absorb parent groups only if each has exactly this
 consumer and the whole sibling set fits the same work/size cap. Each contraction
 has source outdegree one. Never partially absorb a large sibling join.
 """
 blocks,bo,pred,succ,topo,w=chain_data(ix)
 parent=list(range(len(blocks)));members={i:list(b) for i,b in enumerate(blocks)}
 gp={i:set(p) for i,p in pred.items()};gs={i:set(s) for i,s in succ.items()};work=dict(w)
 target=max(1,scale*sum(w.values())/max(1,n))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 merged=0
 for b in topo:
  b=find(b);ps=set(gp[b])
  if not ps or any(gs[a]!={b} for a in ps):continue
  combined=work[b]+sum(work[a] for a in ps);count=len(members[b])+sum(len(members[a]) for a in ps)
  if combined>target or count>max_ops:continue
  newpred=set().union(*(gp[a] for a in ps))-ps-{b}
  for a in sorted(ps):
   members[b].extend(members.pop(a));work[b]+=work.pop(a);parent[a]=b
   for p in gp[a]:gs[p].discard(a);gs[p].add(b)
   gp.pop(a);gs.pop(a);merged+=1
  gp[b]=newpred
 return [members[i] for i in sorted(members)],dict(construction='closed predecessor cones',scale=scale,target_work=target,max_ops=max_ops,absorbed_chain_groups=merged)

def reverse_dfs_order(ix):
 blocks,bo,pred,succ,topo,w=chain_data(ix);tail={}
 for i in reversed(topo):tail[i]=w[i]+max((tail[j] for j in succ[i]),default=0)
 visited=set();order=[]
 for root in sorted((i for i in pred if not succ[i]),key=lambda i:(-w[i],i)):
  stack=[(root,False)]
  while stack:
   i,done=stack.pop()
   if done:
    if i not in visited:visited.add(i);order.append(i)
    continue
   if i in visited:continue
   stack.append((i,True))
   for p in sorted(pred[i],key=lambda p:(-tail[p],p),reverse=True):
    if p not in visited:stack.append((p,False))
 if len(order)!=len(blocks):raise ValueError('reverse DFS coverage')
 return blocks,order,w

def locality_windows(ix,n,scale=.5,max_ops=2048):
 """Consecutive intervals of a locality-preserving valid topological order.
 Quotient edges go forward; actual dependencies, not all windows, gate execution.
 """
 blocks,order,w=reverse_dfs_order(ix);target=max(1,scale*sum(w.values())/max(1,n));groups=[];current=[];weight=0
 for i in order:
  if current and (weight+w[i]>target or len(current)+len(blocks[i])>max_ops):groups.append(current);current=[];weight=0
  current.extend(blocks[i]);weight+=w[i]
 if current:groups.append(current)
 return groups,dict(construction='reverse-DFS locality windows',scale=scale,target_work=target,max_ops=max_ops)

def task_lower_bound(ix,plan):
 """FIXED-plan lower bound: Task work floors and exact activation gates.
 No spill or contention included. Never used as a global optimality certificate.
 """
 ids=[s for seq in plan['core_schedules'] for s in seq];lookup={s:i for i,s in enumerate(ids)};groups=[[] for _ in ids]
 for u,s in plan['node_to_subgraph'].items():groups[lookup[s]].append(int(u))
 f=task_features(ix,groups);core={lookup[s]:k for k,seq in enumerate(plan['core_schedules']) for s in seq}
 qp={i:set(p) for i,p in f['pred'].items()};qs={i:set(s) for i,s in f['succ'].items()};previous={}
 for seq in plan['core_schedules']:
  for s,t in zip(seq,seq[1:]):
   a,b=lookup[s],lookup[t];qp[b].add(a);qs[a].add(b);previous[b]=a
 order=ix.topological(list(qp),qp,qs);finish={}
 for i in order:
  start=max((finish[j]+(1000 if core[j]!=core[i] else 0) for j in f['pred'][i]),default=0)
  if i in previous:start=max(start,finish[previous[i]]+100)
  finish[i]=start+duration_floor(f,i)
 r=candidate_lower_bound(ix,plan,'A',60);r['task_gate_lower_bound']=max(finish.values(),default=0)
 r['lower_bound_cycles']=max(r['lower_bound_cycles'],r['task_gate_lower_bound']);r['scope']='Fixed A partition/placement/queues; relaxed Task work, no global quality claim'
 return r

def task_trace(ix,plan,raw):
 """Exactly replay every A Task activation and one observed critical Task chain."""
 if raw['scene']!='A':raise ValueError('A required')
 view=check_plan(ix,plan);ps=view['subgraph_preds'];core=view['core_by_subgraph']
 tasks={t['task_id']:t for row in raw['per_core_timeline'] for t in row['tasks']};prev={b:a for seq in plan['core_schedules'] for a,b in zip(seq,seq[1:])}
 links={};residuals=[];counts=defaultdict(int)
 for i,t in tasks.items():
  gates=[(0,'initial',None,0)]
  if i in prev:gates.append((tasks[prev[i]]['end']+100,'same_core',prev[i],100))
  for a in ps[i]:gates.append((tasks[a]['end']+(1000 if core[a]!=core[i] else 0),'cross_core' if core[a]!=core[i] else 'same_core_data',a,1000 if core[a]!=core[i] else 0))
  best=max(gates,key=lambda x:(x[0],x[1],-1 if x[2] is None else x[2]));links[i]=best;counts[best[1]]+=1
  if t['start']!=best[0]:residuals.append(dict(task=i,observed=t['start'],reconstructed=best[0]))
 chain=[];last=max(tasks,key=lambda i:(tasks[i]['end'],i)) if tasks else None
 while last is not None:
  t=tasks[last];_,kind,p,lag=links[last]
  chain.append(dict(task=last,core=core[last],**{k:t[k] for k in ('start','end','duration')},gate=kind,gate_lag=lag,predecessor=p));last=p
 chain.reverse();active=sum(t['duration'] for t in chain);fixed=sum(t['gate_lag'] for t in chain)
 if not residuals and active+fixed!=raw['makespan']:raise AssertionError('Chain sum differs')
 return dict(makespan=raw['makespan'],tasks=len(tasks),start_residuals=residuals,gate_counts=dict(counts),one_critical_task_chain=chain,
  chain_task_service_cycles=active,chain_fixed_wait_cycles=fixed,warning='Observed Task service includes contention; not recoverable counterfactual savings')

def candidates(ix,n):
 rows=[]
 for method in ('cones','windows'):
  for scale in (.5,1.0):
   groups,meta=(closed_cones if method=='cones' else locality_windows)(ix,n,scale)
   plan,pm=list_assign(ix,groups,n)
   rows.append((f'{method}_{scale:g}',plan,{**meta,**pm,'bound':task_lower_bound(ix,plan)}))
 return rows

def band_components(ix, width, max_ops=2048):
 """Connected components inside consecutive dependency-depth bands.
 All inter-group data edges go to a later band; same-band components are independent.
 Unlike grouping each depth by core, each Task can contain several dependency levels.
 """
 if type(width) is not int or width<1 or max_ops<0:raise ValueError('Positive integer width required')
 blocks,bo,pred,succ,topo,w=chain_data(ix);level={}
 for b in topo:level[b]=1+max((level[a] for a in pred[b]),default=-1)
 band={b:level[b]//width for b in pred};seen=set();groups=[];rank={b:i for i,b in enumerate(topo)}
 for root in topo:
  if root in seen:continue
  todo=[root];seen.add(root);part=[]
  while todo:
   u=todo.pop();part.append(u)
   for v in pred[u]|succ[u]:
    if v not in seen and band[v]==band[root]:seen.add(v);todo.append(v)
  batch=[]
  for b in sorted(part,key=lambda b:rank[b]):
   if batch and max_ops and len(batch)+len(blocks[b])>max_ops:groups.append(batch);batch=[]
   batch.extend(blocks[b])
  if batch:groups.append(batch)
 return groups,dict(construction='weak components within depth bands',width=width,max_group_ops=max(map(len,groups),default=0))
