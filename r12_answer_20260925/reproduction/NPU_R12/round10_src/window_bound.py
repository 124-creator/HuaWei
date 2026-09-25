"""Global precedence-window workload bound, independent of a submitted plan.

For r_v = earliest compute-only start and q_v = longest successor compute work,
U(a,b,p)={v:pipe(v)=p,r_v>=a,q_v>=b} must fit in [a,T-b]. Hence
T >= a+b+ceil(sum(c_v:v in U)/N). Nonempty subsets only.
This is a necessary capacity/precedence bound, not an exact scheduler.
"""
from __future__ import annotations
from pathlib import Path
import sys, math
ROOT=Path(__file__).resolve().parents[1]
for d in ('src','official/code'):sys.path.insert(0,str(ROOT/d))
from solver import GraphIndex

class RangeMax:
    def __init__(self,n):
        self.n=n;self.m=[-10**60]*(4*max(1,n));self.lazy=[0]*len(self.m);self.idx=[-1]*len(self.m)
    def _push(self,k):
        x=self.lazy[k]
        if x:
            for c in (k*2,k*2+1):self.m[c]+=x;self.lazy[c]+=x
            self.lazy[k]=0
    def _pull(self,k):
        c=k*2 if self.m[k*2]>=self.m[k*2+1] else k*2+1
        self.m[k]=self.m[c];self.idx[k]=self.idx[c]
    def add_prefix(self,end,x,k=1,l=0,r=None):
        r=self.n-1 if r is None else r
        if end<l:return
        if r<=end:self.m[k]+=x;self.lazy[k]+=x;return
        self._push(k);m=(l+r)//2
        self.add_prefix(end,x,k*2,l,m)
        if end>m:self.add_prefix(end,x,k*2+1,m+1,r)
        self._pull(k)
    def activate(self,j,val,k=1,l=0,r=None):
        r=self.n-1 if r is None else r
        if l==r:self.m[k]=val;self.idx[k]=j;self.lazy[k]=0;return
        self._push(k);m=(l+r)//2
        if j<=m:self.activate(j,val,k*2,l,m)
        else:self.activate(j,val,k*2+1,m+1,r)
        self._pull(k)

class Fenwick:
    def __init__(self,n):self.b=[0]*(n+1);self.total=0
    def add(self,j,x):
        self.total+=x;j+=1
        while j<len(self.b):self.b[j]+=x;j+=j&-j
    def prefix(self,j):
        s=0
        while j>0:s+=self.b[j];j-=j&-j
        return s

def times(index):
    r={};q={}
    for u in index.topo:r[u]=max((r[v]+index.ops[v]['cycles'] for v in index.pred[u]),default=0)
    for u in reversed(index.topo):q[u]=max((q[v]+index.ops[v]['cycles'] for v in index.succ[u]),default=0)
    cp=max((r[u]+index.ops[u]['cycles'] for u in index.ids),default=0)
    return r,q,cp

def bound(index:GraphIndex,n:int,pre=None):
    if n<1:raise ValueError('n must be positive')
    rr,qq,cp=pre or times(index);best=cp;cert={'kind':'compute_path','cycles':cp};weights={}
    for p in ('PIPE_M','PIPE_V'):
        ids=[u for u in index.ids if index.ops[u]['pipe']==p and index.ops[u]['cycles']>0]
        weights[p]=sum(index.ops[u]['cycles'] for u in ids)
        if not ids:continue
        levels=sorted(set(qq[u] for u in ids));pos={b:j for j,b in enumerate(levels)}
        tree=RangeMax(len(levels));fw=Fenwick(len(levels));active=set()
        ordered=sorted(ids,key=lambda u:(-rr[u],u));i=0
        while i<len(ordered):
            a=rr[ordered[i]]
            while i<len(ordered) and rr[ordered[i]]==a:
                u=ordered[i];j=pos[qq[u]];w=index.ops[u]['cycles'];fw.add(j,w);tree.add_prefix(j,w)
                if j not in active:
                    tree.activate(j,n*qq[u]+fw.total-fw.prefix(j));active.add(j)
                i+=1
            val=a+(tree.m[1]+n-1)//n
            if val>best:
                j=tree.idx[1];b=levels[j];work=tree.m[1]-n*b
                best=val;cert={'kind':'precedence_window','pipe':p,'a':a,'b':b,'work':work,'cores':n,'cycles':val}
    old=max(cp,*((v+n-1)//n for v in weights.values()))
    return {'old_compute_lower_bound':old,'window_lower_bound':best,'witness':cert,
            'proof_scope':'all legal schedules; per-pipe capacity N; original compute-only precedence','pipe_work':weights}

def brute(index,n):
    r,q,cp=times(index);best=cp
    for p in ('PIPE_M','PIPE_V'):
        us=[u for u in index.ids if index.ops[u]['pipe']==p]
        for a in {r[u] for u in us}:
            for b in {q[u] for u in us}:
                w=sum(index.ops[u]['cycles'] for u in us if r[u]>=a and q[u]>=b)
                if w:best=max(best,a+b+(w+n-1)//n)
    return best

if __name__=='__main__':
    import json,time,csv
    t=time.perf_counter();out=[]
    for graph in sorted((ROOT/'official/data').glob('case_*.json')):
        idx=GraphIndex(json.loads(graph.read_text()));pre=times(idx)
        for n in range(1,6):out.append({'case':graph.stem,'cores':n,**bound(idx,n,pre)})
    dest=ROOT/'round10_reports/window_bounds.json';dest.write_text(json.dumps({'records':out,'wall_seconds':time.perf_counter()-t},ensure_ascii=False,indent=2))
    print('bounds',len(out),'seconds',time.perf_counter()-t)
