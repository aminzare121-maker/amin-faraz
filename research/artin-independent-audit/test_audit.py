import unittest
from audit import assess
class EvidenceTests(unittest.TestCase):
    def test_asr_only_not_full_rule(self):self.assertFalse(assess({'source_sha256':'a'*64})['extractable_for_review'])
    def test_undefined_fraction_blocked(self):self.assertIn('stop_definition',assess({'stop_definition':None})['missing'])
    def test_conflict_not_silently_resolved(self):self.assertIn('unresolved_conflicts',assess({'conflicts':['USD dominance versus gold exception']})['missing'])
    def test_complete_description_not_profit_proof(self):
        rule=dict(source_sha256='a'*64,visual_confirmation=True,audio_confirmation=True,entry_definition='synthetic defined',stop_definition='synthetic defined',volume_definition='synthetic defined',causal_confirmation_time=1)
        result=assess(rule);self.assertEqual(result['market_efficacy'],'NOT_ESTABLISHED');self.assertFalse(result['trade_authority'])
    def test_no_engine_created(self):self.assertFalse(assess({})['engine_created'])
    def test_true_is_not_hash_or_time(self):self.assertIn('source_hash_invalid',assess({'source_sha256':True,'causal_confirmation_time':True})['missing'])
if __name__=='__main__':unittest.main()
