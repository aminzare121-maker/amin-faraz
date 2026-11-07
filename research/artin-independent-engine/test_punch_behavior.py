import unittest
from decimal import Decimal as D
from context_inputs import Context
from entry_engine import Fact
from punch_behavior import derive
from raw_geometry import Candle
from raw_pipeline import RawPipeline

class PunchBehaviorTests(unittest.TestCase):
    def prepare(self,close='104',counts=(1,1),band=True):
        # Normalized schematic witness for S21 near/too-far contrast, NOT
        # measured market OHLC or a complete teacher trade/strong-run model.
        f={'sentiment_permission':'LONG_ONLY','current_setup':True,
            'strong_run_in_sentiment_direction':True,'day_correct_count':counts[0],
            'day_incorrect_count':counts[1],'zone_low':D(99),'zone_high':D(102),'reference_zone_validated':True}
        if band:f.update(confirmation_region_low=D(103),confirmation_region_high=D(106))
        p=RawPipeline('B',('STOPPUNCH_DOJI_TIED','STOPPUNCH_DOJI_AHEAD'),900,'d'*64,
            [Context(0,10000,0,f,'SYNTHETIC_SCHEMATIC_CONDITIONS_NOT_FULL_TEACHER_MARKET_INPUTS')])
        p.step(Candle(0,900,D(101),D(103),D(100),D(101)))
        r=p.step(Candle(900,1800,D(101),max(D(close),D(103)),D(101),D(close)))
        return p,next(x for x in r['decisions'] if x['side']=='BUY' and x['rule_id']=='STOPPUNCH_DOJI_TIED')

    def test_tied_branch_reads_previous_doji_not_confirmation_body(self):
        p,d=self.prepare()
        self.assertEqual(d['status'],'ELIGIBLE')
        f=p.latest_observation('BUY','STOPPUNCH_DOJI_TIED').facts
        self.assertTrue(f['doji_confirmed'].value)
        self.assertEqual(f['doji_shadow_high'].known_at,900)
        self.assertEqual(f['day_analysis_state'].value,'TIED_BY_COUNT')
        self.assertNotEqual(f['candle_open'].value,f['decision_close'].value)

    def test_beyond_shadow_but_outside_sourced_region_is_not_entry(self):
        p,d=self.prepare('120')
        self.assertEqual(d['status'],'REJECT')
        self.assertEqual(d['reasons'],('CONFIRMATION_TOO_FAR',))

    def test_no_region_never_silently_becomes_near(self):
        p,d=self.prepare(band=False)
        self.assertEqual(d['reasons'],('MISSING:confirmation_near',))

    def test_counts_not_money_and_start_is_not_automatically_tied(self):
        p,d=self.prepare(counts=(0,0))
        self.assertEqual(p.latest_observation('BUY','STOPPUNCH_DOJI_TIED').facts['day_analysis_state'].value,'START_OF_DAY')
        self.assertEqual(d['status'],'REVIEW')

    def test_region_cannot_be_chosen_after_seeing_confirmation(self):
        window=[Candle(0,900,D(101),D(103),D(100),D(101)),Candle(900,1800,D(101),D(104),D(101),D(104))]
        facts={k:Fact(v,1800,'LATE_REGION') for k,v in {'confirmation_region_low':D(103),
            'confirmation_region_high':D(106),'zone_low':D(99),'zone_high':D(102)}.items()}
        r=derive('STOPPUNCH_DOJI_TIED','BUY',window,facts)
        self.assertNotIn('confirmation_near',r)
        self.assertNotIn('zone_context',r)

    def test_current_doji_cannot_masquerade_as_previous_pause(self):
        f=dict(sentiment_permission='LONG_ONLY',current_setup=True,strong_run_in_sentiment_direction=True,
            zone_context=True,doji_confirmed=True,day_analysis_state='TIED_BY_COUNT',
            following_confirmation_closed=True,confirmation_near=True,confirmation_timely=True,
            confirmation_close=D(104),doji_shadow_high=D(103))
        p=RawPipeline('B',('STOPPUNCH_DOJI_TIED',),900,'e'*64,[Context(0,3000,0,f,'SYNTHETIC_BAD_ROLE_FIXTURE')])
        p.step(Candle(0,900,D(100),D(102),D(99),D(101)))
        r=p.step(Candle(900,1800,D(104),D(105),D(103),D(104)))
        d=next(x for x in r['decisions'] if x['side']=='BUY')
        self.assertEqual(d['reasons'],('MISSING:doji_confirmed',))
        self.assertNotIn('doji_confirmed',d['derived_required_keys'])

    def test_raw_overlap_is_not_an_automatic_valid_teacher_zone(self):
        window=[Candle(0,900,D(101),D(103),D(100),D(101)),Candle(900,1800,D(101),D(104),D(101),D(104))]
        f={k:Fact(v,0,'SYNTHETIC_REGION_ONLY') for k,v in {'zone_low':D(99),'zone_high':D(102)}.items()}
        r=derive('STOPPUNCH_DOJI_TIED','BUY',window,f)
        self.assertTrue(r['pause_zone_overlap_measured'].value)
        self.assertNotIn('zone_context',r)

if __name__=='__main__':unittest.main()
