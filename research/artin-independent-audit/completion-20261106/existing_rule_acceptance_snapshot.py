"""Research evidence gate only. This defines no Artin trading rules."""
import math
import re

FIELDS=('pivot_confirmation','trend_definition','entry_trigger','stop_placement',
        'target_or_exit','invalidation','exceptions')

def assess(rule):
    reasons=[]
    source=rule.get('source',{})
    if not isinstance(source,dict):source={}
    session=source.get('session')
    if type(session) is not int or session<1:reasons.append('SESSION_REQUIRED')
    start,end=source.get('start_seconds'),source.get('end_seconds')
    if not all(type(x) in (int,float) and math.isfinite(x) for x in (start,end)) or not 0<=start<end:
        reasons.append('VALID_SOURCE_INTERVAL_REQUIRED')
    for key in ('symbol','timeframe'):
        if not isinstance(source.get(key),str) or not source[key].strip():reasons.append(key.upper()+'_REQUIRED')
    evidence=rule.get('evidence',{})
    if not isinstance(evidence,dict):evidence={}
    for key in ('original_audio_verified','same_time_frame_verified','same_symbol_and_timeframe_verified'):
        if evidence.get(key) is not True:reasons.append(key.upper()+'_REQUIRED')
    for key in ('audio_sha256','frame_sha256'):
        if not isinstance(evidence.get(key),str) or not re.fullmatch('[0-9a-f]{64}',evidence[key]):
            reasons.append(key.upper()+'_REQUIRED')
    definitions=rule.get('definitions',{})
    if not isinstance(definitions,dict):definitions={}
    for key in FIELDS:
        if not isinstance(definitions.get(key),str) or not definitions[key].strip():reasons.append(key.upper()+'_UNDEFINED')
    if rule.get('causal_availability_defined') is not True:reasons.append('CAUSAL_TIMING_UNDEFINED')
    if rule.get('derived_from_outcome') is not False:reasons.append('OUTCOME_INDEPENDENCE_UNVERIFIED')
    return {'research_evidence_complete':not reasons,'reasons':reasons,
            'engine_ready':False,'orders_authorized':False,'profitability_verified':False}
