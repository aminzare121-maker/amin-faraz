"""Causal, explainable price features. SMC labels are explicit price-based proxies."""
from datetime import datetime, time as dtime, timezone
from statistics import mean
from zoneinfo import ZoneInfo
from .model import dec


SESSIONS={'Sydney':('Australia/Sydney',8,17),'Tokyo':('Asia/Tokyo',9,18),
          'London':('Europe/London',8,17),'New_York':('America/New_York',8,17)}
REQUIRED_DIRECTION_FRAMES=('15m','1h','4h','1D')


class BarValidationError(ValueError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


def sessions(timestamp):
    result=[]
    for name,(zone,start,end) in SESSIONS.items():
        local=datetime.fromtimestamp(timestamp,timezone.utc).astimezone(ZoneInfo(zone))
        if local.weekday()<5 and start<=local.hour<end:result.append(name)
    return result


def validate_bars(bars, asof, *, price_asof=None):
    if price_asof is not None and (type(price_asof) is not int or abs(price_asof-asof)>14*3600):
        raise BarValidationError('NATIVE_CLOCK_REFERENCE_INVALID')
    previous=-1
    for b in bars:
        if not isinstance(b,dict) or not {'time','open','high','low','close'}<=b.keys():
            raise BarValidationError('OHLC_SCHEMA_INVALID')
        native=b.get('time_basis')=='broker-server'
        if native != (price_asof is not None):raise BarValidationError('NATIVE_CLOCK_REFERENCE_MISSING' if native else 'CANDLE_TIME_BASIS_MISMATCH')
        bound=asof if price_asof is None else price_asof
        if type(b['time']) is not int or type(b.get('observed_at',asof)) is not int:raise BarValidationError('CANDLE_TIMESTAMP_INVALID')
        if b['time']<=previous or b['time']>bound or b.get('observed_at',asof)>asof:raise BarValidationError('CANDLE_TIME_ORDER_OR_FUTURE')
        o,h,l,c=(dec(b[k]) for k in ('open','high','low','close'))
        if not all(v.is_finite() for v in (o,h,l,c)):raise BarValidationError('OHLC_NONFINITE')
        if min(o,h,l,c)<=0 or h<max(o,l,c) or l>min(o,h,c):raise BarValidationError('OHLC_INVALID')
        previous=b['time']


def features(bars,asof,*,price_asof=None):
    validate_bars(bars,asof,price_asof=price_asof)
    # Forming candle is evidence available now, never used as a confirmed historical break.
    closed=[b for b in bars if b.get('final',False)]
    if len(closed)<24:return {'ready':False,'reason':'insufficient_confirmed_bars','forming':bool(bars and not bars[-1].get('final',False))}
    prior,last=closed[-21:-1],closed[-1]
    high=max(float(b['high']) for b in prior);low=min(float(b['low']) for b in prior)
    close=float(last['close']);atr=mean(float(b['high'])-float(b['low']) for b in closed[-14:])
    trend='up' if mean(float(b['close']) for b in closed[-5:])>mean(float(b['close']) for b in closed[-20:]) else 'down'
    bos='bullish' if close>high else 'bearish' if close<low else 'none'
    body=abs(close-float(last['open']));span=float(last['high'])-float(last['low'])
    fvg=None
    if float(closed[-1]['low'])>float(closed[-3]['high']):fvg={'side':'bullish','low':closed[-3]['high'],'high':closed[-1]['low']}
    elif float(closed[-1]['high'])<float(closed[-3]['low']):fvg={'side':'bearish','low':closed[-1]['high'],'high':closed[-3]['low']}
    opposite=[b for b in prior if (float(b['close'])<float(b['open']))==(bos=='bullish')]
    return {'ready':True,'trend':trend,'support':low,'resistance':high,'range_atr_proxy':atr,'bos':bos,
            'mss_proxy':bos!='none' and ((bos=='bullish')!=(trend=='up')),
            'displacement_ratio':body/span if span else 0,'fvg_proxy':fvg,
            'order_block_proxy':({'low':opposite[-1]['low'],'high':opposite[-1]['high']} if bos!='none' and opposite else None),
            'liquidity_proxy':{'prior_high':high,'prior_low':low},'forming':bool(bars and not bars[-1].get('final',False)),
            'forming_ohlc':bars[-1] if bars and not bars[-1].get('final',False) else None}


def analyze(frames,asof,*,price_asof=None):
    evidence={}
    invalid=[]
    for frame,bars in frames.items():
        try:evidence[frame]=features(bars,asof,price_asof=price_asof)
        except (ValueError,TypeError,KeyError) as error:
            invalid.append(frame)
            evidence[frame]={'ready':False,'reason':'invalid_market_bars',
                'error_code':getattr(error,'code','OHLC_VALUE_OR_SCHEMA_INVALID')}
    main=evidence.get('15m',{})
    context_ready=all(evidence.get(f,{}).get('ready') for f in ('1h','4h','1D'))
    context=[evidence[f].get('trend') for f in ('1h','4h','1D') if evidence.get(f,{}).get('ready')]
    blocking_invalid=[f for f in invalid if f in REQUIRED_DIRECTION_FRAMES]
    missing_required=[f for f in REQUIRED_DIRECTION_FRAMES if not evidence.get(f,{}).get('ready')]
    side='none'
    if main.get('ready') and main.get('bos')=='bullish' and context_ready and all(t=='up' for t in context):side='buy'
    if main.get('ready') and main.get('bos')=='bearish' and context_ready and all(t=='down' for t in context):side='sell'
    if blocking_invalid:side='none'
    return {'side':side,'reason':'invalid_market_data' if blocking_invalid else ('required_context_unavailable' if missing_required else 'confirmed_M15_break_with_context' if side!='none' else 'no_validated_aligned_setup'),
            'invalid_frames':blocking_invalid,'all_invalid_frames':invalid,
            'non_directional_invalid_frames':[f for f in invalid if f not in REQUIRED_DIRECTION_FRAMES],
            'unready_required_frames':missing_required,
            'features':evidence,'sessions':sessions(asof),'institutional_order_visibility':False,
            'candle_time_basis':'broker-server' if price_asof is not None else 'utc',
            'historical_utc_mapping_verified':price_asof is None and not invalid,
            'strategy':'price-breakout-v1-research-only'}
