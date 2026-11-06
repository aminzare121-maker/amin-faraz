"""Independent offline executor of source-indexed Artin entry conditions.

This module does not classify raw candles as strong/doji/PRZ. Those observations
must be supplied with their source and available-at time. It never places orders.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping

RULE_IDS=(
 'PULLBACK_STANDARD','REVERSAL_CLASSIC','REVERSAL_THREE','REVERSAL_STAR',
 'BREAK_STRONG','BREAK_WEAK_PIVOT','BREAK_WEAK_FULLBODY_EXCEPTION',
 'BREAK_VERY_STRONG_RETEST','STOPPUNCH_SAME_COLOUR','STOPPUNCH_DOJI_AHEAD',
 'STOPPUNCH_DOJI_TIED','STOPPUNCH_OPPOSITE_CONFIRMATION','STOPPUNCH_S22_SELL_CONFIRMED_PAUSE')
SOURCES={
 'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE':((22,1888.1,1952.66),),
 'PULLBACK_STANDARD':((16,615,854),(16,1003,1109)),
 'REVERSAL_CLASSIC':((20,2188.86,2306.84),(20,2660.22,3255.4)),
 'REVERSAL_THREE':((20,2660.22,3255.4),(20,3440.82,4048.72)),
 'REVERSAL_STAR':((20,3440.82,4048.72),(20,4117.72,4483.72)),
 'BREAK_STRONG':((21,2105.04,2261),(21,2274,2649.38)),
 'BREAK_WEAK_PIVOT':((21,2770.48,3153.16),),
 'BREAK_WEAK_FULLBODY_EXCEPTION':((21,2770.48,3153.16),),
 'BREAK_VERY_STRONG_RETEST':((21,3162.56,3473.88),),
 'STOPPUNCH_SAME_COLOUR':((21,3947,3975),(21,4201.30,4208.84),(21,4597,4661)),
 'STOPPUNCH_DOJI_AHEAD':((21,3984.88,4068.98),(21,4210.14,4214.52)),
 'STOPPUNCH_DOJI_TIED':((21,3984.88,4068.98),(21,4210.14,4214.52)),
 'STOPPUNCH_OPPOSITE_CONFIRMATION':((21,4100,4133),(21,4214.52,4223.26),(23,4694,4728))}

@dataclass(frozen=True)
class Fact:
    value: object
    known_at: int
    source: str
    def __post_init__(self):
        if type(self.known_at) is not int or self.known_at<0:
            raise ValueError('Fact known_at must be a nonnegative integer')
        if not isinstance(self.source,str) or not self.source.strip():
            raise ValueError('Fact requires an observation source')
        if type(self.value) not in (bool,str,int,Decimal):
            raise ValueError('Fact type must be bool, string, integer or Decimal; no binary float')

@dataclass(frozen=True)
class Observation:
    side: str
    at: int
    facts: Mapping[str,Fact]
    def __post_init__(self):
        if self.side not in ('BUY','SELL') or type(self.at) is not int or self.at<0:
            raise ValueError('Explicit side and nonnegative decision time required')
        if not all(isinstance(k,str) and isinstance(v,Fact) for k,v in self.facts.items()):
            raise ValueError('Observation facts must be sourced Fact objects')
        object.__setattr__(self,'facts',MappingProxyType(dict(self.facts)))

@dataclass(frozen=True)
class Decision:
    rule_id: str
    status: str
    reasons: tuple
    sources: tuple
    input_fingerprint: str
    order_created: bool=False

class _Condition(Exception):
    def __init__(self,status,reason):self.status=status;self.reason=reason

class _Reader:
    def __init__(self,observation):self.o=observation;self.used={}
    def value(self,key):
        f=self.o.facts.get(key)
        if f is None:raise _Condition('REVIEW','MISSING:'+key)
        if f.known_at>self.o.at:raise _Condition('REVIEW','FUTURE_INFORMATION:'+key)
        self.used[key]=f
        return f.value
    def yes(self,key,status='WAIT',reason=None):
        v=self.value(key)
        if type(v) is not bool:raise _Condition('REVIEW','INVALID_BOOLEAN:'+key)
        if not v:raise _Condition(status,reason or 'NOT_COMPLETE:'+key)
    def label(self,key,allowed,status='REVIEW',reason=None):
        v=self.value(key)
        if not isinstance(v,str):raise _Condition('REVIEW','INVALID_LABEL:'+key)
        if v not in allowed:raise _Condition(status,reason or 'UNSUPPORTED_LABEL:'+key)
        return v
    def number(self,key):
        v=self.value(key)
        if type(v) not in (str,int,Decimal):raise _Condition('REVIEW','INVALID_NUMBER:'+key)
        try:n=Decimal(v)
        except (InvalidOperation,ValueError):raise _Condition('REVIEW','INVALID_NUMBER:'+key)
        if not n.is_finite() or n<=0:raise _Condition('REVIEW','INVALID_NUMBER:'+key)
        return n

@dataclass(frozen=True)
class Engine:
    plan_id: str
    allowed_rules: tuple
    def __post_init__(self):
        if not isinstance(self.plan_id,str) or not self.plan_id.strip():raise ValueError('Explicit plan id required')
        if type(self.allowed_rules) is not tuple or not self.allowed_rules or len(set(self.allowed_rules))!=len(self.allowed_rules):
            raise ValueError('Explicit unique tuple of allowed rules required')
        if any(x not in RULE_IDS for x in self.allowed_rules):raise ValueError('Unknown rule in plan')
    @property
    def fingerprint(self):
        return sha256(json.dumps([self.plan_id,self.allowed_rules],ensure_ascii=False).encode()).hexdigest()
    def evaluate(self,rule_id,observation):
        if not isinstance(observation,Observation):raise ValueError('Observation required')
        reader=_Reader(observation)
        try:
            if rule_id not in self.allowed_rules:raise _Condition('REJECT','RULE_NOT_IN_FIXED_PLAN')
            bias=reader.label('sentiment_permission',('LONG_ONLY','SHORT_ONLY','TWO_SIDED','UNKNOWN'))
            if bias=='UNKNOWN':
                # S09 fixed-symbol fallback is an explicit analysis state, not
                # a silent conversion of absent economic data into permission.
                state=reader.label('direction_assessment',('REVIEWED_INCONCLUSIVE','MISSING_DATA','NOT_REVIEWED'))
                if state!='REVIEWED_INCONCLUSIVE':raise _Condition('REVIEW','SENTIMENT_NOT_ESTABLISHED')
                reader.yes('fixed_symbol_analysis','REVIEW','FIXED_SYMBOL_FALLBACK_NOT_APPLICABLE')
                reader.yes('teacher_two_sided_branch_selected','REVIEW','TWO_SIDED_BRANCH_NOT_SELECTED')
                bias='TWO_SIDED'
            if (bias=='LONG_ONLY' and observation.side!='BUY') or (bias=='SHORT_ONLY' and observation.side!='SELL'):
                raise _Condition('REJECT','DIRECTION_NOT_PERMITTED')
            reader.yes('current_setup','REJECT','HISTORICAL_SETUP_NOT_FRESH')
            self._family_admission(rule_id,reader)
            self._entry(rule_id,reader)
            status,reasons='ELIGIBLE',('SOURCE_CONDITIONS_SATISFIED_ON_SUPPLIED_OBSERVATIONS',)
            if rule_id=='STOPPUNCH_S22_SELL_CONFIRMED_PAUSE':
                reasons=('EXPLICIT_S22_HYPOTHESIS_CONDITIONS_SATISFIED_NOT_VERIFIED_TEACHER_FORMULA',)
        except _Condition as e:status,reasons=e.status,(e.reason,)
        fingerprint=sha256(json.dumps({'plan':self.fingerprint,'rule':rule_id,'side':observation.side,'at':observation.at,
          'used':{k:{'value':str(v.value),'type':type(v.value).__name__,'known_at':v.known_at,'source':v.source} for k,v in sorted(reader.used.items())}},
          sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        sources=list(SOURCES.get(rule_id,()))
        if 'current_setup' in reader.used:sources.append((15,2836,2897))
        if 'trend_strength' in reader.used:sources.append((14,3111,3415))
        if 'teacher_prz_exception_confirmed' in reader.used:sources.append((15,3443,3512))
        if 'direction_assessment' in reader.used:sources.extend(((9,253,278.12),(9,363.64,387.96),(9,591.16,640)))
        return Decision(rule_id,status,reasons,tuple(sources),fingerprint)

    def _family_admission(self,rule,r):
        # Session14 trendline selector is context-limited by the session15 PRZ exception.
        # It is not imposed on the separately introduced personal StopPunch models.
        if rule.startswith('STOPPUNCH_'):return
        context=r.label('family_selection_context',('TRENDLINE_ONLY','ZONE_CONTEXT'))
        if context=='ZONE_CONTEXT' and rule.startswith('BREAK_'):
            # S21:2387..2649 is the local zone-break candle branch. Do not add
            # the separate trendline-strength selector as another global veto.
            return
        strength=r.label('trend_strength',('WEAK','NORMAL','STRONG','NO_CONFIRMED_TREND'))
        reversal=rule.startswith('REVERSAL_')
        if reversal and strength=='STRONG':
            r.yes('teacher_prz_exception_confirmed','REJECT','STRONG_TREND_REVERSAL_REQUIRES_SOURCED_PRZ_EXCEPTION')
        elif not reversal and strength=='WEAK' and context=='TRENDLINE_ONLY':
            raise _Condition('REJECT','WEAK_TRENDLINE_CONTEXT_NOT_BREAKOUT_FAMILY')
        elif strength=='NO_CONFIRMED_TREND' and context=='TRENDLINE_ONLY':
            raise _Condition('REVIEW','DO_NOT_FORCE_AN_ABSENT_TRENDLINE')

    def _entry(self,rule,r):
        def require(*keys):
            for key in keys:r.yes(key)
        def beyond(close,level):
            a,b=r.number(close),r.number(level)
            if not(a>b if r.o.side=='BUY' else a<b):raise _Condition('WAIT','CLOSE_NOT_BEYOND_REFERENCE')
        if rule=='PULLBACK_STANDARD':
            require('break_occurred','post_break_pivot_confirmed','retest_confirmed','decision_candle_closed')
            beyond('decision_close','post_break_pivot_level');return
        if rule.startswith('REVERSAL_'):
            require('zone_context','reversal_relative_to_last_leg','decision_candle_closed')
            if rule=='REVERSAL_CLASSIC':require('doubt_confirmed','first_confidence_confirmed')
            elif rule=='REVERSAL_THREE':require('three_same_direction_sequence','doubt_confidence_condition','half_leg_condition')
            elif rule=='REVERSAL_STAR':require('star_sequence','body_penetration_condition','half_leg_condition')
            # No universal strong-trend veto: session15 explicitly supplies a PRZ exception.
            return
        if rule=='BREAK_STRONG':
            r.label('break_strength',('STRONG',),'WAIT');require('fullbody_or_marubozu','decision_candle_closed')
            kind=r.label('level_kind',('OB','FVG','PIVOT','LIQUIDITY'))
            close=r.number('decision_close')
            if kind in ('OB','FVG'):
                low,high=r.number('zone_low'),r.number('zone_high')
                if low>high:raise _Condition('REVIEW','INVALID_ZONE_BOUNDS')
                level=high if r.o.side=='BUY' else low
            else:level=r.number('line_level')
            if not(close>level if r.o.side=='BUY' else close<level):raise _Condition('WAIT','CLOSE_NOT_BEYOND_FAR_EDGE')
            return
        if rule=='BREAK_WEAK_PIVOT':
            r.label('break_strength',('WEAK',),'WAIT');require('pullback_confirmed','post_break_pivot_confirmed','decision_candle_closed')
            beyond('decision_close','post_break_pivot_level');return
        if rule=='BREAK_WEAK_FULLBODY_EXCEPTION':
            r.label('break_strength',('WEAK',),'WAIT');require('pullback_confirmed','fullbody_or_marubozu','fullbody_exception_context','decision_candle_closed');return
        if rule=='BREAK_VERY_STRONG_RETEST':
            r.label('break_strength',('VERY_STRONG',),'WAIT')
            r.yes('not_chasing','REJECT','CHASING_MOVE_NOT_ALLOWED')
            opening,closing=r.number('reference_body_open'),r.number('reference_body_close')
            if opening==closing:raise _Condition('REVIEW','REFERENCE_BODY_EMPTY')
            if not(closing>opening if r.o.side=='BUY' else closing<opening):raise _Condition('REVIEW','REFERENCE_BODY_DIRECTION_MISMATCH')
            midpoint=(opening+closing)/Decimal(2)
            lo,hi=r.number('retouch_low'),r.number('retouch_high')
            if lo>hi:raise _Condition('REVIEW','INVALID_RETOUCH_RANGE')
            if not lo<=midpoint<=hi:raise _Condition('WAIT','HALF_BODY_NOT_TOUCHED')
            return # No demand for a new candle close in this specific teacher branch.
        if rule.startswith('STOPPUNCH_'):
            if rule=='STOPPUNCH_S22_SELL_CONFIRMED_PAUSE':
                if r.o.side!='SELL':raise _Condition('REVIEW','S22_CASE_BUY_MAPPING_NOT_SELECTED')
                r.label('teacher_model_variant',('S22_AFTER_BREAK_CONFIRMED_PAUSE',))
                r.label('confirmation_reference_kind',('PAUSE_BODY_CLOSE_HYPOTHESIS','PAUSE_WICK_LOW_HYPOTHESIS'))
                anchors={k:r.value(k) for k in ('run_break_closed_at','pause_opened_at','pause_closed_at',
                    'confirmation_opened_at','confirmation_closed_at')}
                if any(type(v) is not int or v<0 for v in anchors.values()):
                    raise _Condition('REVIEW','INVALID_S22_ROLE_CLOCK')
                if not (anchors['run_break_closed_at']<=anchors['pause_opened_at']<anchors['pause_closed_at']
                        ==anchors['confirmation_opened_at']<anchors['confirmation_closed_at']<=r.o.at):
                    raise _Condition('REVIEW','S22_ROLE_CLOCK_NOT_CAUSAL')
                r.yes('strong_run_in_sentiment_direction')
                if any(r.used[k].known_at>anchors['pause_opened_at'] for k in
                       ('teacher_model_variant','confirmation_reference_kind','run_break_closed_at','strong_run_in_sentiment_direction')):
                    raise _Condition('REVIEW','S22_PLAN_OR_RUN_SELECTED_AFTER_PAUSE')
                if r.used['run_break_closed_at'].known_at<anchors['run_break_closed_at']:
                    raise _Condition('REVIEW','S22_BREAK_KNOWN_BEFORE_OCCURRENCE')
                require('strong_run_in_sentiment_direction','break_before_pause','pause_doubt_confirmed','pause_in_run_direction',
                        'confirmation_in_run_direction',
                        'following_confirmation_closed','confirmation_timely')
                r.value('confirmation_close')
                if r.used['confirmation_close'].known_at<anchors['confirmation_closed_at']:
                    raise _Condition('REVIEW','S22_CLOSE_KNOWN_BEFORE_COMPLETION')
                operand_key=('pause_body_close' if r.used['confirmation_reference_kind'].value=='PAUSE_BODY_CLOSE_HYPOTHESIS'
                             else 'pause_wick_low')
                selected=r.number(operand_key);reference=r.number('teacher_confirmation_reference')
                if reference!=selected:
                    raise _Condition('REVIEW','S22_REFERENCE_DOES_NOT_MATCH_SELECTED_OPERAND')
                if any(r.used[k].known_at<anchors['pause_closed_at'] for k in (operand_key,'teacher_confirmation_reference')):
                    raise _Condition('REVIEW','S22_PAUSE_PRICE_KNOWN_BEFORE_COMPLETION')
                beyond('confirmation_close','teacher_confirmation_reference');return
            if r.o.side!='BUY':raise _Condition('REVIEW','SELL_FORM_MAPPING_NOT_ESTABLISHED_IN_REVIEWED_EXAMPLES')
            require('strong_run_in_sentiment_direction')
            if rule=='STOPPUNCH_SAME_COLOUR':
                require('zone_context','same_colour_pause','pause_candle_closed');return
            if rule in ('STOPPUNCH_DOJI_AHEAD','STOPPUNCH_DOJI_TIED'):
                require('zone_context','doji_confirmed')
                state=r.label('day_analysis_state',('AHEAD_BY_COUNT','TIED_BY_COUNT','BEHIND_BY_COUNT','START_OF_DAY','UNKNOWN'))
                if state in ('BEHIND_BY_COUNT','START_OF_DAY','UNKNOWN'):
                    raise _Condition('REVIEW','DAY_BRANCH_NOT_EXTRACTED_NOT_A_TEACHER_VETO')
                expected='AHEAD_BY_COUNT' if rule.endswith('AHEAD') else 'TIED_BY_COUNT'
                if state!=expected:raise _Condition('REJECT','WRONG_DAY_BRANCH')
                if rule.endswith('AHEAD'):require('doji_candle_closed');return
                require('following_confirmation_closed')
                r.yes('confirmation_near','REJECT','CONFIRMATION_TOO_FAR')
                r.yes('confirmation_timely','REJECT','CONFIRMATION_TOO_LATE')
                beyond('confirmation_close','doji_shadow_high');return
            if rule=='STOPPUNCH_OPPOSITE_CONFIRMATION':
                require('opposite_colour_pause','complete_punch_sequence','following_confirmation_closed')
                r.label('entry_location',('AT_ZONE','BETWEEN_PREEXISTING_ZONES'))
                r.yes('confirmation_near','REJECT','CONFIRMATION_TOO_FAR')
                r.yes('confirmation_timely','REJECT','CONFIRMATION_TOO_LATE')
                beyond('confirmation_close','teacher_confirmation_reference');return
        raise _Condition('REVIEW','RULE_IMPLEMENTATION_MISSING')
