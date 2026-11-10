import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal as D
from unittest.mock import Mock
from artin_automatic_teacher_recognizer import (Bar,AutoRecognizer,InputError,run_scan)
from artin_automatic_trade_cycle import run_auto_paper,ScenarioError
from artin_mt5_demo_automatic import (guard_account,validated_winrate,fxm_targets,
   broker_day_outcomes,broker_volume,exact_broker_price,trade_request,BotBlocked)


def c(t,o,h,l,cl):return Bar(t,D(str(o)),D(str(h)),D(str(l)),D(str(cl)))

def reversal():
    return [c(0,100,101,99,100),c(900,100,105,100,104),
            c(1800,107,110,106,109),c(2700,105,106,101,104),
            c(3600,104,108,104,107),c(4500,107,109,106,108),
            c(5400,108,110,107,109)]

class SourceAutoTests(unittest.TestCase):
    def test_reversal_full_ohlc_without_human_fact_file(self):
        x,s=run_scan(reversal())
        self.assertEqual(len(s),1)
        self.assertEqual(s[0].at,4500)
        self.assertEqual(s[0].side,'BUY')
        self.assertEqual(s[0].route,'REVERSAL_FVG_DOUBT_CONFIDENCE')
        self.assertEqual(s[0].operational_stop,'101')
        self.assertFalse(s[0].teacher_semantics_fully_verified)
        self.assertFalse(s[0].actionable_broker_order)
        self.assertEqual(x.counts['fvg_created'],1)
    def test_closed_only_no_future_signal(self):
        x,s=run_scan(reversal()[:4]);self.assertEqual(s,[])
        y,z=run_scan(reversal()[:5]);self.assertEqual(len(z),1)
    def test_no_lookahead_or_duplicate(self):
        e=AutoRecognizer()
        for x in reversal():e.step(x)
        with self.assertRaisesRegex(InputError,'DUPLICATE_OR_OUT_OF_ORDER'):e.step(reversal()[-1])
    def test_bad_m15_grid_rejected(self):
        with self.assertRaisesRegex(InputError,'INVALID_M15_TIME'):c(123,1,2,1,2)
    def test_gap_resets_old_zone(self):
        b=reversal()[:4]+[c(7200,104,108,104,107)]
        x,s=run_scan(b)
        self.assertEqual(s,[])
        self.assertGreater(x.counts['history_discontinuities'],0)
    def test_bear_reversal_symmetric(self):
        source=reversal()
        # mirror around 200 so bullish becomes bearish with original OHLC order
        bearish=[Bar(x.t,D(200)-x.open,D(200)-x.low,D(200)-x.high,D(200)-x.close) for x in source]
        _,signals=run_scan(bearish)
        self.assertEqual(len(signals),1)
        self.assertEqual(signals[0].side,'SELL')
    def test_exact_body_break_detected_not_assumed_teacher_verified(self):
        b=reversal()[:3]+[c(2700,105,111,105,111)]
        _,signals=run_scan(b)
        self.assertEqual(len(signals),1)
        self.assertEqual(signals[0].route,'BREAK_FVG_EXACT_FULLBODY')
        self.assertFalse(signals[0].actionable_broker_order)
    def test_nonexact_fullbody_does_not_qualify_break(self):
        b=reversal()[:3]+[c(2700,105,112,105,111)]
        _,signals=run_scan(b)
        self.assertEqual(signals,[])
    def test_no_fake_zone_when_three_bars_missing(self):
        b=[c(0,100,101,99,100),c(900,100,105,100,104),c(2700,107,110,106,109)]
        det,signals=run_scan(b)
        self.assertEqual(det.counts['fvg_created'],0)
        self.assertEqual(signals,[])

class CycleTests(unittest.TestCase):
    def cfg(self,**other):
        cfg=dict(initial_balance='1000',reference_balance='1000',risk_pct='1',
                 winrate='43',winrate_source='USER_SELECTED_SCENARIO_NOT_AUDITED',
                 contract_value='100',min_lot='0.01',lot_step='0.01',
                 round_trip_fee_per_lot='0',spread='0',mode='SINGLE_RR')
        cfg.update(other);return cfg
    def test_automatic_full_paper_cycle(self):
        bars=reversal()+[c(6300,109,121,108,120)]
        r=run_auto_paper(bars,**self.cfg())
        self.assertEqual(r['signal_count'],1)
        self.assertEqual(r['finished_trades'],1)
        self.assertEqual(r['trades'][0]['reason'],'TP')
        self.assertEqual(r['orders_submitted'],0)
        self.assertFalse(r['strategy_semantics_verified'])
    def test_winrate_ambiguous_blocked(self):
        with self.assertRaisesRegex(ScenarioError,'FXM_RR_NOT_UNAMBIGUOUS'):
            run_auto_paper(reversal(),**self.cfg(winrate='50'))
    def test_three_tp_requires_band(self):
        with self.assertRaisesRegex(ScenarioError,'FXM_THREE_TP_BAND_REQUIRED'):
            run_auto_paper(reversal(),**self.cfg(mode='THREE_TP'))
    def test_20pct_drawdown_stops(self):
        r=run_auto_paper(reversal(),**self.cfg(initial_balance='800'))
        self.assertTrue(r['stopped_on_20pct_drawdown'])
        self.assertEqual(r['finished_trades'],0)
    def test_same_bar_stop_priority(self):
        # A candle spans both stop/TP. Sequence unknown -> stop-first.
        a=reversal();a[-1]=c(5400,108,122,98,108)
        r=run_auto_paper(a,**self.cfg())
        self.assertEqual(r['trades'][0]['reason'],'STOP')
    def test_three_tp_stop_moves_and_tp3(self):
        r=run_auto_paper(reversal()+[c(6300,109,135,108,130)],**self.cfg(winrate='50',mode='THREE_TP'))
        self.assertEqual(r['finished_trades'],1)
        self.assertEqual(r['trades'][0]['reason'],'TP3')

class DemoSafetyTests(unittest.TestCase):
    def fake_mt(self,mode=0):
        m=Mock();m.ACCOUNT_TRADE_MODE_DEMO=0;m.ACCOUNT_TRADE_MODE_REAL=2
        m.account_info.return_value=SimpleNamespace(trade_mode=mode,server='ePlanet-MT5',company='ePlanet Ltd',login=1,balance=1000)
        m.terminal_info.return_value=SimpleNamespace(data_path='/tmp/mt5-DATA',connected=True)
        return m
    def test_guard_demo_allowed(self):
        self.assertEqual(guard_account(self.fake_mt(),'/tmp/mt5-DATA').login,1)
    def test_guard_real_fails_before_any_broker_trade(self):
        m=self.fake_mt(2)
        with self.assertRaisesRegex(BotBlocked,'STRICT_EPLANET_DEMO_REQUIRED'):
            guard_account(m,'/tmp/mt5-DATA')
        m.order_send.assert_not_called()
    def test_guard_wrong_server_fails(self):
        m=self.fake_mt();m.account_info.return_value.server='not-ePlanet'
        with self.assertRaisesRegex(BotBlocked,'STRICT_EPLANET_DEMO_REQUIRED'):
            guard_account(m,'/tmp/mt5-DATA')
    def test_guard_wrong_terminal_fails(self):
        with self.assertRaisesRegex(BotBlocked,'MT5_TERMINAL_DATA_PATH_MISMATCH'):
            guard_account(self.fake_mt(),'/tmp/another')
    def test_winrate_record_rejects_self_declared_without_audited(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'wr.json';p.write_text(json.dumps({'schema':'fxm_winrate_evidence_v1','wins':5,'losses':5,'source':'x'}))
            with self.assertRaises(BotBlocked):validated_winrate(p)
            p.write_text(json.dumps({'schema':'fxm_winrate_evidence_v1','wins':43,'losses':57,'source':'audited-record','audited':True}))
            w,s=validated_winrate(p)
            self.assertEqual(w,D(43))
    def test_fxm_rr_source_gate(self):
        self.assertEqual(fxm_targets('SINGLE_RR',D(43),'audit'),(D('1.8'),))
        with self.assertRaises(BotBlocked):fxm_targets('SINGLE_RR',D(50),'audit')
        self.assertEqual(fxm_targets('THREE_TP',D(50),'audit'),(D('0.8'),D('1.3'),D('1.8')))
    def test_lot_calculation_actual_broker_profit_not_assumed_contract(self):
        m=self.fake_mt();m.ORDER_TYPE_BUY=0;m.order_calc_profit.return_value=-100
        info=SimpleNamespace(volume_step=0.01,volume_min=0.01,volume_max=10)
        self.assertEqual(broker_volume(m,0,'XAUUSD.st',D('4000'),D('3990'),D('10'),info),D('0.10'))
    def test_broker_price_rejects_silent_repricing(self):
        info=SimpleNamespace(trade_tick_size=0.01)
        with self.assertRaisesRegex(BotBlocked,'NOT_ON_BROKER_TICK'):
            exact_broker_price('4000.005',info)
    def test_broker_day_history_missing_blocks(self):
        m=Mock();m.history_deals_get.return_value=None
        with self.assertRaisesRegex(BotBlocked,'BROKER_DAY_HISTORY_UNAVAILABLE'):
            broker_day_outcomes(m,0,1763000000,[])
    def test_broker_day_after_two_sl_one_tp_stops(self):
        m=Mock();m.DEAL_ENTRY_OUT=1;m.DEAL_ENTRY_OUT_BY=3;m.DEAL_REASON_SL=4;m.DEAL_REASON_TP=5
        d=[SimpleNamespace(magic=26011113,symbol='XAUUSD.st',entry=1,position_id=i,
             reason=reason,time=1763000000+i) for i,reason in enumerate((5,4,4),start=1)]
        m.history_deals_get.return_value=d
        with self.assertRaisesRegex(BotBlocked,'FXM_DAY_STOP'):
            broker_day_outcomes(m,0,1763000100,[])
    def test_broker_day_unknown_exit_reason_blocks(self):
        m=Mock();m.DEAL_ENTRY_OUT=1;m.DEAL_ENTRY_OUT_BY=3;m.DEAL_REASON_SL=4;m.DEAL_REASON_TP=5
        m.history_deals_get.return_value=[SimpleNamespace(magic=26011113,symbol='XAUUSD.st',entry=1,
            position_id=1,reason=99,time=1763000000)]
        with self.assertRaisesRegex(BotBlocked,'UNCLASSIFIED_BROKER_CLOSED_TRADE'):
            broker_day_outcomes(m,0,1763000100,[])

if __name__=='__main__':unittest.main()