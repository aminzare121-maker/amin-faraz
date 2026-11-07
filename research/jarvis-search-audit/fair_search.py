"""Offline candidate for root-fair file search. No app import or installation.
Slow content extractors are NOT preempted; hard extraction deadlines remain open.
"""
import os,time
from pathlib import Path
from collections import deque

def find_files(query,roots,*,max_visits=25000,max_results=50,seconds=20,excerpt=None,clock=time.monotonic):
    query=query.strip().casefold()
    if len(query)<2:return dict(matches=[],scanned=0,limited=False)
    if max_visits<1 or max_results<1 or seconds<=0:raise ValueError('LIMITS')
    deadline=clock()+seconds
    def paths(root):
        root=Path(root)
        if root.is_symlink() or (hasattr(root,'is_junction') and root.is_junction()):return
        for base,dirs,names in os.walk(root,topdown=True,followlinks=False):
            if clock()>=deadline:return
            dirs[:]=[d for d in dirs if not d.startswith('.') and d.lower() not in {'node_modules','__pycache__','appdata'}
                     and not (Path(base)/d).is_symlink()
                     and not (hasattr(Path(base)/d,'is_junction') and (Path(base)/d).is_junction())]
            for name in names:
                if clock()>=deadline:return
                yield Path(base)/name
    pending=deque(iter(paths(r)) for r in roots);matches=[];scanned=0
    while pending and scanned<max_visits and clock()<deadline:
        iterator=pending.popleft()
        try:path=next(iterator)
        except StopIteration:continue
        pending.append(iterator);scanned+=1
        if path.is_symlink():continue
        matched=query in path.name.casefold()
        if not matched and not Path(query).suffix and excerpt is not None and path.suffix.lower() in {'.txt','.md','.csv'}:
            matched=query in excerpt(path).casefold()
        if matched:matches.append({'name':path.name,'path':str(path)})
        if len(matches)>=max_results:break
    return dict(matches=matches,scanned=scanned,limited=bool(pending),
                extraction_timeout='NOT_HARD_BOUNDED',installed_app_changed=False)
