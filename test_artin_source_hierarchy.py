import unittest
from artin_source_hierarchy import resolve_priority, candidate_rule_with_pdf_ok

H = 'a'*64

def model():
    return {
        'oral_evidence': {
            'session': 15, 'audio_sha256': H, 'start_seconds': 1546.15,
            'end_seconds': 1551.0, 'speaker_is_teacher_verified': True,
            'words_checked_against_original_audio': True,
            'meaning_reviewed_against_context': True,
            'teacher_decision': 'NO_TRADE',
            'entry_exit_exception_order_complete': False,
            'independent_motor_comparison_passed': False,
        },
        'pdf_reference': {
            'page': 15, 'pdf_sha256': 'f50f66139fa96c8083e936f368160c3b77667302174e3e1c6084c8bbd6a1a909',
            'meaning_conflict_with_oral': False,
            'claim_of_teacher_speech_verified': False,
            'trade_permission': False,
        },
    }

class HierarchyTests(unittest.TestCase):
    def test_verified_oral_primary_pdf_secondary(self):
        x=resolve_priority(model())
        self.assertEqual(x['status'],'ORAL_PRIMARY_CONTEXT_REVIEWED')
        self.assertEqual(x['authority'],'ORIGINAL_TEACHER_SPEECH')
        self.assertFalse(x['decision_certified'])
        self.assertFalse(x['mt5_trade_allowed'])
    def test_pdf_without_oral_cannot_create_rule(self):
        d=model(); del d['oral_evidence']
        self.assertEqual(resolve_priority(d)['status'],'ORAL_SOURCE_MISSING')
        self.assertFalse(candidate_rule_with_pdf_ok(d)[0])
    def test_machine_asr_not_independently_checked(self):
        d=model();d['oral_evidence']['words_checked_against_original_audio']=False
        self.assertEqual(resolve_priority(d)['status'],'ORAL_AUDIO_REVIEW_REQUIRED')
    def test_pdf_disagreement_is_not_silent_oral_replacement(self):
        d=model();d['pdf_reference']['meaning_conflict_with_oral']=True
        r=resolve_priority(d)
        self.assertEqual(r['status'],'ORAL_PRIMARY_PDF_CONFLICT_FLAGGED')
        self.assertEqual(r['oral_expected_decision'],'NO_TRADE')
        self.assertFalse(candidate_rule_with_pdf_ok(d)[0])
    def test_later_lesson_claim_unverified(self):
        d=model();d['oral_evidence']['later_session_correction_claimed']=True
        self.assertEqual(resolve_priority(d)['status'],'LATER_LESSON_CORRECTION_UNVERIFIED')
    def test_verified_later_lesson_still_needs_motor_review(self):
        d=model();d['oral_evidence'].update(later_session_correction_claimed=True,later_correction_verified=True)
        self.assertEqual(resolve_priority(d)['status'],'ORAL_PRIMARY_CONTEXT_REVIEWED')
        self.assertFalse(resolve_priority(d)['mt5_trade_allowed'])
    def test_invalid_pdf_page(self):
        d=model();d['pdf_reference']['page']=20
        self.assertEqual(resolve_priority(d)['status'],'INVALID_PDF_PROVENANCE')
    def test_pdf_cannot_claim_oral_verified(self):
        d=model();d['pdf_reference']['claim_of_teacher_speech_verified']=True
        self.assertEqual(resolve_priority(d)['status'],'IMPROPER_PDF_PROMOTION')
    def test_page_only_mention_cannot_authorize_trade(self):
        d=model();d['pdf_reference']['trade_permission']=True
        self.assertFalse(resolve_priority(d)['mt5_trade_allowed'])
    def test_missing_original_sha(self):
        d=model();d['oral_evidence']['audio_sha256']='bad'
        self.assertEqual(resolve_priority(d)['status'],'INVALID_ORAL_ANCHOR')
    def test_legacy_rule_without_pdf_unchanged(self):
        self.assertTrue(candidate_rule_with_pdf_ok({})[0])
    def test_pdf_conflict_missing_explicit_resolved_state(self):
        d=model();d['oral_evidence']['meaning_reviewed_against_context']=False
        self.assertEqual(resolve_priority(d)['status'],'ORAL_MEANING_REVIEW_REQUIRED')

if __name__=='__main__': unittest.main()