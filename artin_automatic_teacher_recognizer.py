"""Autonomous, causal OHLC recognition of *measurable subsets* in Artin notes.

This is not a semantic certification of every Artin example. It does not
invent ATR thresholds, arbitrary swing windows, zone age limits, sentiment,
trend-strength classification, or a broker contract. The first available
closed candle can be evaluated without a human event-label file.

Source map:
 - Technical(1).pdf p11: three-candle wick-gap FVG geometry
 - Technical(1).pdf p13: PRZ from FVG, doubt then first confidence in reversal
 - Technical(1).pdf p14: break line / FVG breakout
 - Technical(1).pdf p17: structural SL references, FVG among them
 - FXM.pdf p2,p4: risk budget, RR table, TP ladder
 - existing core/teacher_features.py: unambiguous strict candle predicates.

A signal is tagged PDF_MEASURABLE_SUBSET_CANDIDATE, NOT VERIFIED_TEACHER_TRADE.
The rule for selecting exact FVG opposite edge as operational stop and the
next-bar-open paper-fill assumption are exposed assumptions, not attributed to
Artin. No broker execution APIs are imported.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
import hashlib, json

SOURCE_PAGES={
 'FVG':'Technical(1).pdf#page=11',
 'REVERSAL':'Technical(1).pdf#page=13',
 'BREAK':'Technical(1).pdf#page=14',
 'STOP':'Technical(1).pdf#page=17',
 'FXM_RISK':'FXM.pdf#page=2',
 'FXM_TP':'FXM.pdf#page=4',
}

class InputError(ValueError):pass

def D(v):
    if type(v) not in (int,str,Decimal):raise InputError('EXACT_DECIMAL_REQUIRED')
    try:x=Decimal(v)
    except (InvalidOperation,ValueError):raise InputError('INVALID_DECIMAL') from None
    if not x.is_finite() or x<=0:raise InputError('POSITIVE_PRICE_REQUIRED')
    return x

@dataclass(frozen=True)
class Bar:
    t:int
    open:Decimal
    high:Decimal
    low:Decimal
    close:Decimal
    def __post_init__(self):
        if type(self.t) is not int or self.t<0 or self.t%900:raise InputError('INVALID_M15_TIME')
        for f in ('open','high','low','close'):
            object.__setattr__(self,f,D(getattr(self,f)))
        if not(self.low<=min(self.open,self.close)<=max(self.open,self.close)<=self.high):
            raise InputError('INVALID_OHLC')
    @property
    def color(self):return 'BUY' if self.close>self.open else 'SELL' if self.close<self.open else 'FLAT'
    @property
    def body(self):return abs(self.close-self.open)
    @property
    def upper(self):return self.high-max(self.open,self.close)
    @property
    def lower(self):return min(self.open,self.close)-self.low
    @property
    def doubt(self):return max(self.upper,self.lower)>self.body
    @property
    def confidence(self):return self.body>self.upper+self.lower
    @property
    def exact_fullbody(self):return self.body>0 and self.upper==0 and self.lower==0

@dataclass
class Zone:
    identity:str
    low:Decimal
    high:Decimal
    direction:str
    known_at:int
    first_touch_at:int|None=None
    buy_broken:bool=False
    sell_broken:bool=False

@dataclass(frozen=True)
class Recognition:
    at:int
    side:str
    route:str
    zone_id:str
    zone_low:str
    zone_high:str
    observed_price:str
    operational_stop:str
    source_bars:tuple
    sources:tuple
    status:str='PDF_MEASURABLE_SUBSET_CANDIDATE'
    teacher_semantics_fully_verified:bool=False
    actionable_broker_order:bool=False

class AutoRecognizer:
    """Streaming recognizer; only closed M15 candles in ascending order."""
    def __init__(self):
        self.last=[]
        self.zones={}
        self.seen=set()
        self.latest=None
        self.counts={'bars':0,'fvg_created':0,'reversal_candidates':0,'break_candidates':0,
                     'ambiguous_candidates':0,'history_discontinuities':0}
        self.signal_log=[]

    def step(self,bar:Bar):
        if not isinstance(bar,Bar):raise InputError('BAR_REQUIRED')
        if self.latest is not None and bar.t<=self.latest:raise InputError('DUPLICATE_OR_OUT_OF_ORDER')
        if self.latest is not None and bar.t!=self.latest+900:
            # Unknown missing-session context must not be silently bridged.
            self.zones={};self.last=[];self.counts['history_discontinuities']+=1
        self.latest=bar.t;self.counts['bars']+=1
        results=[]
        if self.last:
            preceding=self.last[-1]
            for zone in self.zones.values():
                # Zone exists before current candle opens. No forward information.
                if zone.known_at>bar.t:continue
                body_buy=(bar.open<=zone.high<bar.close)
                body_sell=(bar.close<zone.low<=bar.open)
                for side,crossed,flag in (('BUY',body_buy,'buy_broken'),('SELL',body_sell,'sell_broken')):
                    if crossed and not getattr(zone,flag):
                        setattr(zone,flag,True)
                        if bar.exact_fullbody:
                            stop=zone.low if side=='BUY' else zone.high
                            if (stop<bar.close if side=='BUY' else stop>bar.close):
                                results.append(Recognition(bar.t+900,side,'BREAK_FVG_EXACT_FULLBODY',zone.identity,
                                    str(zone.low),str(zone.high),str(bar.close),str(stop),
                                    tuple(zone.identity.split(':')[1:])+ (bar.t,),
                                    (SOURCE_PAGES['FVG'],SOURCE_PAGES['BREAK'],SOURCE_PAGES['STOP'])))
                            self.counts['break_candidates']+=1
                # The first observed return to a newly formed FVG can be used
                # to find the immediately following doubt->confidence pair.
                if zone.first_touch_at==preceding.t and zone.known_at<=preceding.t:
                    side=zone.direction
                    # Opposite coloured doubt (leg direction) and same-direction
                    # confidence is a measurable, intentionally narrow subset;
                    # a candle alone cannot establish the teacher's entire leg.
                    if (preceding.color!=side and preceding.color!='FLAT'
                        and preceding.doubt and bar.color==side and bar.confidence):
                        stop=zone.low if side=='BUY' else zone.high
                        if (stop<bar.close if side=='BUY' else stop>bar.close):
                            results.append(Recognition(bar.t+900,side,'REVERSAL_FVG_DOUBT_CONFIDENCE',zone.identity,
                                str(zone.low),str(zone.high),str(bar.close),str(stop),
                                (preceding.t,bar.t),
                                (SOURCE_PAGES['FVG'],SOURCE_PAGES['REVERSAL'],SOURCE_PAGES['STOP'])))
                            self.counts['reversal_candidates']+=1
                # Record first-touch after evaluating current-bar decisions:
                # it cannot create retrospective signals on the same candle.
                if zone.first_touch_at is None and zone.known_at<=bar.t and bar.low<=zone.high and bar.high>=zone.low:
                    zone.first_touch_at=bar.t

        if len(self.last)>=2:
            a,b=self.last[-2:]
            if a.t+900==b.t and b.t+900==bar.t:
                if a.high<bar.low:
                    ident=f'FVG:{a.t}:{b.t}:{bar.t}'
                    self.zones[ident]=Zone(ident,a.high,bar.low,'BUY',bar.t+900)
                    self.counts['fvg_created']+=1
                elif bar.high<a.low:
                    ident=f'FVG:{a.t}:{b.t}:{bar.t}'
                    self.zones[ident]=Zone(ident,bar.high,a.low,'SELL',bar.t+900)
                    self.counts['fvg_created']+=1
        self.last=(self.last+[bar])[-2:]
        # More than one qualifying zone gives an ambiguous market reference.
        # Do not choose the highest/nearest zone by a made-up ranking.
        unique={ (r.side,r.route,r.zone_id):r for r in results}
        if len(unique)>1:
            self.counts['ambiguous_candidates']+=1
            self.signal_log.append({'at':bar.t+900,'status':'REVIEW_MULTIPLE_ZONE_REFERENCES',
                                    'candidates':[asdict(x) for x in unique.values()]})
            return []
        new=[r for r in unique.values() if (r.at,r.zone_id,r.route,r.side) not in self.seen]
        for r in new:
            self.seen.add((r.at,r.zone_id,r.route,r.side));self.signal_log.append(asdict(r))
        return new


def parse_bars(path):
    """Read user's native ePlanet M15 observations; reject unsafe timing/rows."""
    path=Path(path)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    rows=[]
    with path.open(encoding='utf-8-sig') as f:
        for i,line in enumerate(f):
            if not line.strip():continue
            x=json.loads(line)
            t=x.get('raw_open_epoch_no_certified_utc_offset',x.get('time'))
            if type(t) is not int:raise InputError(f'INVALID_TIME_ROW:{i}')
            rows.append(Bar(t,D(str(x['open'])),D(str(x['high'])),D(str(x['low'])),D(str(x['close']))))
    if not rows:raise InputError('NO_BARS')
    return rows,digest


def run_scan(bars):
    detector=AutoRecognizer();signals=[]
    for x in bars:signals.extend(detector.step(x))
    return detector,signals


def report(bars,source_sha,detector,signals):
    return {'schema':'artin_teacher_auto_ohlc_scan_v1',
            'input_sha256':source_sha,'source_bars':len(bars),
            'source_kind':'REAL_BAR_PRICES_SOURCE_NOT_PROOF_OF_TEACHER_TRADES',
            'counts':detector.counts,'signal_count':len(signals),
            'signals':[asdict(s) for s in signals],
            'engine_route_claim':'2_MEASURABLE_PDF_SUBSETS_OF_13_NOT_COMPLETE_TEACHER_SEMANTICS',
            'video_rules_independently_validated':False,
            'paper_or_broker_orders_created':0,
            'assumptions_not_attributed_to_teacher':[
              'strict same-bar OHLC fullbody is only a measurable subset of strong-candle discussion',
              'first FVG touch is an ambiguity-control selection, not a proven teacher filter',
              'opposite FVG edge as operational stop is one chart reference, not a verified teacher choice',
              'opposite-colour doubt does not independently establish an entire market leg',
              'signal available after latest decision candle closes; next-open actual fill unproven'],
            'sources':SOURCE_PAGES}