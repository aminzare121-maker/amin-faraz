"""Reference-based CER/WER quality tests that reject model-only confidence."""
import unittest
from artin_reference_quality_gate_v8 import measure_reference,normal,edit_distance

SHA='a'*64
SRC='b'*64
def example(ref='اگر خرید می‌کنیم',pred=None,channel='chat',at=30):
    return {'source_video_sha256':SHA,'source_media_sha256':SRC,
       'source_timestamp_seconds':at,'channel':channel,
       'reference_checked_against_original':True,
       'original_source_accessible':True,'reviewer_id':'human-reviewer-1',
       'speaker_role_human_verified':True,
       'human_reference_text':ref,'predicted_text':ref if pred is None else pred}


class ReferenceTests(unittest.TestCase):
    def test_persian_arabic_spelling_normalization(self):
        self.assertEqual(normal('عربي ك و ي  '), 'عربی ک و ی')
        self.assertEqual(normal('سلام‌عليكم'), 'سلام علیکم')

    def test_early_three_samples_never_certify_full_class(self):
        refs=[example(at=i) for i in range(3)]
        r=measure_reference(refs)
        self.assertEqual(r['character_error_rate'],0)
        self.assertEqual(r['word_error_rate'],0)
        self.assertFalse(r['sample_passes_quality_gate'])
        self.assertFalse(r['permission_to_trade'])

    def test_buy_sell_reversal_blocks_even_if_general_error_rate_is_small(self):
        refs=[example(ref='اگر قیمت در منطقه مشخص بود خرید می‌کنیم',
                pred='اگر قیمت در منطقه مشخص بود فروش می‌کنیم',at=i)
                for i in range(30)]
        r=measure_reference(refs,max_cer=1,max_wer=1)
        self.assertEqual(r['critical_term_mismatches'],30)
        self.assertFalse(r['sample_passes_quality_gate'])

    def test_direct_buy_versus_do_not_buy_is_semantic_risk(self):
        refs=[example(ref='در صورت شکست این ناحیه بخر',
                      pred='در صورت شکست این ناحیه نخر',at=i)
              for i in range(30)]
        result=measure_reference(refs,max_cer=1,max_wer=1)
        self.assertEqual(result['critical_term_mismatches'],30)
        self.assertFalse(result['sample_passes_quality_gate'])

    def test_negated_farsi_imperative_and_copula_are_critical(self):
        refs=[example(ref='این وضعیت ورود نیست',
                      pred='این وضعیت ورود است',at=i)
              for i in range(30)]
        result=measure_reference(refs,max_cer=1,max_wer=1)
        self.assertEqual(result['critical_term_mismatches'],30)

    def test_unrelated_word_containing_nah_does_not_trigger_negation(self):
        from artin_reference_quality_gate_v8 import critical_presence
        self.assertFalse(critical_presence('نه','خانه'))
        self.assertTrue(critical_presence('نه','نه، خرید نکن'))
        self.assertTrue(critical_presence('نمی',normal('نمی‌فروشیم')))

    def test_strict_three_human_checked_samples_can_pass_sample_only(self):
        refs=[example(at=i) for i in range(3)]
        r=measure_reference(refs,min_cases=3)
        self.assertTrue(r['sample_passes_quality_gate'])
        self.assertEqual(r['status'],'QUALITY_SAMPLE_PASS_ONLY_NOT_TRADE_APPROVAL')
        self.assertFalse(r['all_teacher_strategy_rules_verified'])
        self.assertFalse(r['permission_to_trade'])

    def test_unreviewed_reference_blocks_not_false_zero_error(self):
        r=example()
        r['reference_checked_against_original']=False
        res=measure_reference([r],min_cases=1)
        self.assertIsNone(res['word_error_rate'])
        self.assertFalse(res['sample_passes_quality_gate'])

    def test_unverified_speaker_role_for_asr_is_not_gold(self):
        r=example(channel='speech')
        r['speaker_role_human_verified']=False
        res=measure_reference([r],min_cases=1)
        self.assertEqual(res['unverified_items'],1)

    def test_duplicate_source_fails(self):
        x=example()
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            measure_reference([x,x])

    def test_source_sha_invalid_fails(self):
        x=example();x['source_media_sha256']='bad'
        with self.assertRaisesRegex(ValueError,'SHA256'):
            measure_reference([x])


if __name__=='__main__':unittest.main()
