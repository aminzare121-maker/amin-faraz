"""Match independently recorded ASR segment IDs to their true timestamps.

Never zip separate segment-ID and timestamp lists by position. This module
only performs source identity checks; it cannot infer a trading decision.
"""
from collections import Counter
import math

def bind_pair(pair, source_index, tolerance=0.025):
    if not isinstance(pair,dict):raise ValueError('pair must be an object')
    ids=pair.get('segment_ids'); times=pair.get('phrases'); expected=pair.get('source_audio_sha256')
    if not isinstance(ids,list) or not isinstance(times,list) or len(ids)!=len(times) or len(ids)!=2 or len(set(ids))!=len(ids):
        raise ValueError('pair must have two unique IDs and intervals')
    if not isinstance(expected,str) or len(expected)!=64:raise ValueError('invalid original wav sha')
    def validate(a,b):
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (a,b)) or a<0 or b<=a:raise ValueError('invalid speech interval')
        return (float(a),float(b))
    observed=[]
    for sid in ids:
        record=source_index.get(sid)
        if not record:raise ValueError('source segment id not found')
        if record.get('source_audio_sha256')!=expected:raise ValueError('source audio sha mismatch')
        a,b=validate(record['start_seconds'],record['end_seconds'])
        observed.append({'source_segment_id':sid,'start_seconds':a,'end_seconds':b})
    unpaired=[validate(*t) for t in times]
    for x in observed:
        matching=[(i,t) for i,t in enumerate(unpaired) if abs(t[0]-x['start_seconds'])<=tolerance and abs(t[1]-x['end_seconds'])<=tolerance]
        if len(matching)!=1:raise ValueError('no unique matching speech interval for ASR id')
        unpaired.pop(matching[0][0])
    if unpaired:raise ValueError('extra intervals')
    return sorted(observed,key=lambda x:(x['start_seconds'],x['source_segment_id']))