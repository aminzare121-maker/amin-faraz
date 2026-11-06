import unittest
from decimal import Decimal as D
from context_inputs import Context
from raw_geometry import Candle
from raw_pipeline import RawPipeline
from teacher_features import candle_predicates

RULE='STOPPUNCH_OPPOSITE_CONFIRMATION'
def bar(t,o,h,l,c):return Candle(t,t+900,*map(D,(o,h,l,c)))
def model(region_low='112.1'):
    # Run assessment, its anchor and location are explicit source inputs.
    # Freshness/whole role chain/pause/reference/close/region are measured.
    c=Context(0,5000,900,dict(sentiment_permission='LONG_ONLY',punch_run_end_opened_at=0,
        strong_run_in_sentiment_direction=True,
        entry_location='BETWEEN_PREEXISTING_ZONES',confirmation_region_low=D(region_low),
        confirmation_region_high=D(114)),'SYNTHETIC_S21_CASE_CONTEXT_NOT_MARKET_CLASSIFICATION')
    return RawPipeline('S21_OPPOSITE_SOURCE_SUBSET',(RULE,),900,'a'*64,[c])
def buy(result):return next(x for x in result['decisions'] if x['side']=='BUY')

class OppositePauseRawTests(unittest.TestCase):
    def test_source_subset_uses_previous_red_upper_wick_without_doubt_shape_gate(self):
        p=model();p.step(bar(0,'90','108','90','108'));pause=bar(900,'108','112','103','104')
        self.assertFalse(candle_predicates(pause)['doubt_shape'].value)
        self.assertNotEqual(buy(p.step(pause))['status'],'ELIGIBLE')
        r=buy(p.step(bar(1800,'104','114','104','113')))
        self.assertEqual(r['status'],'ELIGIBLE')
        self.assertEqual(r['dependency_facts']['teacher_confirmation_reference']['value'],D(112))
        self.assertTrue(r['dependency_facts']['confirmation_near']['value'])
        self.assertEqual(r['dependency_facts']['current_setup']['origin'],'DERIVED_MIXED')
        self.assertEqual(r['dependency_facts']['complete_punch_sequence']['origin'],'DERIVED_MIXED')
    def test_body_only_cross_is_not_sufficient_for_this_s21_wick_case(self):
        p=model('109');p.step(bar(0,'90','108','90','108'));p.step(bar(900,'108','112','103','104'))
        r=buy(p.step(bar(1800,'104','111','104','110')))
        self.assertEqual(r['status'],'WAIT')
        self.assertIn('CLOSE_NOT_BEYOND_REFERENCE',r['reasons'])
        self.assertTrue(r['dependency_facts']['confirmation_near']['value'])
    def test_far_close_wrong_colour_or_gap_does_not_create_source_subset(self):
        for pause,current in (
            (bar(900,'108','112','103','104'),bar(1800,'104','120','104','119')),
            (bar(900,'104','112','103','108'),bar(1800,'108','114','108','113')),
            (bar(900,'108','112','103','104'),bar(2700,'104','114','104','113'))):
            p=model();p.step(bar(0,'90','108','90','108'));p.step(pause)
            self.assertNotEqual(buy(p.step(current))['status'],'ELIGIBLE')
    def test_ready_flags_cannot_manufacture_raw_freshness_without_run_anchor(self):
        c=Context(2700,5000,2700,dict(sentiment_permission='LONG_ONLY',current_setup=True,
            strong_run_in_sentiment_direction=True,complete_punch_sequence=True,
            opposite_colour_pause=True,following_confirmation_closed=True,confirmation_timely=True,
            confirmation_near=True,confirmation_close=D(113),teacher_confirmation_reference=D(112),
            entry_location='BETWEEN_PREEXISTING_ZONES'),'SYNTHETIC_READY_FLAGS_WITHOUT_ROLE_ANCHOR')
        p=RawPipeline('NO_READY_FRESHNESS_BYPASS',(RULE,),900,'a'*64,[c])
        p.step(bar(0,'90','108','90','108'));p.step(bar(900,'108','112','103','104'))
        r=buy(p.step(bar(1800,'104','114','104','113')))
        self.assertNotEqual(r['status'],'ELIGIBLE')
        self.assertEqual(r['punch_role_chain_status'],'MISSING_SOURCED_RUN_OR_END_ANCHOR')
        self.assertIn('current_setup',r['missing_dependencies'])

if __name__=='__main__':unittest.main()
