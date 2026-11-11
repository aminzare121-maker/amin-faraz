"""S19 source correction, isolated from pinned earlier core."""
import unittest
from decimal import Decimal as D
from context_inputs import Context
from raw_geometry import Candle
from raw_pipeline import RawPipeline

def C(t,o,h,l,c):return Candle(t,t+900,*(D(x) for x in (o,h,l,c)))

class TeacherS19CorrectedTests(unittest.TestCase):
    def setup_pipeline(self):
        facts={'sentiment_permission':'LONG_ONLY','current_setup':True,
               'family_selection_context':'ZONE_CONTEXT','trend_strength':'NORMAL',
               'zone_context':True,'reversal_relative_to_last_leg':True,
               'doubt_confidence_condition':True,'half_leg_condition':True,'three_sequence_pivot_confirmed':True}
        # Tests use synthetic context to isolate exact rule logic; these are
        # NOT observed teacher-chart facts or a broker authorization.
        ctx=Context(0,7200,0,facts,'SYNTHETIC_S19_LOGIC_FIXTURE')
        return RawPipeline('S19_TEST',('REVERSAL_THREE',),900,'e'*64,[ctx])

    def test_mixed_colours_doubt_in_sentiment_direction_is_not_rejected(self):
        p=self.setup_pipeline()
        for c in (C(0,'10','13','10','11'), C(900,'11','11.1','9.5','10'), C(1800,'10','12','10','12')):
            result=p.step(c)
        buy=[x for x in result['decisions'] if x['side']=='BUY'][0]
        self.assertEqual(buy['status'],'ELIGIBLE')
        fact=buy['dependency_facts']['three_doubt_in_sentiment_sequence']
        self.assertTrue(fact['value'])
        self.assertEqual(fact['origin'],'DERIVED_FROM_RAW')
        self.assertFalse(buy['order_created'])

    def test_three_same_colour_without_doubt_is_not_auto_approved(self):
        p=self.setup_pipeline()
        for t in (0,900,1800):result=p.step(C(t,'10','12','10','12'))
        buy=next(x for x in result['decisions'] if x['side']=='BUY')
        self.assertEqual(buy['status'],'WAIT')
        self.assertIn('three_doubt_in_sentiment_sequence',buy['reasons'][0])

    def test_traceable_session19_source_inside_thirteen_rule_engine(self):
        from entry_engine import Engine, Observation, Fact, RULE_IDS
        self.assertEqual(len(RULE_IDS),13)
        p=RawPipeline('S19_REFERENCE',('REVERSAL_THREE',),900,'b'*64)
        for c in (C(0,'10','13','10','11'), C(900,'11','11.1','9.5','10'), C(1800,'10','12','10','12')):
            result=p.step(c)
        d=next(x for x in result['decisions'] if x['side']=='BUY')
        self.assertIn((19,3440.62,3625.96),d['sources'])
        self.assertFalse(d['order_created'])
        self.assertIn('half_leg_condition',d['missing_dependencies'])
        self.assertIn('sentiment_permission',d['missing_dependencies'])

    def test_source_required_pivot_not_invented_from_three_candles(self):
        # S19 3646..3654: teacher explicitly requires a pivot for this sequence.
        # Raw 3-candle geometry alone must NOT authorize a teacher trade.
        p=RawPipeline('S19_NO_INVENTED_PIVOT',('REVERSAL_THREE',),900,'a'*64,
            [Context(0,7200,0,{'sentiment_permission':'LONG_ONLY','current_setup':True,
                'family_selection_context':'ZONE_CONTEXT','trend_strength':'NORMAL',
                'zone_context':True,'reversal_relative_to_last_leg':True,
                'doubt_confidence_condition':True,'half_leg_condition':True},
                'SYNTHETIC_CASE_WITHOUT_PIVOT')])
        for c in (C(0,'10','13','10','11'),C(900,'11','11.1','9.5','10'),C(1800,'10','12','10','12')):
            result=p.step(c)
        buy=next(x for x in result['decisions'] if x['side']=='BUY')
        self.assertNotEqual(buy['status'],'ELIGIBLE')
        self.assertIn('three_sequence_pivot_confirmed',buy['missing_dependencies'])
        self.assertFalse(buy['order_created'])

    def test_source_required_pivot_false_blocks_entry(self):
        p=RawPipeline('S19_PIVOT_REJECTED',('REVERSAL_THREE',),900,'a'*64,
            [Context(0,7200,0,{'sentiment_permission':'LONG_ONLY','current_setup':True,
                'family_selection_context':'ZONE_CONTEXT','trend_strength':'NORMAL',
                'zone_context':True,'reversal_relative_to_last_leg':True,
                'doubt_confidence_condition':True,'half_leg_condition':True,
                'three_sequence_pivot_confirmed':False},
                'SYNTHETIC_CASE_INVALID_PIVOT')])
        for c in (C(0,'10','13','10','11'),C(900,'11','11.1','9.5','10'),C(1800,'10','12','10','12')):
            result=p.step(c)
        buy=next(x for x in result['decisions'] if x['side']=='BUY')
        self.assertEqual(buy['status'],'WAIT')
        self.assertFalse(buy['order_created'])

    def test_missing_half_leg_or_sentiment_is_not_eligible(self):
        p=RawPipeline('S19_MISSING_CONTEXT',('REVERSAL_THREE',),900,'f'*64)
        for c in (C(0,'10','13','10','11'), C(900,'11','11.1','9.5','10'), C(1800,'10','12','10','12')):
            result=p.step(c)
        buy=next(x for x in result['decisions'] if x['side']=='BUY')
        self.assertNotEqual(buy['status'],'ELIGIBLE')
        self.assertIn('half_leg_condition',buy['missing_dependencies'])
        self.assertIn('sentiment_permission',buy['missing_dependencies'])

if __name__=='__main__':unittest.main()
