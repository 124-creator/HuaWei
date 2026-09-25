"""Deterministic interval-index calendar, replacing linear empty-slot scans.

Only the virtual heuristic calendar is indexed. No official evaluator changes.
Fit is tested with exactly the old expression t + duration + gap <= next_start.
Subtree pruning uses outward slack to avoid unsafe floating-point elimination.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

_MASK=(1<<64)-1

def _priority(i:int)->int:
    x=(i+0x9e3779b97f4a7c15)&_MASK
    x=((x^(x>>30))*0xbf58476d1ce4e5b9)&_MASK
    x=((x^(x>>27))*0x94d049bb133111eb)&_MASK
    return x^(x>>31)

@dataclass(slots=True)
class _Node:
    low: float
    high: float
    ident: int
    priority: int
    left: _Node|None=None
    right: _Node|None=None
    span: float=0.0
    rightmost: float=0.0
    def __post_init__(self):
        self.span=self.high-self.low
        self.rightmost=self.high
    @property
    def key(self):return self.low,self.ident

def _update(n):
    n.span=max(n.high-n.low,n.left.span if n.left else -math.inf,n.right.span if n.right else -math.inf)
    n.rightmost=max(n.high,n.left.rightmost if n.left else -math.inf,n.right.rightmost if n.right else -math.inf)
    return n

def _split(n,key):
    if n is None:return None,None
    if n.key<key:
        n.right,b=_split(n.right,key);return _update(n),b
    a,n.left=_split(n.left,key);return a,_update(n)

def _merge(a,b):
    if a is None:return b
    if b is None:return a
    if a.priority<b.priority:a.right=_merge(a.right,b);return _update(a)
    b.left=_merge(a,b.left);return _update(b)

def _insert(root,n):
    if root is None:return n
    if n.priority<root.priority:
        n.left,n.right=_split(root,n.key);return _update(n)
    if n.key<root.key:root.left=_insert(root.left,n)
    else:root.right=_insert(root.right,n)
    return _update(root)

def _delete(root,key):
    if root is None:raise KeyError(key)
    if root.key==key:return _merge(root.left,root.right)
    if key<root.key:root.left=_delete(root.left,key)
    else:root.right=_delete(root.right,key)
    return _update(root)

class GapCalendar:
    def __init__(self,gap:float=0):
        if gap<0:raise ValueError('gap must be nonnegative')
        self.gap=gap;self.serial=0;self.root=None;self.tasks=[];self.query_visits=0
        self._add(0,math.inf)
    def _add(self,low,high):
        # Every virtual duration is at least 1, matching the original constructor.
        if low+1+self.gap>high:return
        self.serial+=1
        self.root=_insert(self.root,_Node(low,high,self.serial,_priority(self.serial)))
    def find(self,ready:float,duration:float):
        if ready<0 or duration<1 or not math.isfinite(ready+duration):raise ValueError('Invalid calendar request')
        need=duration+self.gap
        def seek(n):
            if n is None:return None
            self.query_visits+=1
            scale=max(abs(ready),abs(duration),abs(n.rightmost))
            eps=0 if not math.isfinite(scale) else 16*math.ulp(max(1.0,scale))
            if n.span+eps<need or n.rightmost+eps<ready+need:return None
            ans=seek(n.left)
            if ans is not None:return ans
            t=max(ready,n.low)
            if t+duration+self.gap<=n.high:return t,n.key
            return seek(n.right)
        found=seek(self.root)
        if found is None:raise AssertionError('Infinite tail must fit')
        return found
    def occupy(self,key,start:float,duration:float,task:int):
        n=self.root
        while n is not None and n.key!=key:n=n.left if key<n.key else n.right
        if n is None:raise KeyError(key)
        if start<n.low or start+duration+self.gap>n.high:raise ValueError('Slot no longer fits')
        low,high=n.low,n.high
        self.root=_delete(self.root,key)
        end=start+duration
        self._add(low,start)
        self._add(end+self.gap,high)
        self.tasks.append((start,end,task))
    def ordered_tasks(self):return sorted(self.tasks)
