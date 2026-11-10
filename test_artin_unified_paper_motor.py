import copy
import json
import tempfile
import unittest
from pathlib import Path
from artin_unified_paper_motor import MotorError,run_document,verify_journal

ROOT=Path(__file__).parent


def f(value,at=900,source='synthetic-chart-test-900'):
    return {'value':value,'known_at':at,'source':source}


def setup(side='BUY',mode='THREE_TP',at=901,day='teacher-test-day-1'):
    if side=='BUY':
        entry,stop='4000','3995'
    else:
        entry,stop='4000','4005'
    x={'id':f'setup-{side}-{at}','kind':'SETUP','at':at,'source':'synthetic-classroom-test',
       'side':side,'route':'REVERSAL_CLASSIC','trading_day':day,
       'facts':{
           'sentiment_permission':f('TWO_SIDED'),
           'current_setup':f(True),
           'family_selection_context':f('ZONE_CONTEXT'),
           'trend_strength':f('NORMAL'),
           'zone_context':f(True),
           'reversal_relative_to_last_leg':f(True),
           'decision_candle_closed':f(True),
           'doubt_confirmed':f(True),
           'first_confidence_confirmed':f(True)},
       'technical_chart':{'entry_family':f('REVERSAL'),
           'teacher_scene_meaning_confirmed':f(True),
           'prz_context':f('TREND'), 'prz_teacher_confirmed':f(True),
           'stop_anchor_kind':f('PIVOT'),
           'entry_price':f(entry),'structural_stop_price':f(stop)},
       'target_mode':mode,'target_mode_source':'FXM.pdf#page=4',
       'winrate':'55' if mode=='THREE_TP' else '35',
       'winrate_evidence':'synthetic-only-calibration'}
    if mode == 'SINGLE_RR':x['target_mode_source']='FXM.pdf#page=4'
    return x


def evt(kind,at,bid='4000',ask='4000',id=None):
    return {'id':id or f'{kind}-{at}','kind':kind,'at':at,
            'source':'synthetic-bid-ask-sequence','bid':bid,'ask':ask}


def doc(events):
    return {'schema':'artin_unified_paper_events_v1','mode':'SYNTHETIC_TEST',
      'account':{'balance':'1000','reference_balance':'1000','risk_pct':'1'},
      'contract':{'money_per_price_unit_per_lot':'100','min_lot':'0.01',
          'lot_step':'0.01','source':'synthetic-contract-only'},
      'costs':{'round_trip_fee_per_lot':'0','adverse_price_allowance':'0',
          'source':'synthetic-no-cost-example'},'events':events}


class UnifiedMotorTests(unittest.TestCase):
 def run_e(self,events):
    return run_document(doc(events),core_dir=ROOT/'core')
 def test_three_target_buy_full_paper_cycle(self):
    r=self.run_e([setup(),evt('FILL',902,'3999.9','4000'),
      evt('QUOTE',903,'4004','4004.2'),evt('QUOTE',904,'4006.5','4006.7'),
      evt('QUOTE',905,'4009','4009.2'),evt('EXIT_FILL',906,'4009','4009.2')])
    self.assertEqual(r['counts']['PLANNED'],1)
    self.assertEqual(r['counts']['OPENED'],1)
    self.assertEqual(r['counts']['STOP_MOVES'],2)
    self.assertEqual(r['counts']['CLOSED'],1)
    self.assertEqual(r['paper_balance_final'],'1018.00')
    self.assertEqual(r['orders_sent'],0)
    self.assertTrue(verify_journal(r))
    self.assertFalse(r['active_paper_position'])
 def test_sell_one_target_and_explicit_exit_model_loss(self):
    r=self.run_e([setup('SELL','SINGLE_RR'),evt('FILL',902,'4000','4000.1'),
                   evt('QUOTE',903,'4005','4005'),evt('EXIT_FILL',904,'4005','4005')])
    self.assertEqual(r['counts']['CLOSED'],1)
    self.assertEqual(r['paper_balance_final'],'990.00')
    self.assertEqual(r['trace'][-2]['status'],'PAPER_STOP_TOUCH')
 def test_stop_trigger_not_assumed_fill(self):
    r=self.run_e([setup(),evt('FILL',902,'4000','4000'),evt('QUOTE',903,'3995','3995.2')])
    self.assertEqual(r['counts']['CLOSED'],0)
    self.assertEqual(r['paper_balance_final'],'1000')
    self.assertTrue(r['active_paper_position'])
 def test_unverified_core_blocks_even_if_pdf_fields_present(self):
    s=setup();s['facts'].pop('doubt_confirmed')
    r=self.run_e([s,evt('FILL',902)])
    self.assertEqual(r['counts']['PLANNED'],0)
    self.assertEqual(r['counts']['OPENED'],0)
    self.assertEqual(r['trace'][0]['status'],'BLOCKED_PINNED_13_ROUTE')
 def test_missing_pdf_chart_evidence_blocks_core_eligible(self):
    s=setup();s['technical_chart'].pop('prz_teacher_confirmed')
    r=self.run_e([s])
    self.assertEqual(r['counts']['PLANNED'],0)
    self.assertEqual(r['trace'][0]['status'],'BLOCKED_TEACHER_PDF_OR_FXM')
 def test_entry_market_mismatch_cancels_plan_without_resizing(self):
    r=self.run_e([setup(),evt('FILL',902,'3999','4000.01')])
    self.assertEqual(r['trace'][-1]['status'],'PAPER_FILL_PRICE_DIFFERS_REPLAN_REQUIRED')
    self.assertEqual(r['counts']['OPENED'],0)
 def test_duplicate_event_id_rejected(self):
    s=setup()
    with self.assertRaisesRegex(MotorError,'DUPLICATE'):
      self.run_e([s,s])
 def test_future_teacher_fact_rejected(self):
    s=setup();s['facts']['current_setup']['known_at']=2000
    with self.assertRaisesRegex(MotorError,'LOOKAHEAD'):
      self.run_e([s])
 def test_source_required(self):
    s=setup();s['source']=''
    with self.assertRaisesRegex(MotorError,'SOURCE'):
      self.run_e([s])
 def test_wrong_account_risk_rejected(self):
    d=doc([setup()]);d['account']['risk_pct']='4'
    r=run_document(d,core_dir=ROOT/'core')
    self.assertEqual(r['counts']['OPENED'],0)
    self.assertEqual(r['trace'][0]['status'],'BLOCKED_FXM_ACCOUNT_RISK')
 def test_journal_tamper_detected(self):
    r=self.run_e([setup()])
    r['trace'][0]['status']='FAKE'
    self.assertFalse(verify_journal(r))
 def test_paper_mode_no_synthetic_event(self):
    d=doc([setup()]);d['mode']='PAPER_SOURCED'
    with self.assertRaisesRegex(MotorError,'SYNTHETIC'):
      run_document(d,core_dir=ROOT/'core')
 def test_breakeven_recorded_outcome_never_converted_to_win(self):
    # Single target loss followed by a second attempt at unchanged balance.
    r=self.run_e([setup(),evt('FILL',902),evt('QUOTE',903,'4004','4004'),
        evt('QUOTE',904,'4000','4000.1'),evt('EXIT_FILL',905,'4000','4000.1'),
        setup(at=906)])
    self.assertEqual(r['counts']['CLOSED'],1)
    self.assertEqual(r['trace'][-1]['status'],'BLOCKED_FXM_DAY_SEQUENCE')
 def test_20pct_drawdown_gate(self):
    d=doc([setup()]);d['account']['balance']='799'
    r=run_document(d,core_dir=ROOT/'core')
    self.assertEqual(r['trace'][0]['status'],'BLOCKED_FXM_ACCOUNT_RISK')
 def test_buy_single_target_triggers_and_exit(self):
    r=self.run_e([setup('BUY','SINGLE_RR'),evt('FILL',902),
       evt('QUOTE',903,'4010','4010.2'),evt('EXIT_FILL',904,'4010','4010.2')])
    self.assertEqual(r['counts']['CLOSED'],1)
    self.assertEqual(r['paper_balance_final'],'1020.00')
 def test_stop_move_uses_bid_for_buy(self):
    r=self.run_e([setup(),evt('FILL',902),evt('QUOTE',903,'4003.8','4004.3')])
    self.assertEqual(r['counts']['STOP_MOVES'],0)
 def test_stop_move_uses_ask_for_sell(self):
    r=self.run_e([setup('SELL'),evt('FILL',902),evt('QUOTE',903,'3995.8','3996.2')])
    self.assertEqual(r['counts']['STOP_MOVES'],0)
 def test_teacher_pdf_original_hashes_verified(self):
    if not (ROOT/'FXM.pdf').exists() or not (ROOT/'Technical(1).pdf').exists():
        self.skipTest('Original owner-provided scanned PDFs are not published in GitHub')
    r=self.run_e([setup()])
    for name,x in r['original_teacher_pdf_integrity'].items():
        self.assertTrue(x['hash_matched_original_upload'],name)
 def test_teacher_pdf_changed_detected(self):
    from artin_unified_paper_motor import inspect_pdf_sources
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp,'FXM.pdf').write_bytes(b'changed or substituted pages')
        with self.assertRaisesRegex(MotorError,'TEACHER_PDF_CHANGED'):
            inspect_pdf_sources(tmp)
 def test_breakout_teacher_pdf_engine_to_risk_integration(self):
    s=setup();s['route']='BREAK_STRONG'
    s['facts']['break_strength']=f('STRONG')
    s['facts']['fullbody_or_marubozu']=f(True)
    s['facts']['level_kind']=f('PIVOT')
    s['facts']['line_level']=f('3999')
    s['facts']['decision_close']=f('4001')
    s['technical_chart']['entry_family']=f('BREAK')
    s['technical_chart']['break_line_price']=f('3999')
    s['technical_chart']['break_teacher_confirmed']=f(True)
    s['technical_chart']['decision_close']=f('4001')
    r=self.run_e([s])
    self.assertEqual(r['counts']['PLANNED'],1)
    self.assertEqual(r['trace'][0]['detail']['entry'],'4000')
 def test_wrong_break_close_cannot_open(self):
    s=setup();s['route']='BREAK_STRONG'
    s['facts'].update(break_strength=f('STRONG'),fullbody_or_marubozu=f(True),
      level_kind=f('PIVOT'),line_level=f('4001'),decision_close=f('4000'))
    r=self.run_e([s])
    self.assertEqual(r['counts']['PLANNED'],0)
    self.assertEqual(r['trace'][0]['status'],'BLOCKED_PINNED_13_ROUTE')
 def test_session_day_rollback_rejected(self):
    a=setup(day='day-1');b=setup(at=902,day='day-2');c=setup(at=903,day='day-1')
    for x in (a,b,c): x['facts'].pop('doubt_confirmed')  # no staged position
    with self.assertRaisesRegex(MotorError,'TRADING_DAY_ROLLBACK'):
      self.run_e([a,b,c])
 def test_unknown_target_mode_does_not_open(self):
    s=setup();s['target_mode']='MAGIC_NEW_RULE'
    r=self.run_e([s])
    self.assertEqual(r['trace'][0]['status'],'BLOCKED_TEACHER_PDF_OR_FXM')
 def test_no_broker_api(self):
    source=(ROOT/'artin_unified_paper_motor.py').read_text()
    for s in ('order_send(', 'requests.post(', 'TRADE_ACTION_DEAL','subprocess.Popen('):
      self.assertNotIn(s,source)

if __name__ == '__main__':unittest.main()