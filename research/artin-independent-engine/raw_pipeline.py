"""CSV -> causal measurements -> teacher predicates -> sourced context -> entry.

The pipeline does not turn a raw FVG into an accepted zone or body colour into
economic bias. Every decision includes all absent dependencies, even when the
entry evaluator exits at its first gate. Missing data is never a negative setup.
"""
import csv,io,json
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from entry_engine import Engine,Fact,Observation,RULE_IDS
from raw_geometry import Candle,extract,geometry
from teacher_features import candle_predicates
from context_inputs import facts_as_of

COMMON=('sentiment_permission','current_setup')
FAMILY=('family_selection_context','trend_strength')
REQUIRED={
 'PULLBACK_STANDARD':('break_occurred','post_break_pivot_confirmed','retest_confirmed','decision_candle_closed','decision_close','post_break_pivot_level'),
 'REVERSAL_CLASSIC':('zone_context','reversal_relative_to_last_leg','decision_candle_closed','doubt_confirmed','first_confidence_confirmed'),
 'REVERSAL_THREE':('zone_context','reversal_relative_to_last_leg','decision_candle_closed','three_same_direction_sequence','doubt_confidence_condition','half_leg_condition'),
 'REVERSAL_STAR':('zone_context','reversal_relative_to_last_leg','decision_candle_closed','star_sequence','body_penetration_condition','half_leg_condition'),
 'BREAK_STRONG':('break_strength','fullbody_or_marubozu','decision_candle_closed','level_kind','decision_close'),
 'BREAK_WEAK_PIVOT':('break_strength','pullback_confirmed','post_break_pivot_confirmed','decision_candle_closed','decision_close','post_break_pivot_level'),
 'BREAK_WEAK_FULLBODY_EXCEPTION':('break_strength','pullback_confirmed','fullbody_or_marubozu','fullbody_exception_context','decision_candle_closed'),
 'BREAK_VERY_STRONG_RETEST':('break_strength','not_chasing','reference_body_open','reference_body_close','retouch_low','retouch_high'),
 'STOPPUNCH_SAME_COLOUR':('strong_run_in_sentiment_direction','zone_context','same_colour_pause','pause_candle_closed'),
 'STOPPUNCH_DOJI_AHEAD':('strong_run_in_sentiment_direction','zone_context','doji_confirmed','day_analysis_state','doji_candle_closed'),
 'STOPPUNCH_DOJI_TIED':('strong_run_in_sentiment_direction','zone_context','doji_confirmed','day_analysis_state','following_confirmation_closed','confirmation_near','confirmation_timely','confirmation_close','doji_shadow_high'),
 'STOPPUNCH_OPPOSITE_CONFIRMATION':('strong_run_in_sentiment_direction','opposite_colour_pause','complete_punch_sequence','following_confirmation_closed','entry_location','confirmation_near','confirmation_timely','confirmation_close','teacher_confirmation_reference'),
}

def read_csv(path,interval_seconds):
    if type(interval_seconds) is not int or interval_seconds<=0:raise ValueError('explicit interval required')
    data=Path(path).read_bytes();fingerprint=sha256(data).hexdigest()
    rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline='')))
    candles=tuple(Candle(int(r['time_raw_epoch']),int(r['time_raw_epoch'])+interval_seconds,
                        *(Decimal(r[k]) for k in ('open','high','low','close'))) for r in rows)
    # Validate the whole input once, without treating open bars as known.
    extract(candles,at=0,interval_seconds=interval_seconds)
    return candles,fingerprint

def required_for(rule,facts):
    keys=list(COMMON)+([] if rule.startswith('STOPPUNCH_') else list(FAMILY))+list(REQUIRED[rule])
    if rule=='BREAK_STRONG':
        kind=facts.get('level_kind')
        if kind is None:pass # geometry alternatives are inventoried separately until level kind is known
        elif kind.value in ('OB','FVG'):keys+=['zone_low','zone_high']
        else:keys+=['line_level']
    if rule.startswith('REVERSAL_') and facts.get('trend_strength',Fact('',0,'DIAGNOSTIC')).value=='STRONG':
        keys.append('teacher_prz_exception_confirmed')
    return tuple(dict.fromkeys(keys))

class RawPipeline:
    def __init__(self,plan_id,allowed_rules,interval_seconds,source_sha,contexts=()):
        if type(interval_seconds) is not int or interval_seconds<=0:raise ValueError('explicit interval required')
        if not isinstance(source_sha,str) or len(source_sha)!=64 or any(c not in '0123456789abcdef' for c in source_sha):
            raise ValueError('CSV SHA256 required')
        self.engine=Engine(plan_id,tuple(allowed_rules));self.interval=interval_seconds
        self.source='CSV_SHA256:'+source_sha;self.contexts=tuple(contexts);self.bars=[]
        self.last_observations=MappingProxyType({})
        self.context_fingerprint=sha256(json.dumps([
            {'valid_from':c.valid_from,'valid_until':c.valid_until,'known_at':c.known_at,
             'source':c.source,'facts':{k:{'type':type(v).__name__,'value':str(v)} for k,v in sorted(c.facts.items())}}
            for c in self.contexts],sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def latest_observation(self,side):
        if side not in ('BUY','SELL') or side not in self.last_observations:
            raise ValueError('processed raw candle and explicit side required')
        return self.last_observations[side]

    def step(self,bar):
        if not isinstance(bar,Candle):raise ValueError('Candle required')
        window=tuple(self.bars[-2:])+(bar,)
        raw=extract(window,at=bar.closed_at,interval_seconds=self.interval)
        at=bar.closed_at
        supplied=facts_as_of(self.contexts,at)
        g=geometry(bar);predicates=candle_predicates(bar)
        source=self.source+':'+str(bar.opened_at)
        generated={
            'candle_open':Fact(bar.open,at,source),'candle_high':Fact(bar.high,at,source),
            'candle_low':Fact(bar.low,at,source),'decision_close':Fact(bar.close,at,source),
            'decision_candle_closed':Fact(True,at,source),
            'body':Fact(g.body,at,source),'upper_wick':Fact(g.upper_wick,at,source),
            'lower_wick':Fact(g.lower_wick,at,source),'body_midpoint':Fact(g.body_midpoint,at,source),
            'candle_color':Fact(g.color,at,source),
        }
        unresolved={}
        for key,p in predicates.items():
            if p.value is not None:generated[key]=Fact(p.value,at,source+':TEACHER:'+str(p.sources))
            else:unresolved[key]=p.reason
        if len(window)==3 and not raw['gaps']:
            colors=[geometry(c).color for c in window]
            generated['three_up_raw']=Fact(all(c=='UP' for c in colors),at,source)
            generated['three_down_raw']=Fact(all(c=='DOWN' for c in colors),at,source)
        for k in generated.keys() & supplied.keys():
            if generated[k].value!=supplied[k].value:raise ValueError('context conflicts with measured fact: '+k)
        facts={**supplied,**generated}
        decisions=[];observations={}
        for side,direction in (('BUY','UP'),('SELL','DOWN')):
            sf=dict(facts)
            # A downward fullbody above a level is not a BUY breakout candle.
            if 'fullbody_or_marubozu' in sf and sf['fullbody_or_marubozu'].value is True and g.color!=direction:
                sf['fullbody_or_marubozu']=Fact(False,at,source+':CANDLE_DIRECTION_MISMATCH_FOR_'+side)
            key='three_up_raw' if side=='BUY' else 'three_down_raw'
            if key in facts:sf['three_same_direction_sequence']=facts[key]
            o=Observation(side,at,sf);observations[side]=o
            for rule in self.engine.allowed_rules:
                decision=self.engine.evaluate(rule,o)
                required=required_for(rule,sf)
                absent=[k for k in required if k not in sf]
                future=[k for k in required if k in sf and sf[k].known_at>at]
                decisions.append({**asdict(decision),'side':side,'missing_dependencies':absent,
                    'future_dependencies':future,'supplied_context_keys':sorted(supplied),
                    'derived_required_keys':[k for k in required if k in generated or k=='three_same_direction_sequence' and key in facts],
                    'context_required_keys':[k for k in required if k in supplied and k not in generated],
                    'dependency_facts':{k:{'value':f.value,'type':type(f.value).__name__,
                        'known_at':f.known_at,'source':f.source,
                        'origin':'DERIVED_FROM_RAW' if k in generated or k=='three_same_direction_sequence' and key in facts else 'SOURCED_CONTEXT'}
                        for k,f in sf.items() if k in required},
                    'unresolved_reference_alternatives':(['zone_low+zone_high','line_level'] if rule=='BREAK_STRONG' and 'level_kind' not in sf else []),
                    'dependency_inventory_is_entry_coverage_not_proof_of_eligibility':True})
        self.bars.append(bar)
        self.last_observations=MappingProxyType(observations)
        return {'at':at,'bar_opened_at':bar.opened_at,'geometry':asdict(g),
                'context_fingerprint':self.context_fingerprint,
                'active_context_windows':[{'valid_from':c.valid_from,'valid_until':c.valid_until,
                    'known_at':c.known_at,'source':c.source} for c in self.contexts
                    if c.known_at<=at and c.valid_from<=at<c.valid_until],
                'raw_parent_candles':[asdict(c) for c in window],
                'predicates':{k:asdict(v) for k,v in predicates.items()},
                'unresolved_shape_interpretations':unresolved,
                'new_candidates':[asdict(c) for c in raw['candidates'] if c.known_at==at],
                'gap_before_bar':bool(len(window)>1 and window[-2].closed_at!=bar.opened_at),
                'decisions':decisions,'orders_sent':0,'broker_connected':False}
