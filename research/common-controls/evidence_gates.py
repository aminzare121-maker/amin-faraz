"""Fail-closed historical clock and session gates. Reviewed receipts are trust inputs."""
def approved(evidence,registry):
    e=registry.get(evidence,{})
    sha=e.get('sha256','')
    return e.get('reviewed') is True and e.get('issuer')=='Eplanet' and isinstance(sha,str) and len(sha)==64 and all(c in '0123456789abcdef' for c in sha) and e.get('historical') is True

def server_to_utc(raw,periods,registry):
    candidates=[]
    for p in periods:
        if not approved(p.get('evidence_id'),registry) or p.get('status')!='VERIFIED':continue
        if type(p.get('offset_seconds')) is not int or p['utc_end']<=p['utc_start']:raise ValueError('BAD_PERIOD')
        utc=raw-p['offset_seconds']
        if p['utc_start']<=utc<p['utc_end']:candidates.append((utc,p['evidence_id']))
    if len(candidates)!=1:raise ValueError('TIME_UNKNOWN_OR_AMBIGUOUS')
    return candidates[0][0]

def classify_gap(start,end,schedule,registry):
    if type(start) is not int or type(end) is not int or start%900 or end%900 or end<=start:raise ValueError('BAD_GAP')
    slots=[]
    for t in range(start,end,900):
        matches=[s for s in schedule if s['start']<=t and t+900<=s['end'] and approved(s.get('evidence_id'),registry)]
        states={s['state'] for s in matches}
        state=next(iter(states)) if len(states)==1 and states<={'OPEN','CLOSED'} else 'UNKNOWN'
        slots.append({'time':t,'class':{'OPEN':'OPEN_MISSING','CLOSED':'SCHEDULED_CLOSED'}.get(state,'UNKNOWN')})
    kinds={s['class'] for s in slots}
    return {'classification':next(iter(kinds)) if len(kinds)==1 else 'UNKNOWN','slots':slots,'filled':0}

def final_gate(periods,gaps,costs_verified,registry,start,end):
    reasons=[]
    cursor=start
    for p in sorted(periods,key=lambda p:p['utc_start']):
        if p['utc_end']<=start or p['utc_start']>=end:continue
        if p['utc_start']>cursor or not approved(p.get('evidence_id'),registry) or p.get('status')!='VERIFIED':break
        if p['utc_start']<cursor and cursor!=start:break
        cursor=min(end,p['utc_end'])
    if end<=start or cursor!=end:reasons.append('TIME_MAPPING_UNVERIFIED')
    if any(g['classification']!='SCHEDULED_CLOSED' for g in gaps):reasons.append('OPEN_MISSING_OR_UNKNOWN')
    if not isinstance(costs_verified,dict) or costs_verified.get('status')!='VERIFIED' or not approved(costs_verified.get('evidence_id'),registry):reasons.append('COSTS_UNVERIFIED')
    return {'final_backtest_allowed':not reasons,'reasons':reasons,'trade_allowed':False}
