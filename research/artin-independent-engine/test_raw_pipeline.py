import unittest
from decimal import Decimal as D
from entry_engine import RULE_IDS
from raw_geometry import Candle
from raw_pipeline import RawPipeline
from teacher_features import candle_predicates
from context_inputs import Context,EconomicValue,EconomicRelease,facts_as_of

def candle(t,o='10',h='12',l='10',c='12'):
    return Candle(t,t+900,*map(D,(o,h,l,c)))

class RawPipelineTests(unittest.TestCase):
    def test_source_comparisons_withhold_ambiguous_wick_sum(self):
        p=candle_predicates(candle(0,'10','11.6','9.4','11'))
        self.assertIsNone(p['confidence_shape'].value)
        self.assertIsNone(p['doubt_shape'].value)
        self.assertTrue(candle_predicates(candle(0))['fullbody_or_marubozu'].value)
        self.assertIsNone(candle_predicates(candle(0,'10','12.01','10','12'))['fullbody_or_marubozu'].value)

    def test_confidence_doubt_and_no_epsilon_doji(self):
        self.assertTrue(candle_predicates(candle(0))['confidence_shape'].value)
        self.assertTrue(candle_predicates(candle(0,'10','13','10','11'))['doubt_shape'].value)
        self.assertTrue(candle_predicates(candle(0,'10','11','9','10'))['doji_confirmed'].value)
        self.assertIsNone(candle_predicates(candle(0,'10','11','9','10.00001'))['doji_confirmed'].value)

    def test_economics_as_of_does_not_leak_release_actual(self):
        v=lambda n,t:EconomicValue(D(n),t,'TEST_HISTORICAL_VINTAGE',True)
        event=EconomicRelease('TEST',100,v('2',0),v('3',10),v('4',105))
        self.assertEqual(event.comparison(99)['delta'],D(1))
        self.assertEqual(event.comparison(100)['status'],'NOT_YET_AVAILABLE')
        self.assertEqual(event.comparison(105)['delta'],D(1))
        self.assertIsNone(event.comparison(105)['sentiment_permission'])
        with self.assertRaises(ValueError):EconomicRelease('TEST',100,actual=v('4',99))

    def test_revision_without_vintage_is_not_historical_knowledge(self):
        v=EconomicValue(D(1),0,'LATEST_REVISION',False)
        self.assertEqual(EconomicRelease('X',100,v,v).comparison(20)['status'],'UNVERIFIED_VINTAGE')

    def test_context_expiry_future_and_conflict(self):
        a=Context(0,100,10,{'sentiment_permission':'LONG_ONLY'},'TEACHER_TEST_CONTEXT')
        self.assertEqual(facts_as_of([a],9),{})
        self.assertEqual(facts_as_of([a],100),{})
        self.assertEqual(facts_as_of([a],10)['sentiment_permission'].value,'LONG_ONLY')
        b=Context(0,100,0,{'sentiment_permission':'SHORT_ONLY'},'CONFLICTING_TEST_CONTEXT')
        with self.assertRaises(ValueError):facts_as_of([a,b],10)

    def test_raw_to_break_entry_with_explicit_test_context_no_shape_booleans(self):
        # Synthetic context is explicit; no claim this represents a real market signal.
        ctx=Context(0,2000,0,{'sentiment_permission':'LONG_ONLY','current_setup':True,
            'family_selection_context':'ZONE_CONTEXT','trend_strength':'NORMAL','break_strength':'STRONG',
            'level_kind':'FVG','zone_low':D(9),'zone_high':D(11)},'SYNTHETIC_TEACHER_CONTEXT_FIXTURE')
        r=RawPipeline('TEST',('BREAK_STRONG',),900,'a'*64,[ctx]).step(candle(0))
        buy,sell=r['decisions']
        self.assertEqual(buy['status'],'ELIGIBLE')
        self.assertEqual(buy['missing_dependencies'],[])
        self.assertIn('fullbody_or_marubozu',buy['derived_required_keys'])
        self.assertNotIn('fullbody_or_marubozu',buy['context_required_keys'])
        self.assertEqual(sell['status'],'REJECT')

    def test_all_missing_dependencies_not_only_first_gate(self):
        r=RawPipeline('TEST',RULE_IDS,900,'b'*64).step(candle(0))
        d=next(x for x in r['decisions'] if x['rule_id']=='REVERSAL_CLASSIC')
        self.assertEqual(d['reasons'],('MISSING:sentiment_permission',))
        self.assertIn('zone_context',d['missing_dependencies'])
        self.assertIn('doubt_confirmed',d['missing_dependencies'])
        self.assertIn('decision_candle_closed',d['derived_required_keys'])

    def test_opposite_fullbody_above_zone_is_not_buy_breakout(self):
        ctx=Context(0,2000,0,{'sentiment_permission':'LONG_ONLY','current_setup':True,
            'family_selection_context':'ZONE_CONTEXT','trend_strength':'NORMAL','break_strength':'STRONG',
            'level_kind':'FVG','zone_low':D(9),'zone_high':D(11)},'SYNTHETIC_DIRECTION_REGRESSION')
        r=RawPipeline('TEST',('BREAK_STRONG',),900,'a'*64,[ctx]).step(candle(0,'14','14','12','12'))
        self.assertEqual(r['decisions'][0]['status'],'WAIT')
        self.assertIn('fullbody_or_marubozu',r['decisions'][0]['reasons'][0])

    def test_context_cannot_override_measured_close(self):
        ctx=Context(0,2000,0,{'decision_close':D(999)},'SYNTHETIC_CONFLICT')
        with self.assertRaises(ValueError):RawPipeline('TEST',RULE_IDS,900,'c'*64,[ctx]).step(candle(0))

    def test_three_bar_direction_is_side_specific_and_gap_resets(self):
        p=RawPipeline('TEST',('REVERSAL_THREE',),900,'d'*64)
        for t in (0,900,1800):r=p.step(candle(t))
        self.assertIn('three_same_direction_sequence',r['decisions'][0]['derived_required_keys'])
        self.assertTrue(r['new_candidates'])
        r=p.step(candle(3600))
        self.assertNotIn('three_same_direction_sequence',r['decisions'][0]['derived_required_keys'])
        self.assertTrue(r['gap_before_bar'])

    def test_replay_prefix_is_stable_and_bad_bar_does_not_advance(self):
        p=RawPipeline('TEST',RULE_IDS,900,'e'*64)
        q=RawPipeline('TEST',RULE_IDS,900,'e'*64)
        before=p.step(candle(0))
        expected=q.step(candle(0))
        self.assertEqual(before,expected)
        p.step(candle(900))
        self.assertEqual(before,expected)
        with self.assertRaises(ValueError):p.step(candle(0))
        self.assertEqual(len(p.bars),2)

if __name__=='__main__':unittest.main()
