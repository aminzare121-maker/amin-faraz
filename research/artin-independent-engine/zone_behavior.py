"""Online FVG-reference and fresh break behaviour from raw candles.

S19:3357..3395 defines the wick gap as FVG, not a trading signal.
S21:2119..2261 uses the far edge of the same zone as break reference.
S15:2836..2897 distinguishes a new event from arriving after it.

Crossing bodies are a measurable supported subset, not a veto against every
gap-open example. No zone TTL, touch-consumption rule, ranking or ratio invented.
Strong/very-strong remains unresolved by shape alone; both branches are retained.
"""
from dataclasses import dataclass
from decimal import Decimal
from entry_engine import Fact
from raw_geometry import extract,geometry

@dataclass(frozen=True)
class FVGReference:
    identity: str
    low: Decimal
    high: Decimal
    known_at: int
    parents: tuple

class ZoneBehavior:
    def __init__(self,interval_seconds,source):
        self.interval=interval_seconds;self.source=source;self.bars=[];self.zones={};self.seen=set()
        self.cross_counts={};self.history_unknown=set()

    def fork(self):
        other=ZoneBehavior(self.interval,self.source)
        other.bars=list(self.bars);other.zones=dict(self.zones);other.seen=set(self.seen)
        other.cross_counts=dict(self.cross_counts);other.history_unknown=set(self.history_unknown)
        return other

    def step(self,bar):
        window=tuple(self.bars[-2:])+(bar,)
        raw=extract(window,at=bar.closed_at,interval_seconds=self.interval)
        events=[];previous=self.bars[-1] if self.bars else None
        if previous is not None and previous.closed_at!=bar.opened_at:
            self.history_unknown.update(self.zones)
        for zone in self.zones.values():
            if zone.known_at>bar.opened_at or previous is None:continue
            for side,edge in (('BUY',zone.high),('SELL',zone.low)):
                prior_far=previous.close>edge if side=='BUY' else previous.close<edge
                close_far=bar.close>edge if side=='BUY' else bar.close<edge
                body_cross=(bar.open<=edge<bar.close if side=='BUY' else bar.close<edge<=bar.open)
                if not close_far or prior_far:continue
                key=(zone.identity,side,bar.opened_at)
                if key in self.seen:continue
                self.seen.add(key)
                gap=previous.closed_at!=bar.opened_at
                prior_crosses=self.cross_counts.get(zone.identity,0)
                events.append({'kind':'FVG_BREAK_GEOMETRY','zone_id':zone.identity,'side':side,
                    'at':bar.closed_at,'zone_low':zone.low,'zone_high':zone.high,'edge':edge,
                    'body_cross':body_cross,'series_gap':gap,'reference_known_at':zone.known_at,
                    'prior_far_edge_crosses':prior_crosses,'history_unknown':zone.identity in self.history_unknown,
                    'parents':zone.parents,'classification':'BRANCH_STRENGTH_NOT_INFERRED_FROM_FULLBODY',
                    'possible_teacher_actions':('WEAK_WAIT_PULLBACK_CONFIRMATION','STRONG_CLOSE_ENTRY','VERY_STRONG_WAIT_HALF_BODY'),
                    'sources':((19,3357.52,3395.52),(21,2119,2261),(15,2836,2897))})
                self.cross_counts[zone.identity]=prior_crosses+1
        # Newly formed zones cannot be retrospectively broken by their own parent.
        for candidate in raw['candidates']:
            if candidate.kind!='FVG_CANDIDATE' or candidate.known_at!=bar.closed_at:continue
            identity='FVG:'+','.join(map(str,candidate.candle_open_times))
            self.zones.setdefault(identity,FVGReference(identity,candidate.low,candidate.high,
                candidate.known_at,candidate.candle_open_times))
        self.bars=(self.bars+[bar])[-2:]
        return events

    def reference_facts(self,events,side,at):
        candidates=[e for e in events if e['side']==side and e['at']==at]
        if len(candidates)!=1:return {},'MULTIPLE_REFERENCES' if candidates else 'NO_NEW_REFERENCE_BREAK'
        e=candidates[0]
        if e['history_unknown']:return {},'REVIEW_ZONE_HISTORY_UNKNOWN_AFTER_GAP'
        if e['prior_far_edge_crosses']:
            return {},'REVIEW_LIFECYCLE_UNRESOLVED_AFTER_PRIOR_CROSS'
        if not e['body_cross'] or e['series_gap']:return {},'CROSSING_NOT_ESTABLISHED_BY_THIS_BODY_SUBSET'
        source=self.source+':'+e['zone_id']+':'+str(e['at'])+':S19_3357_S21_2119_S15_2836'
        values={'family_selection_context':'ZONE_CONTEXT','level_kind':'FVG','zone_low':e['zone_low'],
            'zone_high':e['zone_high'],'current_setup':True,'break_occurred':True}
        return {k:Fact(v,at,source) for k,v in values.items()},'FRESH_REFERENCE_MEASURED_STRENGTH_STILL_REQUIRED'
