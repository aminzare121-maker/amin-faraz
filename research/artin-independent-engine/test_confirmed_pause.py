import unittest
from decimal import Decimal as D
from context_inputs import Context
from raw_geometry import Candle
from raw_pipeline import RawPipeline
from entry_engine import Engine,Fact,Observation
from examples import demo_document

RULE='STOPPUNCH_S22_SELL_CONFIRMED_PAUSE'
def bar(t,o,h,l,c):return Candle(t,t+900,*map(D,(o,h,l,c)))
def pipeline(variant='S22_AFTER_BREAK_CONFIRMED_PAUSE',known=900,operand='PAUSE_WICK_LOW_HYPOTHESIS',extra=None):
    ctx=Context(0,10000,known,dict(sentiment_permission='SHORT_ONLY',current_setup=True,
        teacher_model_variant=variant,strong_run_in_sentiment_direction=True,run_break_closed_at=900,
        confirmation_reference_kind=operand,**(extra or {})),
        'SYNTHETIC_SOURCED_RUN_FIXTURE_NOT_RAW_CLASSIFICATION')
    return RawPipeline('S22_CONDITIONAL_SOURCE_CASE',(RULE,),900,'a'*64,[ctx])

class ConfirmedPauseTests(unittest.TestCase):
    def test_same_prices_from_different_raw_source_hashes_have_different_decision_identity(self):
        a=pipeline();b=RawPipeline('S22_CONDITIONAL_SOURCE_CASE',(RULE,),900,'b'*64,a.contexts)
        results=[]
        for p in (a,b):
            for c in (bar(0,'110','111','99','100'),bar(900,'100','104','98','99'),bar(1800,'99','100','94','95')):
                r=p.step(c)
            results.append(next(d for d in r['decisions'] if d['side']=='SELL'))
        self.assertNotEqual(results[0]['input_fingerprint'],results[1]['input_fingerprint'])
        self.assertIn('CSV_SHA256:'+'a'*64,results[0]['dependency_facts']['confirmation_close']['source'])
    def test_annotated_operand_label_cannot_disagree_with_reference_or_use_premature_prices(self):
        c=next(c for c in demo_document()['cases'] if c['rule_id']==RULE)
        facts={k:Fact(**v) for k,v in c['facts'].items()}
        e=Engine('DIRECT_CLOCK_CONTRACT',(RULE,))
        self.assertEqual(e.evaluate(RULE,Observation('SELL',100,facts)).status,'ELIGIBLE')
        mismatch={**facts,'teacher_confirmation_reference':Fact('100',100,'MISMATCH')}
        self.assertIn('S22_REFERENCE_DOES_NOT_MATCH_SELECTED_OPERAND',e.evaluate(RULE,Observation('SELL',100,mismatch)).reasons)
        early={**facts,'pause_wick_low':Fact('99',69,'BEFORE_PAUSE_COMPLETION')}
        self.assertIn('S22_PAUSE_PRICE_KNOWN_BEFORE_COMPLETION',e.evaluate(RULE,Observation('SELL',100,early)).reasons)
    def test_red_pause_waits_then_raw_red_close_below_low_qualifies_sell(self):
        p=pipeline()
        p.step(bar(0,'110','111','99','100'))
        pause=p.step(bar(900,'100','104','98','99'))
        sell=lambda r:next(d for d in r['decisions'] if d['side']=='SELL')
        self.assertNotEqual(sell(pause)['status'],'ELIGIBLE')
        result=p.step(bar(1800,'99','100','94','95'))
        self.assertEqual(sell(result)['status'],'ELIGIBLE')
        self.assertEqual(sell(result)['dependency_facts']['teacher_confirmation_reference']['value'],D(98))
        self.assertEqual(sell(result)['dependency_facts']['pause_doubt_confirmed']['origin'],'DERIVED_MIXED')
    def test_non_breaking_confirmation_waits(self):
        p=pipeline();p.step(bar(0,'110','111','99','100'));p.step(bar(900,'100','104','98','99'))
        r=p.step(bar(1800,'100','101','98','98'))
        self.assertEqual(next(d for d in r['decisions'] if d['side']=='SELL')['status'],'WAIT')
    def test_late_or_wrong_variant_does_not_retroactively_create_source_case(self):
        for p in (pipeline(known=1800),pipeline('S21_ZONE_SAME_COLOUR')):
            p.step(bar(0,'110','111','99','100'));p.step(bar(900,'100','104','98','99'))
            r=p.step(bar(1800,'99','100','94','95'))
            self.assertNotEqual(next(d for d in r['decisions'] if d['side']=='SELL')['status'],'ELIGIBLE')
    def test_gap_does_not_manufacture_next_confirmation(self):
        p=pipeline();p.step(bar(0,'110','111','99','100'));p.step(bar(900,'100','104','98','99'))
        r=p.step(bar(2700,'99','100','94','95'))
        self.assertNotEqual(next(d for d in r['decisions'] if d['side']=='SELL')['status'],'ELIGIBLE')
    def test_source_header_case_prunes_strict_wick_hypothesis_not_a_full_teacher_acceptance(self):
        # Affinely normalized S22 header geometry; not published market OHLC.
        # Original prices stay in the private local source probe. Times are
        # consecutive-bar coordinates, not broker UTC.
        statuses={}
        for operand in ('PAUSE_BODY_CLOSE_HYPOTHESIS','PAUSE_WICK_LOW_HYPOTHESIS','UNKNOWN'):
            p=pipeline(operand=operand)
            p.step(bar(0,'340','344','263','271'))
            before=p.step(bar(900,'270','290','248','266'))
            self.assertNotEqual(next(d for d in before['decisions'] if d['side']=='SELL')['status'],'ELIGIBLE')
            r=p.step(bar(1800,'266','266','226','249'))
            statuses[operand]=next(d for d in r['decisions'] if d['side']=='SELL')['status']
        self.assertEqual(statuses,{'PAUSE_BODY_CLOSE_HYPOTHESIS':'ELIGIBLE',
            'PAUSE_WICK_LOW_HYPOTHESIS':'WAIT','UNKNOWN':'REVIEW'})
    def test_ready_made_role_flags_cannot_bypass_late_variant_or_raw_gap(self):
        roles=dict(break_before_pause=True,pause_doubt_confirmed=True,pause_in_run_direction=True,
            confirmation_in_run_direction=True,following_confirmation_closed=True,confirmation_timely=True,
            confirmation_close=D(95),teacher_confirmation_reference=D(98),pause_opened_at=900,
            pause_closed_at=1800,confirmation_opened_at=1800,confirmation_closed_at=2700)
        p=pipeline(known=1800,extra=roles)
        p.step(bar(0,'110','111','99','100'));p.step(bar(900,'100','104','98','99'))
        r=p.step(bar(1800,'99','100','94','95'))
        self.assertNotEqual(next(d for d in r['decisions'] if d['side']=='SELL')['status'],'ELIGIBLE')

if __name__=='__main__':unittest.main()
