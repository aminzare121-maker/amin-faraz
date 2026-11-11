"""CSV -> causal measurements -> teacher predicates -> sourced context -> entry.

The pipeline does not turn a raw FVG into an accepted zone or body colour into
economic bias. Every decision includes all absent dependencies, even when the
entry evaluator exits at its first gate. Missing data is never a negative setup.
"""
import csv,io,json
from dataclasses import asdict
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from entry_engine import Engine,Fact,Observation,RULE_IDS
from raw_geometry import Candle,extract,geometry
from teacher_features import candle_predicates
from context_inputs import facts_as_of
from zone_behavior import ZoneBehavior
from punch_behavior import derive as derive_punch
from pullback_bridge import ClosedPullbackBridge
from confirmed_pause import derive as derive_confirmed_pause,ROLE_KEYS as CONFIRMED_PAUSE_ROLE_KEYS
from relative_sequence import measure as measure_sequence

COMMON=('sentiment_permission','current_setup')
FAMILY=('family_selection_context','trend_strength')
REQUIRED={
 'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE':('teacher_model_variant','strong_run_in_sentiment_direction',
    'run_break_closed_at','confirmation_reference_kind','pause_opened_at','pause_closed_at','confirmation_opened_at','confirmation_closed_at','pause_body_close','pause_wick_low',
    'break_before_pause','pause_doubt_confirmed','pause_in_run_direction','confirmation_in_run_direction','following_confirmation_closed','confirmation_timely',
    'confirmation_close','teacher_confirmation_reference'),
 'PULLBACK_STANDARD':('break_occurred','post_break_pivot_confirmed','retest_confirmed','decision_candle_closed','decision_close','post_break_pivot_level'),
 'REVERSAL_CLASSIC':('zone_context','reversal_relative_to_last_leg','decision_candle_closed','doubt_confirmed','first_confidence_confirmed'),
 'REVERSAL_THREE':('zone_context','reversal_relative_to_last_leg','decision_candle_closed','three_doubt_in_sentiment_sequence','doubt_confidence_condition','half_leg_condition','three_sequence_pivot_confirmed'),
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
    if rule.startswith('BREAK_') and facts.get('family_selection_context',Fact('',0,'DIAGNOSTIC')).value=='ZONE_CONTEXT':
        keys=[k for k in keys if k!='trend_strength']
    if facts.get('sentiment_permission',Fact('',0,'DIAGNOSTIC')).value=='UNKNOWN':
        keys+=['direction_assessment','fixed_symbol_analysis','teacher_two_sided_branch_selected']
    if rule=='BREAK_STRONG':
        kind=facts.get('level_kind')
        if kind is None:pass # geometry alternatives are inventoried separately until level kind is known
        elif kind.value in ('OB','FVG'):keys+=['zone_low','zone_high']
        else:keys+=['line_level']
    if rule.startswith('REVERSAL_') and facts.get('trend_strength',Fact('',0,'DIAGNOSTIC')).value=='STRONG':
        keys.append('teacher_prz_exception_confirmed')
    return tuple(dict.fromkeys(keys))

class RawPipeline:
    def __init__(self,plan_id,allowed_rules,interval_seconds,source_sha,contexts=(),direction_plan=None):
        if type(interval_seconds) is not int or interval_seconds<=0:raise ValueError('explicit interval required')
        if not isinstance(source_sha,str) or len(source_sha)!=64 or any(c not in '0123456789abcdef' for c in source_sha):
            raise ValueError('CSV SHA256 required')
        self.engine=Engine(plan_id,tuple(allowed_rules));self.interval=interval_seconds
        self.source='CSV_SHA256:'+source_sha;self.contexts=tuple(contexts);self.bars=[]
        self.direction_plan=direction_plan
        self.direction_plan_fingerprint=None if direction_plan is None else direction_plan.fingerprint
        self.last_observations=MappingProxyType({})
        self.branch_observations=MappingProxyType({});self.behavior=ZoneBehavior(interval_seconds,self.source)
        self.pullbacks=ClosedPullbackBridge(interval_seconds,self.source)
        self.context_fingerprint=sha256(json.dumps([
            {'valid_from':c.valid_from,'valid_until':c.valid_until,'known_at':c.known_at,
             'source':c.source,'facts':{k:{'type':type(v).__name__,'value':str(v)} for k,v in sorted(c.facts.items())}}
            for c in self.contexts],sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def latest_observation(self,side,rule_id=None):
        if side not in ('BUY','SELL') or side not in self.last_observations:
            raise ValueError('processed raw candle and explicit side required')
        return self.branch_observations[(side,rule_id)] if rule_id is not None else self.last_observations[side]

    def step(self,bar):
        if not isinstance(bar,Candle):raise ValueError('Candle required')
        window=tuple(self.bars[-2:])+(bar,)
        raw=extract(window,at=bar.closed_at,interval_seconds=self.interval)
        # Advance behaviour only after raw validation and context validation below.
        at=bar.closed_at
        supplied=facts_as_of(self.contexts,at)
        seq=measure_sequence(tuple(self.bars),bar,supplied.get('sequence_start_opened_at'),self.source,at,self.interval)
        # Exact JSON rational values; these measurements are deliberately not
        # promoted into strong/very-strong entry facts.
        sequence_measurement={k:({'numerator':v.numerator,'denominator':v.denominator}
                                if isinstance(v,Fraction) else v) for k,v in seq.items()}
        context_keys=tuple(supplied)
        if (None if self.direction_plan is None else self.direction_plan.fingerprint)!=self.direction_plan_fingerprint:
            raise ValueError('predeclared direction plan changed during replay')
        policy={} if self.direction_plan is None else self.direction_plan.derive(supplied,at)
        original_direction=supplied.get('sentiment_permission')
        supplied={**supplied,**policy}
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
        pending_behavior=self.behavior.fork()
        behavior_events=pending_behavior.step(bar)
        pending_pullbacks=self.pullbacks.fork()
        pullback_events=pending_pullbacks.step(bar,behavior_events)
        decisions=[];observations={};branch_observations={}
        for side,direction in (('BUY','UP'),('SELL','DOWN')):
            sf=dict(facts)
            # A downward fullbody above a level is not a BUY breakout candle.
            if 'fullbody_or_marubozu' in sf and sf['fullbody_or_marubozu'].value is True and g.color!=direction:
                sf['fullbody_or_marubozu']=Fact(False,at,source+':CANDLE_DIRECTION_MISMATCH_FOR_'+side)
            key='three_up_raw' if side=='BUY' else 'three_down_raw'
            if key in facts:sf['three_same_direction_sequence']=facts[key]
            o=Observation(side,at,sf);observations[side]=o
            for rule in self.engine.allowed_rules:
                rf=dict(sf);behavior_facts={};punch={};behavior_status='NOT_A_ZONE_BREAK_BRANCH'
                if rule=='REVERSAL_THREE' and len(window)==3 and not raw['gaps']:
                    # S19 3500.82..3519: at least ONE of three candles in
                    # sentiment direction is doubt (not all same-direction).
                    # Do not force uncertain body-vs-shadow classifications.
                    aligned=[c for c in window if geometry(c).color==direction]
                    values=[candle_predicates(c)['doubt_shape'].value for c in aligned]
                    shape=(True if True in values else False if not aligned or all(v is False for v in values) else None)
                    if shape is not None:
                        rf['three_doubt_in_sentiment_sequence']=Fact(shape,at,
                            source+':OHLC:S19_3500.82_3519_MACHINE_UNVERIFIED')
                        behavior_facts['three_doubt_in_sentiment_sequence']=rf['three_doubt_in_sentiment_sequence']
                if rule.startswith('BREAK_') and 'level_kind' not in supplied:
                    behavior_facts,behavior_status=pending_behavior.reference_facts(behavior_events,side,at)
                    for k,f in behavior_facts.items():
                        if k in supplied and supplied[k].value!=f.value:raise ValueError('context conflicts with raw reference: '+k)
                    rf.update(behavior_facts)
                if rule in ('STOPPUNCH_DOJI_AHEAD','STOPPUNCH_DOJI_TIED','STOPPUNCH_OPPOSITE_CONFIRMATION'):
                    if rule=='STOPPUNCH_DOJI_TIED':
                        # Generic shape belongs to current candle, not the previous
                        # pause. Explicit near-zero pause labels need timestamp binding.
                        rf.pop('doji_confirmed',None)
                    if rule=='STOPPUNCH_OPPOSITE_CONFIRMATION':
                        for k in ('opposite_colour_pause','following_confirmation_closed','confirmation_close',
                                  'teacher_confirmation_reference','confirmation_timely','current_setup','complete_punch_sequence'):
                            rf.pop(k,None)
                    punch=derive_punch(rule,side,window,rf,raw_source=self.source)
                    for k,f in punch.items():
                        if k in supplied and supplied[k].value!=f.value:raise ValueError('context conflicts with raw punch role: '+k)
                    rf.update(punch);behavior_facts={**behavior_facts,**punch}
                if rule=='STOPPUNCH_S22_SELL_CONFIRMED_PAUSE':
                    # No supplied role fallback when the raw chain is unknown.
                    for k in CONFIRMED_PAUSE_ROLE_KEYS:rf.pop(k,None)
                    punch=derive_confirmed_pause(side,window,rf,raw_source=self.source)
                    for k,f in punch.items():
                        if k in supplied and supplied[k].value!=f.value:
                            raise ValueError('context conflicts with measured S22 role: '+k)
                    rf.update(punch);behavior_facts={**behavior_facts,**punch}
                ro=Observation(side,at,rf);branch_observations[(side,rule)]=ro
                decision=self.engine.evaluate(rule,ro)
                required=required_for(rule,rf)
                absent=[k for k in required if k not in rf]
                future=[k for k in required if k in rf and rf[k].known_at>at]
                decisions.append({**asdict(decision),'side':side,'missing_dependencies':absent,
                    'future_dependencies':future,'supplied_context_keys':sorted(context_keys),
                    'behavior_status':behavior_status,
                    'punch_role_chain_status':None if 'punch_role_chain_status' not in punch else punch['punch_role_chain_status'].value,
                    'derived_required_keys':[k for k in required if k in rf and (k in generated or k in behavior_facts or k=='three_same_direction_sequence' and key in facts)],
                    'context_required_keys':[k for k in required if k in rf and k in supplied and k not in policy and k not in generated and k not in behavior_facts],
                    'policy_required_keys':[k for k in required if k in rf and k in policy],
                    'dependency_facts':{k:{'value':f.value,'type':type(f.value).__name__,
                        'known_at':f.known_at,'source':f.source,
                        'origin':'DECLARED_RESEARCH_POLICY' if k in policy else 'DERIVED_MIXED' if k in punch else 'DERIVED_FROM_RAW' if k in generated or k in behavior_facts or k=='three_same_direction_sequence' and key in facts else 'SOURCED_CONTEXT'}
                        for k,f in rf.items() if k in required},
                    'behavior_parent_facts':{k:{'value':v.value,'known_at':v.known_at,'source':v.source}
                        for k,v in supplied.items() if punch and k in ('day_correct_count','day_incorrect_count',
                            'confirmation_region_low','confirmation_region_high','zone_low','zone_high',
                            'reference_zone_validated','pause_doji_classified','pause_candle_opened_at',
                            'teacher_model_variant','run_break_closed_at','strong_run_in_sentiment_direction','punch_run_end_opened_at')},
                    'unresolved_reference_alternatives':(['zone_low+zone_high','line_level'] if rule=='BREAK_STRONG' and 'level_kind' not in rf else []),
                    'dependency_inventory_is_entry_coverage_not_proof_of_eligibility':True})
        self.bars.append(bar)
        self.behavior=pending_behavior
        self.pullbacks=pending_pullbacks
        self.last_observations=MappingProxyType(observations)
        self.branch_observations=MappingProxyType(branch_observations)
        return {'at':at,'bar_opened_at':bar.opened_at,'geometry':asdict(g),
                'relative_sequence_measurement':sequence_measurement,
                'context_fingerprint':self.context_fingerprint,
                'direction_plan':None if self.direction_plan is None else self.direction_plan.serialize(),
                'original_direction_evidence':None if original_direction is None else {'value':original_direction.value,
                    'known_at':original_direction.known_at,'source':original_direction.source},
                'behavior_events':behavior_events,
                'pullback_core_candidates':pullback_events,
                'active_context_windows':[{'valid_from':c.valid_from,'valid_until':c.valid_until,
                    'known_at':c.known_at,'source':c.source} for c in self.contexts
                    if c.known_at<=at and c.valid_from<=at<c.valid_until],
                'raw_parent_candles':[asdict(c) for c in window],
                'predicates':{k:asdict(v) for k,v in predicates.items()},
                'unresolved_shape_interpretations':unresolved,
                'new_candidates':[asdict(c) for c in raw['candidates'] if c.known_at==at],
                'gap_before_bar':bool(len(window)>1 and window[-2].closed_at!=bar.opened_at),
                'decisions':decisions,'orders_sent':0,'broker_connected':False}