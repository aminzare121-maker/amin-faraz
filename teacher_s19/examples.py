"""Wholly synthetic observations for checking code, not market/teacher fills."""
from entry_engine import RULE_IDS

def demo_document():
    common={'sentiment_permission':'LONG_ONLY','current_setup':True,
            'family_selection_context':'ZONE_CONTEXT','trend_strength':'NORMAL'}
    specifics={
      'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE':dict(sentiment_permission='SHORT_ONLY',teacher_model_variant='S22_AFTER_BREAK_CONFIRMED_PAUSE',strong_run_in_sentiment_direction=True,break_before_pause=True,pause_doubt_confirmed=True,pause_in_run_direction=True,confirmation_in_run_direction=True,following_confirmation_closed=True,confirmation_timely=True,confirmation_close='98',teacher_confirmation_reference='99'),
      'PULLBACK_STANDARD':dict(break_occurred=True,post_break_pivot_confirmed=True,retest_confirmed=True,decision_candle_closed=True,decision_close='102',post_break_pivot_level='101'),
      'REVERSAL_CLASSIC':dict(zone_context=True,reversal_relative_to_last_leg=True,decision_candle_closed=True,doubt_confirmed=True,first_confidence_confirmed=True),
      'REVERSAL_THREE':dict(zone_context=True,reversal_relative_to_last_leg=True,decision_candle_closed=True,three_doubt_in_sentiment_sequence=True,doubt_confidence_condition=True,half_leg_condition=True,three_sequence_pivot_confirmed=True),
      'REVERSAL_STAR':dict(zone_context=True,reversal_relative_to_last_leg=True,decision_candle_closed=True,star_sequence=True,body_penetration_condition=True,half_leg_condition=True),
      'BREAK_STRONG':dict(break_strength='STRONG',fullbody_or_marubozu=True,decision_candle_closed=True,level_kind='FVG',zone_low='99',zone_high='101',decision_close='102'),
      'BREAK_WEAK_PIVOT':dict(break_strength='WEAK',pullback_confirmed=True,post_break_pivot_confirmed=True,decision_candle_closed=True,decision_close='102',post_break_pivot_level='101'),
      'BREAK_WEAK_FULLBODY_EXCEPTION':dict(break_strength='WEAK',pullback_confirmed=True,fullbody_or_marubozu=True,fullbody_exception_context=True,decision_candle_closed=True),
      'BREAK_VERY_STRONG_RETEST':dict(break_strength='VERY_STRONG',not_chasing=True,reference_body_open='100',reference_body_close='104',retouch_low='101.9',retouch_high='102.1'),
      'STOPPUNCH_SAME_COLOUR':dict(strong_run_in_sentiment_direction=True,zone_context=True,same_colour_pause=True,pause_candle_closed=True),
      'STOPPUNCH_DOJI_AHEAD':dict(strong_run_in_sentiment_direction=True,zone_context=True,doji_confirmed=True,day_analysis_state='AHEAD_BY_COUNT',doji_candle_closed=True),
      'STOPPUNCH_DOJI_TIED':dict(strong_run_in_sentiment_direction=True,zone_context=True,doji_confirmed=True,day_analysis_state='TIED_BY_COUNT',following_confirmation_closed=True,confirmation_near=True,confirmation_timely=True,confirmation_close='102',doji_shadow_high='101'),
      'STOPPUNCH_OPPOSITE_CONFIRMATION':dict(strong_run_in_sentiment_direction=True,opposite_colour_pause=True,complete_punch_sequence=True,following_confirmation_closed=True,entry_location='BETWEEN_PREEXISTING_ZONES',confirmation_near=True,confirmation_timely=True,confirmation_close='102',teacher_confirmation_reference='101')}
    document={'mode':'ANNOTATED_OFFLINE','plan_id':'synthetic-source-condition-check',
      'allowed_rules':list(RULE_IDS),'synthetic_only':True,
      'cases':[{'rule_id':rule,'side':'SELL' if rule=='STOPPUNCH_S22_SELL_CONFIRMED_PAUSE' else 'BUY','at':100,
        'facts':{key:{'value':value,'known_at':100,'source':'SYNTHETIC_TEST_NOT_A_TEACHER_OR_MARKET_OBSERVATION'}
                 for key,value in {**common,**specifics[rule]}.items()}} for rule in RULE_IDS]}
    s22=next(c for c in document['cases'] if c['rule_id']=='STOPPUNCH_S22_SELL_CONFIRMED_PAUSE')
    for k,v in dict(confirmation_reference_kind='PAUSE_WICK_LOW_HYPOTHESIS',run_break_closed_at=40,
                   pause_opened_at=40,pause_closed_at=70,confirmation_opened_at=70,confirmation_closed_at=100,
                   pause_body_close='100',pause_wick_low='99').items():
        s22['facts'][k]={'value':v,'known_at':100,'source':'SYNTHETIC_ROLE_CLOCK_FIXTURE'}
    for k in ('confirmation_reference_kind','run_break_closed_at','teacher_model_variant','strong_run_in_sentiment_direction'):
        s22['facts'][k]['known_at']=0
    s22['facts']['run_break_closed_at']['known_at']=40
    s22['facts']['strong_run_in_sentiment_direction']['known_at']=40
    document['cases'][0]['paper_trade']={
      'entry_price':'102','initial_stop':'100','target_price':'108','aggregate_risk_remaining':'25',
      'instrument':{'money_per_price_unit_per_lot':'100','min_lot':'0.01','lot_step':'0.01'},
      'costs':{'round_trip_fee_per_lot':'10','adverse_price_allowance':'0.1'},
      'box':{'box_id':'SYNTHETIC_BOX','risk_budget':'25','target_definition':'Explicit synthetic structural target, not a teacher default',
             'management_choices':['reduce','riskfree','saveprofit','fulltarget'],'declared_before_box':True},
      'events':[{'event':'fill_entry','fill_price':'102','lots':'0.11'},
        {'event':'manage','label':'reduce','new_stop':'101','at':101,'trigger':{'value':True,'known_at':101,'source':'SYNTHETIC_TRIGGER'}},
        {'event':'manage','label':'riskfree','new_stop':'102.2','at':102,'trigger':{'value':True,'known_at':102,'source':'SYNTHETIC_TRIGGER'}},
        {'event':'manage','label':'saveprofit','new_stop':'104','at':103,'trigger':{'value':True,'known_at':103,'source':'SYNTHETIC_TRIGGER'}},
        {'event':'quote','bid':'108','ask':'108.2','at':104},
        {'event':'close','exit_fill':'108','actual_round_trip_fee':None},
        {'event':'close','exit_fill':'108','actual_round_trip_fee':'1.1'}]}
    # Explicit synthetic fixture evidence; never inferred for user input events.
    for index,event in enumerate(document['cases'][0]['paper_trade']['events']):
        event.setdefault('at',100+index)
        event['known_at']=event['at']
        event['source']='SYNTHETIC_EXECUTION_EVENT_NOT_MARKET_EVIDENCE'
    return document
