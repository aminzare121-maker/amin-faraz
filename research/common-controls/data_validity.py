"""Versioned provenance envelope. Reuses reviewed evidence gates, no raw reader.
Evidence trust is a reviewed registry input, never a status asserted by a feed.
"""
from registry import digest

FIELDS=('source','version','raw_sha256','kind','price_side','time','candle_completeness','session','bid_ask','provenance','evidence')
STATES={'VERIFIED','CONDITIONAL','UNKNOWN','INVALID','NOT_APPLICABLE'}

def validate(envelope):
    if envelope.get('schema')!='faraz-data-v1' or any(k not in envelope for k in FIELDS):raise ValueError('CONTRACT_SCHEMA')
    sha=envelope['raw_sha256']
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('RAW_HASH')
    if envelope['source'] not in ('EplanetDemo','Dukascopy','Synthetic') or not envelope['version']:raise ValueError('SOURCE_VERSION')
    if envelope['kind'] not in ('M1','M15','TICK'):raise ValueError('KIND')
    for name in ('price_side','time','candle_completeness','session','bid_ask','provenance'):
        item=envelope[name]
        if not isinstance(item,dict) or item.get('status') not in STATES:raise ValueError('STATUS_'+name)
        if item['status']=='VERIFIED':
            refs=item.get('evidence_ids',[])
            if not refs:raise ValueError('NO_EVIDENCE_'+name)
            for ref in refs:
                e=envelope['evidence'].get(ref,{})
                h=e.get('sha256','')
                if e.get('reviewed') is not True or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('UNREVIEWED_'+name)
    if envelope['price_side'].get('value') not in ('BID','ASK','BID_ASK','UNKNOWN'):raise ValueError('PRICE_SIDE')
    return digest(envelope)

def gate(envelope,purpose):
    fingerprint=validate(envelope)
    if purpose not in ('price_comparison','strategy_research','raw_inventory'):raise ValueError('PURPOSE')
    requirements=[] if purpose=='raw_inventory' else ['provenance','price_side','time','candle_completeness']
    if purpose=='strategy_research':requirements+=['session','bid_ask']
    reasons=[name for name in requirements if envelope[name]['status']!='VERIFIED']
    if envelope['time'].get('value')!='UTC' and purpose!='raw_inventory':reasons.append('TIME_NOT_UTC')
    if envelope['kind']=='TICK' and purpose=='strategy_research' and envelope['price_side']['value']!='BID_ASK':reasons.append('NO_BOTH_SIDES')
    return dict(contract_sha256=fingerprint,purpose=purpose,allowed=not reasons,blocked_by=sorted(set(reasons)),trade_allowed=False,
                financial_approval=False)
