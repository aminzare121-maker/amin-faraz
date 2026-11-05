"""In-memory synthetic contract QA. No file, network, CSV or broker reader."""
import hashlib,json
from decimal import Decimal,InvalidOperation
REQUIRED=('licence','provenance','session_calendar','timezone','dst_policy','commission','tick_size','tick_value','swap','slippage','volume_grid','account_currency')
def future_gate(metadata):
    missing=[k for k in REQUIRED if not isinstance(metadata.get(k),dict) or metadata[k].get('status')!='VERIFIED' or not metadata[k].get('evidence_id')]
    # Even asserted VERIFIED records do not grant real-data authority in this package.
    return {'missing_or_unverified':missing,'real_data_authorized':False,'fit_allowed':False,'trade_allowed':False,'status':'BLOCKED_CURRENT_SCOPE'}

def dry_run(raw,receipt):
    base={'fit_allowed':False,'trade_allowed':False,'real_data_used':False,'rows_processed':0}
    if not isinstance(receipt,dict) or receipt.get('scope')!='SYNTHETIC_ONLY' or receipt.get('origin')!='IN_MEMORY_FIXTURE':
        return {**base,'status':'BLOCKED','reasons':['REAL_OR_UNVERIFIED_INPUT_FORBIDDEN']}
    if not isinstance(raw,bytes):return {**base,'status':'BLOCKED','reasons':['IMMUTABLE_BYTES_REQUIRED']}
    sha=hashlib.sha256(raw).hexdigest()
    if receipt.get('sha256')!=sha:return {**base,'status':'BLOCKED','reasons':['ORIGINAL_BYTE_HASH_MISMATCH']}
    if receipt.get('timezone')!='UTC' or receipt.get('session')!='SYNTHETIC_CONTINUOUS':
        return {**base,'status':'BLOCKED','reasons':['TIME_OR_SESSION_UNKNOWN']}
    try:
        rows=json.loads(raw)
        if not isinstance(rows,list) or not rows:raise ValueError('NO_DATA')
        kind=receipt.get('kind');prev=None
        for row in rows:
            if not isinstance(row,dict):raise ValueError('SCHEMA')
            if kind=='TICK':
                if set(row)!={'ts_ms','bid','ask'}:raise ValueError('TICK_SCHEMA')
                ts=row['ts_ms']; nums=[number(row[k]) for k in ('bid','ask')]
                if nums[0]>nums[1]:raise ValueError('CROSSED_QUOTE')
            elif kind=='M15':
                if set(row)!={'open_ms','close_ms','available_ms','open','high','low','close','price_side'}:raise ValueError('BAR_SCHEMA')
                ts=row['open_ms'];close=row['close_ms'];available=row['available_ms']
                if type(close) is not int or type(available) is not int or type(ts) is not int or close-ts!=900000 or available<close:raise ValueError('BAR_TIME_OR_LOOKAHEAD')
                if row['price_side'] not in ('BID','ASK'):raise ValueError('PRICE_SIDE_UNKNOWN')
                o,h,l,c=[number(row[k]) for k in ('open','high','low','close')]
                if not l<=min(o,c)<=max(o,c)<=h:raise ValueError('OHLC')
                if prev is not None and ts-prev!=900000:raise ValueError('SESSION_GAP_UNCLASSIFIED')
            else:raise ValueError('KIND_UNKNOWN')
            if type(ts) is not int or ts<0 or (prev is not None and ts<=prev):raise ValueError('TIME_ORDER_OR_DUPLICATE')
            prev=ts
        return {**base,'status':'SYNTHETIC_DRY_RUN_PASS','rows_processed':len(rows),'sha256_before':sha,'sha256_after':hashlib.sha256(raw).hexdigest(),'reasons':[]}
    except (ValueError,TypeError,KeyError,InvalidOperation,UnicodeError) as exc:
        return {**base,'status':'BLOCKED','reasons':[str(exc)]}

def number(v):
    if not isinstance(v,str):raise ValueError('DECIMAL_STRING_REQUIRED')
    d=Decimal(v)
    if not d.is_finite() or d<=0:raise ValueError('NONFINITE_OR_NONPOSITIVE_PRICE')
    return d

def synthetic_receipt(rows,kind='TICK'):
    raw=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
    return raw,{'scope':'SYNTHETIC_ONLY','origin':'IN_MEMORY_FIXTURE','sha256':hashlib.sha256(raw).hexdigest(),'timezone':'UTC','session':'SYNTHETIC_CONTINUOUS','kind':kind}
