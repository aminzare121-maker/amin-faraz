"""Tests use fabricated lesson claims; no speaker or teacher is authenticated."""
import unittest

from classroom_rule_review import audit_dialogue_records, SCHEMA
from teacher_evidence_gate import audit_candidate


def rec(rid, relation, speaker, at, **extra):
    item=dict(record_id=rid, rule_id="STOPPUNCH_DOJI_AHEAD",
              session=21, at_seconds=at, relation=relation,
              speaker=speaker, text="جملهٔ کاملاً ساختگی آزمایشی")
    item.update(extra)
    return item


class ClassroomReviewTests(unittest.TestCase):
    def test_empty_index_never_grants_trades(self):
        result=audit_dialogue_records(dict(schema=SCHEMA,records=[]))
        self.assertEqual(result["rule_count"],13)
        self.assertEqual(result["rules"]["BREAK_STRONG"]["reason"],"NO_DIALOGUE_REVIEW_RECORDS")
        self.assertFalse(result["rules"]["BREAK_STRONG"]["rule_can_trade"])

    def test_question_unanswered_even_if_claimed_as_an_answer_in_asr(self):
        q=rec("student-q","INTRODUCES","STUDENT",20,
              speaker_verified=True,media_verified=True)
        a=rec("answer-claim","ANSWERS_QUESTION","TEACHER",30,
              speaker_verified=False,media_verified=False,
              teacher_answer_reviewed=False,answers_record_id="student-q")
        data=audit_dialogue_records(dict(schema=SCHEMA,records=[q,a]))
        status=data["rules"]["STOPPUNCH_DOJI_AHEAD"]
        self.assertEqual(status["reason"],"STUDENT_QUESTIONS_UNANSWERED")
        self.assertEqual(status["unanswered_question_ids"],["student-q"])
        self.assertFalse(status["rule_can_trade"])

    def test_later_teacher_correction_demands_code_replay(self):
        old=rec("teacher-old","INTRODUCES","TEACHER",20,
                speaker_verified=True,media_verified=True)
        new=rec("teacher-new","CORRECTS","TEACHER",40,
                speaker_verified=True,media_verified=True,
                supersedes_record_id="teacher-old")
        status=audit_dialogue_records(dict(schema=SCHEMA,records=[old,new]))["rules"]["STOPPUNCH_DOJI_AHEAD"]
        self.assertEqual(status["reason"],"TEACHER_CORRECTIONS_NOT_CODE_REPLAYED")
        self.assertEqual(status["latest_record_id"],"teacher-new")

    def test_missing_superseded_rule_is_rejected(self):
        new=rec("new","CORRECTS","TEACHER",40,supersedes_record_id="missing")
        with self.assertRaisesRegex(ValueError,"Correction reference missing"):
            audit_dialogue_records(dict(schema=SCHEMA,records=[new]))

    def test_backdated_correction_is_rejected(self):
        old=rec("old","INTRODUCES","TEACHER",40)
        new=rec("new","CORRECTS","TEACHER",20,supersedes_record_id="old")
        with self.assertRaisesRegex(ValueError,"must occur later"):
            audit_dialogue_records(dict(schema=SCHEMA,records=[old,new]))

    def test_student_instruction_cannot_be_authoritative_answer(self):
        bad=rec("student-statement","ANSWERS_QUESTION","STUDENT",20)
        with self.assertRaisesRegex(ValueError,"Student statement"):
            audit_dialogue_records(dict(schema=SCHEMA,records=[bad]))

    def test_even_self_reported_complete_lesson_is_not_semantically_verified(self):
        old=rec("old","INTRODUCES","TEACHER",20,
                speaker_verified=True,media_verified=True,
                teacher_answer_reviewed=True,positive_case_replayed=True,
                negative_case_replayed=True)
        r=audit_dialogue_records(dict(schema=SCHEMA,records=[old]))
        s=r["rules"]["STOPPUNCH_DOJI_AHEAD"]
        self.assertFalse(s["rule_can_trade"])
        self.assertEqual(s["reason"],"FULL_TEACHER_EXAMPLES_AND_SEMANTICS_UNVERIFIED")

    def test_gate_uses_dialogue_review_reason_on_raw_signal(self):
        idx=audit_dialogue_records(dict(schema=SCHEMA,records=[]))
        audit=audit_candidate(dict(status="ELIGIBLE",rule_id="STOPPUNCH_DOJI_AHEAD",side="BUY"),900,classroom_index=idx)
        self.assertEqual(audit["reason"],"DIALOGUE_NO_DIALOGUE_REVIEW_RECORDS")
        self.assertFalse(audit["teacher_rule_verified"])

    def test_fake_approval_flag_cannot_switch_on_trade(self):
        idx=audit_dialogue_records(dict(schema=SCHEMA,records=[]))
        idx["rules"]["STOPPUNCH_DOJI_AHEAD"]["rule_can_trade"]=True
        with self.assertRaisesRegex(ValueError,"cannot grant trade permission"):
            audit_candidate(dict(status="ELIGIBLE",rule_id="STOPPUNCH_DOJI_AHEAD",side="BUY"),900,classroom_index=idx)


if __name__=="__main__":
    unittest.main()
