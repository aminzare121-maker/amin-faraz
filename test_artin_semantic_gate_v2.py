import unittest
from artin_semantic_gate_v2 import audit

SHA = "a" * 64

def fixture():
    return {"source_registry": {"1": SHA}, "sessions": [{"session": 1, "rules": [{
        "kind": "entry", "cross_session_checked": True, "ambiguity_resolved": True,
        "evidence": [
            {"modality": "speech", "source_sha256": SHA, "start": 1, "end": 3, "evidence_id": "asr"},
            {"modality": "image", "source_sha256": SHA, "start": 2, "end": 2.5, "evidence_id": "frame"}],
        "independent_comparison": {"teacher_example_id": "example", "reviewer": "test-reviewer",
            "review_evidence_id": "review-1", "expected_decision": "ENTER",
            "observed_decision": "ENTER", "independent": True, "review_result": "PASS"}
    }]}]}

class Tests(unittest.TestCase):
    def test_empty(self):
        self.assertFalse(audit({"sessions": []})["complete"])
    def test_valid_structure_not_semantic(self):
        self.assertEqual(audit(fixture())["sessions"][0]["status"], "STRUCTURALLY_REVIEWED")
        self.assertFalse(audit(fixture())["semantic_fidelity_certified"])
    def test_timestamp_disagreement(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["evidence"][1].update({"start": 4, "end": 5})
        self.assertIn("av_timestamps_do_not_overlap", audit(d)["errors"][0])
    def test_source_mismatch(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["evidence"][1]["source_sha256"] = "b" * 64
        self.assertIn("invalid_or_unmatched_source_anchor", audit(d)["errors"][0])
    def test_review_proof_missing(self):
        d = fixture()
        del d["sessions"][0]["rules"][0]["independent_comparison"]["review_evidence_id"]
        self.assertIn("comparison_not_verified", audit(d)["errors"][0])
    def test_empty_rules_fail(self):
        d = fixture()
        d["sessions"][0]["rules"] = []
        self.assertEqual(audit(d)["sessions"][0]["status"], "UNVERIFIED")

    def test_hypothetical_market_scenario_is_valid_teaching_example(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["teaching_scenario"] = {
            "kind": "hypothetical_market_state",
            "market_state": "If price breaks resistance and retests, consider entry",
            "claims_observed_trade": False,
        }
        result = audit(d)
        self.assertEqual(result["sessions"][0]["status"], "STRUCTURALLY_REVIEWED")
        self.assertFalse(result["semantic_fidelity_certified"])

    def test_hypothetical_must_not_claim_historical_execution(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["teaching_scenario"] = {
            "kind": "hypothetical_market_state",
            "market_state": "Suppose price rejects resistance",
            "claims_observed_trade": True,
        }
        self.assertIn("hypothetical_falsely_claims_observed_trade", audit(d)["errors"][0])

    def test_unproven_historical_claim_rejected(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["teaching_scenario"] = {
            "kind": "observed_market_state",
            "market_state": "Price retests support in archived chart",
            "source_observation_verified": False,
        }
        self.assertIn("unverified_historical_observation", audit(d)["errors"][0])

    def test_verified_source_observation_is_structural_only(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["teaching_scenario"] = {
            "kind": "observed_market_state",
            "market_state": "Chart shows a test of support",
            "source_observation_verified": True,
            "observation_evidence_id": "frame-source-01",
        }
        result = audit(d)
        self.assertEqual(result["sessions"][0]["status"], "STRUCTURALLY_REVIEWED")
        self.assertFalse(result["semantic_fidelity_certified"])

    def test_hypothetical_without_market_state_rejected(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["teaching_scenario"] = {
            "kind": "hypothetical_market_state",
            "claims_observed_trade": False,
        }
        self.assertIn("missing_scenario_market_state", audit(d)["errors"][0])

    def test_teacher_pdf_alone_cannot_certify_rule(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["pdf_reference"] = {
            "page": 14, "pdf_sha256": "f50f66139fa96c8083e936f368160c3b77667302174e3e1c6084c8bbd6a1a909",
        }
        self.assertIn("pdf_source_priority_oral_source_missing", audit(d)["errors"][0])

    def test_machine_asr_plus_pdf_not_enough(self):
        d = fixture()
        d["sessions"][0]["rules"][0].update(
            pdf_reference={"page": 15, "pdf_sha256": "f50f66139fa96c8083e936f368160c3b77667302174e3e1c6084c8bbd6a1a909"},
            oral_evidence={"session": 1, "audio_sha256": SHA, "start_seconds": 1,
                           "end_seconds": 3, "speaker_is_teacher_verified": False,
                           "words_checked_against_original_audio": False}
        )
        self.assertIn("pdf_source_priority_oral_audio_review_required", audit(d)["errors"][0])

    def test_reviewed_oral_with_pdf_stays_structural(self):
        d = fixture()
        d["sessions"][0]["rules"][0].update(
            pdf_reference={"page": 13, "pdf_sha256": "f50f66139fa96c8083e936f368160c3b77667302174e3e1c6084c8bbd6a1a909"},
            oral_evidence={"session": 1, "audio_sha256": SHA, "start_seconds": 1,
                           "end_seconds": 3, "speaker_is_teacher_verified": True,
                           "words_checked_against_original_audio": True,
                           "meaning_reviewed_against_context": True,
                           "teacher_decision": "ENTER"}
        )
        result = audit(d)
        self.assertEqual(result["sessions"][0]["status"], "STRUCTURALLY_REVIEWED")
        self.assertFalse(result["semantic_fidelity_certified"])

    def test_pdf_conflict_flags_rule_for_review(self):
        d = fixture()
        d["sessions"][0]["rules"][0].update(
            pdf_reference={"page": 14, "pdf_sha256": "f50f66139fa96c8083e936f368160c3b77667302174e3e1c6084c8bbd6a1a909",
                           "meaning_conflict_with_oral": True},
            oral_evidence={"session": 1, "audio_sha256": SHA, "start_seconds": 1,
                           "end_seconds": 3, "speaker_is_teacher_verified": True,
                           "words_checked_against_original_audio": True,
                           "meaning_reviewed_against_context": True,
                           "teacher_decision": "ENTER"}
        )
        self.assertIn("pdf_source_priority_oral_primary_pdf_conflict_flagged", audit(d)["errors"][0])

if __name__ == "__main__":
    unittest.main()
