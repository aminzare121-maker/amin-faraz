import json,os,tempfile,unittest
from decimal import Decimal as D,localcontext
from pathlib import Path
from capital import BoxPlan
from context_inputs import Context
from raw_geometry import Candle
from raw_pipeline import RawPipeline
from run_raw import assert_outputs_separate,input_digest,run
from zone_behavior import ZoneBehavior
from monthly_execution import MonthlyExecutor
from entry_engine import Engine,Fact,Observation
from test_monthly_execution import execution
from copy import deepcopy

def bars():
    return [Candle(0,900,D(10),D(11),D(9),D(10)),
        Candle(900,1800,D(10),D(13),D(10),D(12)),
        Candle(1800,2700,D(13),D(14),D(12),D(13)),
        Candle(2700,3600,D(13),D(13),D(10),D(10))]

class RootRepairTests(unittest.TestCase):
    def obs(self,at):
        vals=dict(sentiment_permission='TWO_SIDED',current_setup=True,family_selection_context='ZONE_CONTEXT',
            break_strength='STRONG',fullbody_or_marubozu=True,decision_candle_closed=True,
            level_kind='PIVOT',decision_close=D(101),line_level=D(100))
        return Observation('BUY',at,{k:Fact(v,at,'SYNTHETIC') for k,v in vals.items()})

    def test_fingerprint_exact_under_low_decimal_precision(self):
        make=lambda x:BoxPlan('B',D(x),'target',(),True)
        with localcontext() as c:
            c.prec=2
            a=make('25.00000000000000000000000001').fingerprint
            b=make('25.00000000000000000000000002').fingerprint
            self.assertNotEqual(a,b)
            self.assertEqual(make('25.00').fingerprint,make('2.5E1').fingerprint)
        self.assertEqual(a,make('25.00000000000000000000000001').fingerprint)

    def test_all_inputs_aliases_and_hardlinks_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source=p/'context.json';source.write_text('KEEP',encoding='utf8')
            with self.assertRaises(ValueError):assert_outputs_separate([source],[source])
            alias=p/'SUMMARY.json';os.link(source,alias)
            with self.assertRaises(ValueError):assert_outputs_separate([alias],[source])
            self.assertEqual(source.read_text(encoding='utf8'),'KEEP')

    def test_context_protection_and_receipt_in_actual_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);csv=p/'bars.csv';csv.write_text('time_raw_epoch,open,high,low,close\n0,10,11,9,10\n',encoding='utf8')
            out=p/'out';out.mkdir();context=out/'SUMMARY.json';context.write_text('KEEP',encoding='utf8')
            with self.assertRaises(ValueError):run(csv,out,900,protected_inputs=[context])
            self.assertEqual(context.read_text(encoding='utf8'),'KEEP')
            result=run(csv,p/'safe',900)
            self.assertIn('monthly_execution.py',result['provenance']['module_sha256'])
            self.assertIn('decimal_context',result['provenance'])
            self.assertNotEqual(input_digest({'x':D('1')}),input_digest({'x':'1'}))

    def test_fvg_reference_exists_before_break_and_far_edge_is_same_zone(self):
        z=ZoneBehavior(900,'SYNTHETIC_RAW_GEOMETRY_SOURCE')
        for b in bars()[:3]:self.assertEqual(z.step(b),[])
        events=z.step(bars()[3]);self.assertEqual(len(events),1)
        e=events[0];self.assertEqual((e['side'],e['edge']),('SELL',D(11)))
        self.assertEqual(e['reference_known_at'],2700)
        f,status=z.reference_facts(events,'SELL',3600)
        self.assertEqual((f['zone_low'].value,f['zone_high'].value),(D(11),D(12)))
        self.assertTrue(f['current_setup'].value)
        self.assertNotIn('break_strength',f)
        # Every touch is not consumption; no undocumented zone TTL or one-use veto.
        self.assertEqual(len(z.zones),1)
        self.assertEqual(z.step(Candle(3600,4500,D(10),D(11),D(9),D(10))),[])

    def test_raw_behavior_reduces_ready_flags_without_fabricating_strength(self):
        ctx=Context(0,10000,0,{'sentiment_permission':'SHORT_ONLY'},'SYNTHETIC_DIRECTION_ONLY')
        p=RawPipeline('B',('BREAK_STRONG',),900,'a'*64,[ctx])
        for b in bars():result=p.step(b)
        d=next(x for x in result['decisions'] if x['side']=='SELL')
        self.assertEqual(d['reasons'],('MISSING:break_strength',))
        for k in ('current_setup','zone_low','zone_high','level_kind','family_selection_context'):
            self.assertIn(k,d['derived_required_keys'])
        self.assertNotIn('trend_strength',d['missing_dependencies'])
        self.assertEqual(p.latest_observation('SELL','BREAK_STRONG').facts['zone_low'].value,D(11))

    def test_local_zone_break_does_not_require_global_trendline_gate(self):
        ctx=Context(0,10000,0,{'sentiment_permission':'SHORT_ONLY','break_strength':'STRONG'},
            'SYNTHETIC_CLASSIFICATION_FIXTURE_NOT_A_MARKET_OR_TEACHER_RAW_EXAMPLE')
        p=RawPipeline('B',('BREAK_STRONG',),900,'b'*64,[ctx])
        for b in bars():r=p.step(b)
        d=next(x for x in r['decisions'] if x['side']=='SELL')
        self.assertEqual(d['status'],'ELIGIBLE')
        self.assertNotIn('trend_strength',p.latest_observation('SELL','BREAK_STRONG').facts)

    def test_gap_and_multiple_zone_selection_never_silently_choose_reference(self):
        z=ZoneBehavior(900,'SYNTHETIC')
        for b in bars()[:3]:z.step(b)
        events=z.step(Candle(3600,4500,D(13),D(13),D(10),D(10)))
        self.assertEqual(z.reference_facts(events,'SELL',4500)[0],{})
        z=ZoneBehavior(900,'SYNTHETIC')
        for b in bars()[:3]:z.step(b)
        events=z.step(bars()[3]);e=dict(events[0]);e['zone_id']='ANOTHER_ZONE'
        self.assertEqual(z.reference_facts(events+[e],'SELL',3600)[1],'MULTIPLE_REFERENCES')

    def test_failed_context_conflict_does_not_advance_behavior(self):
        ctx=Context(0,10000,0,{'sentiment_permission':'SHORT_ONLY','current_setup':False},'SYNTHETIC_CONFLICT')
        p=RawPipeline('B',('BREAK_STRONG',),900,'c'*64,[ctx])
        for b in bars()[:3]:p.step(b)
        with self.assertRaises(ValueError):p.step(bars()[3])
        self.assertEqual(len(p.bars),3)
        self.assertEqual(p.behavior.bars[-1].closed_at,2700)

    def test_recross_does_not_reuse_old_zone_as_automatically_fresh(self):
        z=ZoneBehavior(900,'SYNTHETIC')
        for b in bars():z.step(b)
        events=z.step(Candle(3600,4500,D(10),D(13),D(10),D(13)))
        f,status=z.reference_facts(events,'BUY',4500)
        self.assertEqual(f,{})
        self.assertEqual(status,'REVIEW_LIFECYCLE_UNRESOLVED_AFTER_PRIOR_CROSS')
        self.assertIn('FVG:0,900,1800',z.zones) # Unknown lifecycle, not an invented one-touch expiry.

    def test_gap_uncertainty_stays_after_next_contiguous_bar(self):
        z=ZoneBehavior(900,'SYNTHETIC')
        for b in bars()[:3]:z.step(b)
        z.step(Candle(3600,4500,D(13),D(15),D(13),D(14)))
        events=z.step(Candle(4500,5400,D(14),D(14),D(10),D(10)))
        self.assertFalse(events[0]['series_gap'])
        self.assertTrue(events[0]['history_unknown'])
        self.assertEqual(z.reference_facts(events,'SELL',5400)[1],'REVIEW_ZONE_HISTORY_UNKNOWN_AFTER_GAP')

    def test_normal_entry_but_gapped_exit_unknown_fee_does_not_spend_stale_cash(self):
        e=Engine('B',('BREAK_STRONG',));doc=execution();b=deepcopy(doc['specs'][0]);b.update(at=1800,trade_id='test2')
        doc['specs'].append(b);doc['events']=[
            dict(trade_id='test1',at=900,known_at=900,source='SYNTHETIC',event='fill_entry',fill_price='100'),
            dict(trade_id='test1',at=901,known_at=901,source='SYNTHETIC_GAP_EXIT',event='close',exit_fill='50',actual_round_trip_fee=None)]
        m=MonthlyExecutor(e,'100','.03',doc);o=self.obs(900);m.accept(e.evaluate('BREAK_STRONG',o),o)
        o=self.obs(1800);r=m.accept(e.evaluate('BREAK_STRONG',o),o)
        self.assertFalse(m.trades['test1'].budget_overrun)
        self.assertEqual(r['reason'],'EXIT_COST_RECONCILIATION_REQUIRED')
        self.assertEqual(len(m.trades),1)

    def test_entry_cannot_use_cash_from_later_coordinator_clock(self):
        e=Engine('B',('BREAK_STRONG',));m=MonthlyExecutor(e,'100','.03',execution())
        m.advance(1800);o=self.obs(900)
        with self.assertRaises(ValueError):m.accept(e.evaluate('BREAK_STRONG',o),o)
        self.assertEqual(m.trades,{})

if __name__=='__main__':unittest.main()
