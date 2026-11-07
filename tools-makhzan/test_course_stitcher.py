"""Regression for real first source and SYNTHETIC future class stitching."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from course_stitcher import (
    validate_course, register_lesson, append_evidence, link_lessons, course_puzzle,
    hydrate_persistent_anchors
)

HERE=Path(__file__).resolve().parent
def first():
    return json.loads((HERE/"courses"/"artin"/"COURSE_REGISTRY.json").read_text(encoding="utf8"))

def fictional_second():
    # This is TEST DATA, not a claim that user has sent another class.
    return {
       "session_id":"ARTIN-TEST-002","sequence":2,
       "source_label":"SYNTHETIC_FOR_TESTS_ONLY.mp4",
       "submitted_by_user":True,
       "source_page":"https://my.uupload.ir/p/synthetic",
       "source_sha256":"c"*64,
       "duration_seconds":600,"chunks_5min":2,
       "evidence_status":"TEST_ONLY","verified_strategy_rules":0
    }

def demo_nodes():
    return [
      {"evidence_id":"EVID-J2-001","session_id":"ARTIN-J2-001",
       "video_sha256":first()["registered_sessions"][0]["source_sha256"],
       "start_seconds":50.0,"end_seconds":55.0,
       "source_media_sha256":"b"*64,"modality":"speech",
       "topic_id":"TOPIC-FOREX-INTRO","review_status":"UNVERIFIED",
       "can_trade":False},
      {"evidence_id":"EVID-TEST-002","session_id":"ARTIN-TEST-002",
       "video_sha256":"c"*64,
       "start_seconds":70.0,"end_seconds":81.0,
       "source_media_sha256":"d"*64,"modality":"speech",
       "topic_id":"TOPIC-FOREX-INTRO","review_status":"UNVERIFIED",
       "can_trade":False}
    ]

class MultiSessionPuzzleTests(unittest.TestCase):
    def test_source_anchors_from_actual_first_video_are_not_empty_anymore(self):
        live=hydrate_persistent_anchors(first(),HERE.parent)
        report=course_puzzle(live)
        self.assertEqual(report["registered_user_submitted_sessions"],1)
        self.assertEqual(report["registered_original_source_evidence"],2094)
        self.assertEqual(len(report["topic_chains"]),2)
        self.assertFalse(report["ready_to_issue_teacher_rules"])
        self.assertEqual(len(live["cross_session_links"]),0)

    def test_actual_original_2035_speech_and_59_question_sources_have_no_private_text(self):
        live=hydrate_persistent_anchors(first(),HERE.parent)
        speech=[n for n in live["evidence_nodes"] if n["modality"]=="speech"]
        chat=[n for n in live["evidence_nodes"] if n["modality"]=="chat"]
        self.assertEqual(len(speech),2035)
        self.assertEqual(len(chat),59)
        self.assertEqual(sum("unverified_rule_candidate_id" in n for n in speech),35)
        self.assertTrue(all("text" not in n and "candidate_text" not in n for n in live["evidence_nodes"]))
        self.assertTrue(all(n["can_trade"] is False for n in live["evidence_nodes"]))

    def test_actual_first_video_registered_as_waiting_session_one(self):
        x=first()
        sessions,nodes=validate_course(x)
        self.assertEqual(list(sessions),["ARTIN-J2-001"])
        self.assertEqual(x["registered_sessions"][0]["chunks_5min"],17)
        self.assertEqual(len(nodes),0)
        self.assertIsNone(x["session_count_expected"])
        self.assertFalse(x["all_sessions_received_confirmed_by_user"])
        self.assertFalse(course_puzzle(x)["ready_to_issue_teacher_rules"])

    def test_next_video_registration_preserves_first_video_byte_for_byte(self):
        x=first()
        old=deepcopy(x["registered_sessions"][0])
        combined=register_lesson(x,fictional_second())
        self.assertEqual(x["registered_sessions"],[old])
        self.assertEqual(combined["registered_sessions"][0],old)
        self.assertEqual([s["sequence"] for s in combined["registered_sessions"]],[1,2])

    def test_repeat_same_video_is_rejected_not_rerun_as_new(self):
        x=first()
        another=fictional_second()
        another["source_sha256"]=x["registered_sessions"][0]["source_sha256"]
        with self.assertRaisesRegex(ValueError,"repeated"):
            register_lesson(x,another)

    def test_unknown_unsent_lesson_cannot_have_evidence(self):
        x=first()
        with self.assertRaisesRegex(ValueError,"user has not sent"):
            append_evidence(x,[demo_nodes()[1]])

    def test_compatible_lesson_fragments_linked_like_puzzle(self):
        x=register_lesson(first(),fictional_second())
        x=append_evidence(x,demo_nodes())
        x=link_lessons(x,[{"link_id":"LINK-J2-TO-J3",
            "earlier_evidence_id":"EVID-J2-001",
            "later_evidence_id":"EVID-TEST-002",
            "relationship":"CONTINUES",
            "review_status":"UNVERIFIED","can_trade":False}])
        report=course_puzzle(x)
        self.assertEqual(report["registered_user_submitted_sessions"],2)
        self.assertEqual(report["linked_cross_session_evidence_count"],1)
        self.assertEqual(report["topic_chains"][0]["source_evidence_count"],2)
        self.assertEqual(report["topic_chains"][0]["session_ids_in_order"],
                         ["ARTIN-J2-001","ARTIN-TEST-002"])
        self.assertFalse(report["ready_to_issue_teacher_rules"])
        self.assertTrue(report["old_evidence_retained"])

    def test_later_teacher_correction_keeps_original_unverified(self):
        x=register_lesson(first(),fictional_second())
        x=append_evidence(x,demo_nodes())
        x=link_lessons(x,[{"link_id":"LINK-CORRECTS-J2",
            "earlier_evidence_id":"EVID-J2-001",
            "later_evidence_id":"EVID-TEST-002",
            "relationship":"CORRECTS","review_status":"UNVERIFIED",
            "can_trade":False}])
        t=course_puzzle(x)["topic_chains"][0]
        self.assertEqual(t["corrections_or_exceptions_not_reconciled"],1)
        self.assertEqual(t["source_evidence_ids_in_order"],["EVID-J2-001","EVID-TEST-002"])
        self.assertFalse(t["complete_instructor_rule_certified"])

    def test_corrected_lesson_cannot_erase_earlier_evidence(self):
        x=register_lesson(first(),fictional_second())
        x=append_evidence(x,demo_nodes())
        with self.assertRaisesRegex(ValueError,"Never erase"):
            link_lessons(x,[{"link_id":"LINK-BAD-CORRECTION",
               "earlier_evidence_id":"EVID-J2-001",
               "later_evidence_id":"EVID-TEST-002",
               "relationship":"CORRECTS","review_status":"UNVERIFIED",
               "replaces_earlier_evidence":True}])

    def test_model_cannot_verify_amendment_without_human_source_proof(self):
        x=register_lesson(first(),fictional_second())
        x=append_evidence(x,demo_nodes())
        with self.assertRaisesRegex(ValueError,"independently reviewed"):
            link_lessons(x,[{"link_id":"LINK-FAKE-CONFIRMED",
               "earlier_evidence_id":"EVID-J2-001",
               "later_evidence_id":"EVID-TEST-002",
               "relationship":"EXCEPTION","review_status":"SOURCE_HUMAN_REVIEWED"}])

    def test_cannot_reverse_session_time(self):
        x=register_lesson(first(),fictional_second())
        x=append_evidence(x,demo_nodes())
        with self.assertRaisesRegex(ValueError,"earlier to a later"):
            link_lessons(x,[{"link_id":"LINK-BACKWARD",
              "earlier_evidence_id":"EVID-TEST-002",
              "later_evidence_id":"EVID-J2-001",
              "relationship":"EXPLAINS","review_status":"UNVERIFIED"}])

    def test_fabricated_third_session_order_rejected(self):
        x=first();second=fictional_second();second["sequence"]=3
        with self.assertRaisesRegex(ValueError,"follow the previous"):
            register_lesson(x,second)

    def test_when_user_later_confirms_course_complete_meaning_still_unproven(self):
        x=register_lesson(first(),fictional_second())
        x["all_sessions_received_confirmed_by_user"]=True
        x["next_intake_status"]="COURSE_CLOSED_BY_USER_PENDING_VALIDATION"
        summary=course_puzzle(x)
        self.assertEqual(summary["current_status"],"SOURCE_REVIEW_AND_CONSISTENCY_CHECK_REQUIRED")
        self.assertFalse(summary["ready_to_issue_teacher_rules"])

    def test_source_hash_mixup_across_sessions_rejected(self):
        x=register_lesson(first(),fictional_second())
        n=demo_nodes()
        n[1]["video_sha256"]=n[0]["video_sha256"]
        with self.assertRaisesRegex(ValueError,"source video SHA"):
            append_evidence(x,n)

    def test_no_new_videos_must_not_falsely_claim_complete_course(self):
        x=first()
        x["next_intake_status"]="COMPLETE"
        with self.assertRaisesRegex(ValueError,"cannot be called complete"):
            course_puzzle(x)

if __name__=="__main__":
    unittest.main()
