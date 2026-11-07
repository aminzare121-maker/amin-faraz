"""Regression tests; invented trace examples are NOT real classroom evidence."""
import unittest

from teacher_evidence_gate import audit_candidate, inventory, summarize_audits


def complete_synthetic_candidate(**changes):
    value = dict(
        status='ELIGIBLE', side='BUY', rule_id='BREAK_STRONG',
        input_fingerprint='synthetic-sha-not-a-proof',
        sources=[[21, 2105, 2261]],
        missing_dependencies=[], future_dependencies=[],
        context_required_keys=[], policy_required_keys=[],
        derived_required_keys=['decision_close'],
        dependency_facts={'decision_close': {
            'value':'4000', 'known_at':900,
            'source':'synthetic-CSV-closed-bar', 'origin':'DERIVED_FROM_RAW'}},
    )
    value.update(changes)
    return value


class TeacherEvidenceGateTests(unittest.TestCase):
    def test_every_raw_only_fact_still_requires_original_classroom_review(self):
        audit = audit_candidate(complete_synthetic_candidate(), 900)
        self.assertEqual(audit['reason'], 'ORIGINAL_TEACHER_DIALOGUE_VISUAL_AND_CASES_NOT_VERIFIED')
        self.assertFalse(audit['can_execute_as_teacher_method'])
        self.assertFalse(audit['teacher_rule_verified'])

    def test_unregistered_rule_fails_closed(self):
        result = audit_candidate(complete_synthetic_candidate(rule_id='INVENTED_RULE'), 900)
        self.assertEqual(result['reason'], 'UNREGISTERED_RULE')

    def test_s22_hypothesis_fails_closed_even_if_it_says_eligible(self):
        result = audit_candidate(complete_synthetic_candidate(
            rule_id='STOPPUNCH_S22_SELL_CONFIRMED_PAUSE', side='SELL'), 900)
        self.assertEqual(result['reason'], 'EXPLICIT_RESEARCH_HYPOTHESIS_NOT_CONFIRMED_TEACHER_FORMULA')

    def test_context_is_not_teacher_verification(self):
        result = audit_candidate(complete_synthetic_candidate(
            context_required_keys=['sentiment_permission']),900)
        self.assertEqual(result['reason'], 'EXTERNAL_CONTEXT_NEEDS_SOURCE_REVIEW')

    def test_research_policy_is_not_teacher_verification(self):
        result = audit_candidate(complete_synthetic_candidate(
            policy_required_keys=['sentiment_permission']),900)
        self.assertEqual(result['reason'], 'RESEARCH_DIRECTION_POLICY_NEEDS_SOURCE_REVIEW')

    def test_missing_required_fact_prevents_promotion(self):
        result = audit_candidate(complete_synthetic_candidate(
            missing_dependencies=['trend_strength']),900)
        self.assertEqual(result['reason'], 'RAW_TRACE_HAS_MISSING_DEPENDENCIES')

    def test_future_information_prevents_promotion(self):
        result = audit_candidate(complete_synthetic_candidate(
            future_dependencies=['decision_close']),900)
        self.assertEqual(result['reason'], 'RAW_TRACE_USES_FUTURE_DEPENDENCIES')

    def test_future_fact_timestamp_prevents_promotion(self):
        c=complete_synthetic_candidate()
        c['dependency_facts']['decision_close']['known_at']=901
        result=audit_candidate(c,900)
        self.assertEqual(result['reason'],'RAW_TRACE_FACT_PROVENANCE_INVALID')

    def test_incomplete_trace_not_trusted(self):
        c=complete_synthetic_candidate()
        del c['dependency_facts']
        result=audit_candidate(c,900)
        self.assertEqual(result['reason'],'RAW_TRACE_PROVENANCE_FIELDS_MISSING')

    def test_context_fact_not_verified_by_a_source_string(self):
        c=complete_synthetic_candidate()
        c['dependency_facts']['sentiment_permission']={
            'value':'LONG_ONLY','known_at':800,'source':'session9:300',
            'origin':'SOURCED_CONTEXT'}
        result=audit_candidate(c,900)
        self.assertEqual(result['reason'],'UNREVIEWED_CONTEXT_ORIGIN')

    def test_class_source_inventory_is_not_a_recording_review(self):
        report=inventory()
        self.assertEqual(report['kind'],'FILE_AVAILABILITY_INVENTORY_NOT_COMPLETED_LISTENING')
        self.assertIn(1, report['sessions_without_audio'])
        self.assertFalse(report['independently_reheard_entire_course_in_this_work'])

    def test_summary_never_claims_teacher_execution(self):
        a=[audit_candidate(complete_synthetic_candidate(),900)]
        result=summarize_audits(a)
        self.assertEqual(result['can_execute_as_teacher_method'],0)
        self.assertTrue(result['all_teacher_provenance_gates_closed'])


if __name__=='__main__':
    unittest.main()
