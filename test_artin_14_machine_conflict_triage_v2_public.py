"""Public synthetic tests; no private lesson audio, images or transcribed speech."""
import json
import unittest
from artin_14_machine_conflict_triage_v2 import wording_class, normalize, public_projection

class PublicPersianLexicalTests(unittest.TestCase):
    def test_negated_past_tense_was_missed_by_v1(self):
        self.assertEqual(wording_class('ورود نکردم'),'NEGATED_ENTRY_WORDING')
    def test_negated_plural_past_tense(self):
        self.assertEqual(wording_class('وارد معامله نشدم'),'NEGATED_ENTRY_WORDING')
        self.assertEqual(wording_class('ورود نکردیم'),'NEGATED_ENTRY_WORDING')
    def test_negative_with_persian_zwnj(self):
        self.assertEqual(wording_class('اینجا ورود نمی‌کنیم'),'NEGATED_ENTRY_WORDING')
    def test_direct_positive_action_candidate(self):
        self.assertEqual(wording_class('اینجا ورود میکنیم'),'POSITIVE_ENTRY_ACTION_WORDING')
    def test_nominal_reference_is_not_action_decision(self):
        self.assertEqual(wording_class('ورود به پوزیشن'),'ENTRY_REFERENCE_WITHOUT_ACTION_ASSERTION')
    def test_generic_positive_advice_not_action_decision(self):
        self.assertEqual(wording_class('ورودتون مناسب باشه'),'ENTRY_REFERENCE_WITHOUT_ACTION_ASSERTION')
    def test_unrelated_word(self):
        self.assertEqual(wording_class('چه رنگی؟'),'NO_ENTRY_WORD')
    def test_public_redaction(self):
        synthetic={'summary':{'distinct_pairs':1,'mt5_trades_authorized':0},'cases':[{
          'pair_number_original':1,'session':19,'route_ids':['SYNTHETIC'],
          'screen_type_visually_observed':'WEBINAR_ROOM_NO_TRADING_CHART_VISIBLE',
          'v2_wording_status':'FALSE_LEXICAL_FLIP_BOTH_WORDINGS_NEGATED',
          'utterances':[{'machine_text_unverified':'SECRET'}],
          'source_wav_sha256':'SECRET_SHA', 'trade_permitted':False}]}
        p=public_projection(synthetic);out=json.dumps(p)
        self.assertNotIn('SECRET',out);self.assertNotIn('SHA',out)
        self.assertEqual(p['cases'][0]['trade_permitted'],False)

if __name__=='__main__':unittest.main()