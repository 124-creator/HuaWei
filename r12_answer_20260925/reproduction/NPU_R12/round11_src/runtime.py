"""Linux process-tree timeout handling and atomic evidence I/O.
Does not alter any official simulation code. Cancels descendant sessions too.
"""
from __future__ import annotations
from pathlib import Path
import hashlib, json, os, signal, subprocess, time

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def write_json(path: Path, value) -> None:
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)

def descendants(pid: int) -> list[int]:
    children={}
    for folder in Path('/proc').iterdir():
        if not folder.name.isdigit():continue
        try:
            stat=(folder/'stat').read_text();rest=stat[stat.rfind(')')+2:].split();ppid=int(rest[1]);child=int(folder.name)
        except (OSError,IndexError,ValueError):continue
        children.setdefault(ppid,[]).append(child)
    found=[];stack=[pid];seen={pid}
    while stack:
        for child in children.get(stack.pop(),[]):
            if child not in seen:seen.add(child);found.append(child);stack.append(child)
    return found

def execute(cmd: list[str], timeout: float, log: Path) -> dict:
    if os.name!='posix' or not Path('/proc').exists():
        raise RuntimeError('This audited process-tree runner requires Linux /proc.')
    log=Path(log);log.parent.mkdir(parents=True,exist_ok=True);t=time.perf_counter()
    process=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,encoding='utf-8',errors='replace',start_new_session=True)
    killed=[]
    try:
        text,_=process.communicate(timeout=max(.1,timeout));status='ok' if process.returncode==0 else 'process_error'
    except subprocess.TimeoutExpired:
        killed=descendants(process.pid)
        for pid in list(reversed(killed))+[process.pid]:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
        try:text,_=process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill();text,_=process.communicate();
        status='timeout'
    log.write_text(text,encoding='utf-8')
    return {'status':status,'returncode':process.returncode,'wall_seconds':time.perf_counter()-t,
        'timeout_seconds':timeout,'command':cmd,'terminated_descendant_pids':killed}
