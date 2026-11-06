import unittest
from direction_plan import DirectionPlan
from entry_engine import Fact
from raw_geometry import Candle
from raw_pipeline import RawPipeline
from decimal import Decimal as D

class DirectionPlanTests(unittest.TestCase):
    def plan(self):return DirectionPlan('FIXED_INSTRUMENT_TEST','XAUUSD.st','S09_FIXED_SYMBOL_TWO_SIDED_ASSUMPTION',True)
    def test_missing_data_alone_never_chooses_plan(self):
        p=RawPipeline('B',('BREAK_STRONG',),900,'a'*64)
        r=p.step(Candle(0,900,D(10),D(12),D(10),D(12)))
        self.assertEqual(r['decisions'][0]['reasons'],('MISSING:sentiment_permission',))
    def test_explicit_assumption_does_not_fabricate_economic_review(self):
        p=self.plan();f=p.derive({},900)
        self.assertEqual(f['sentiment_permission'].value,'TWO_SIDED')
        self.assertEqual(f['historical_direction_evidence_state'].value,'MISSING')
        self.assertFalse(p.serialize()['economic_review_completed_claimed'])
        self.assertNotIn('direction_assessment',f)
    def test_sourced_one_way_and_invalid_values_are_not_overwritten(self):
        p=self.plan()
        for x in ('LONG_ONLY','SHORT_ONLY','INVALID',True):
            self.assertEqual(p.derive({'sentiment_permission':Fact(x,0,'SOURCE')},900),{})
    def test_policy_origin_is_separate_from_observed_context(self):
        p=RawPipeline('B',('BREAK_STRONG',),900,'b'*64,direction_plan=self.plan())
        r=p.step(Candle(0,900,D(10),D(12),D(10),D(12)))
        d=r['decisions'][0]
        self.assertNotEqual(d['reasons'],('MISSING:sentiment_permission',))
        self.assertIn('sentiment_permission',d['policy_required_keys'])
        self.assertNotIn('sentiment_permission',d['context_required_keys'])
        self.assertEqual(d['dependency_facts']['sentiment_permission']['origin'],'DECLARED_RESEARCH_POLICY')
    def test_plan_requires_symbol_predeclaration_and_cannot_change_mid_path(self):
        with self.assertRaises(ValueError):DirectionPlan('B','','S09_FIXED_SYMBOL_TWO_SIDED_ASSUMPTION',True)
        with self.assertRaises(ValueError):DirectionPlan('B','XAUUSD.st','S09_FIXED_SYMBOL_TWO_SIDED_ASSUMPTION',False)
        p=RawPipeline('B',('BREAK_STRONG',),900,'c'*64,direction_plan=self.plan())
        p.direction_plan=DirectionPlan('CHANGED','XAUUSD.st','S09_FIXED_SYMBOL_TWO_SIDED_ASSUMPTION',True)
        with self.assertRaises(ValueError):p.step(Candle(0,900,D(10),D(12),D(10),D(12)))

if __name__=='__main__':unittest.main()
