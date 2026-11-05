"""Strict overlap QA. No financial result when side/session/cost semantics are unknown."""
from decimal import Decimal
from statistics import median

def compare(left,right,left_meta,right_meta):
    required=('canonical','price_side','timezone','bar_seconds','unit','session_evidence','mapping_evidence')
    for meta in (left_meta,right_meta):
        if any(meta.get(k) in (None,'','UNKNOWN') for k in required):raise ValueError('METADATA_UNKNOWN')
        if meta['timezone']!='UTC' or meta['bar_seconds']!=900 or meta['price_side'] not in ('BID','ASK'):raise ValueError('UNSUPPORTED_SEMANTICS')
    for key in ('canonical','price_side','timezone','bar_seconds','unit'):
        if left_meta[key]!=right_meta[key]:raise ValueError('INCOMPARABLE_'+key)
    def index(rows):
        result={};last=None
        for row in rows:
            t=row['time']
            if type(t) is not int or t%900 or (last is not None and t<=last):raise ValueError('DUPLICATE_OR_TIME_ORDER')
            p={k:Decimal(str(row[k])) for k in ('open','high','low','close')}
            if any(not v.is_finite() or v<=0 for v in p.values()):raise ValueError('INVALID_PRICE')
            if not p['low']<=min(p['open'],p['close'])<=max(p['open'],p['close'])<=p['high']:raise ValueError('OHLC')
            result[t]=p;last=t
        return result
    a,b=index(left),index(right);common=sorted(set(a)&set(b))
    if not common:return {'status':'NO_OVERLAP','matched':0,'financial_comparison':'NOT_RUN'}
    begin,end=max(min(a),min(b)),min(max(a),max(b))
    left_only=[t for t in a if begin<=t<=end and t not in b];right_only=[t for t in b if begin<=t<=end and t not in a]
    metrics={}
    for field in ('open','high','low','close'):
        diffs=[a[t][field]-b[t][field] for t in common]
        metrics[field]={'signed_mean':str(sum(diffs)/len(diffs)),'median_absolute':str(median(abs(d) for d in diffs)),'max_absolute':str(max(abs(d) for d in diffs))}
    return {'status':'COMPARABLE_PRICE_ONLY','matched':len(common),'overlap_first':begin,'overlap_last':end,
            'left_only_in_overlap':len(left_only),'right_only_in_overlap':len(right_only),'price_differences':metrics,
            'spread_difference':'UNKNOWN_NEEDS_SYNCHRONIZED_BID_ASK','latency':'UNKNOWN_NEEDS_RECEIPT_TIMES',
            'financial_comparison':'NOT_RUN','causal_attribution':'NOT_ESTABLISHED'}

def news_at(records,decision_ms):
    """Strict availability gate. Caller supplies frozen point-in-time versions."""
    out=[]
    if type(decision_ms) is not int or decision_ms<0:raise ValueError('DECISION_TIME')
    for r in records:
        sha=r.get('receipt_sha256')
        if r.get('kind')!='FACT' or r.get('status')!='VERIFIED' or not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):continue
        p,a=r.get('published_ms'),r.get('available_ms')
        if type(p) is not int or type(a) is not int or not 0<=p<=a<=decision_ms:continue
        if r.get('retracted') is True:continue
        out.append(dict(r))
    return out

def net_cost(gross,spread,commission,swap,slippage):
    if any(v is None for v in (gross,spread,commission,swap,slippage)):return {'status':'UNKNOWN_COST','net':None}
    values=[Decimal(str(v)) for v in (gross,spread,commission,swap,slippage)]
    if any(not x.is_finite() for x in values) or any(x<0 for x in (values[1],values[2],values[4])):raise ValueError('COST_VALUE')
    # Swap is signed cash flow; positive swap credit, negative debit.
    return {'status':'EXPLICIT_COST_INPUTS','net':str(values[0]-values[1]-values[2]+values[3]-values[4]),
            'costs_validated':False}
