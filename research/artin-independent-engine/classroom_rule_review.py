"""Map reviewed teacher/student dialogue claims to Artin rule IDs.

Records are NOT facts until independently checked against audio/video. This
module inventories corrections and unresolved answers for the decision gate;
it cannot authorize a trade. Its output intentionally has no approval flag.
"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from entry_engine import RULE_IDS

SCHEMA = "artin_dialogue_review_v1"
RELATIONS = frozenset(("INTRODUCES", "ANSWERS_QUESTION", "CLARIFIES", "CORRECTS", "EXCEPTION"))


def audit_dialogue_records(doc):
    if not isinstance(doc,dict) or doc.get("schema")!=SCHEMA:
        raise ValueError("Explicit artin dialogue review schema required")
    rows=doc.get("records")
    if not isinstance(rows,list):
        raise ValueError("Dialogue records list required")
    seen=set()
    by_rule=defaultdict(list)
    for r in rows:
        if not isinstance(r,dict):
            raise ValueError("Each dialogue record must be an object")
        rid,rule,relation=r.get("record_id"),r.get("rule_id"),r.get("relation")
        if type(rid) is not str or not rid.strip() or rid in seen:
            raise ValueError("Stable, unique record_id required")
        seen.add(rid)
        if rule not in RULE_IDS:
            raise ValueError("Rule must exist in Artin code registry")
        if relation not in RELATIONS:
            raise ValueError("Explicit educational relation required")
        session,at=r.get("session"),r.get("at_seconds")
        if type(session) is not int or not 1 <= session <= 26 or \
           type(at) not in (int,float) or not 0 <= at <= 100000:
            raise ValueError("Lesson and timestamp required")
        if r.get("speaker") not in ("TEACHER","STUDENT","UNKNOWN"):
            raise ValueError("Speaker attribution must be explicit")
        if relation in ("ANSWERS_QUESTION","CLARIFIES","CORRECTS","EXCEPTION") and \
           r["speaker"] not in ("TEACHER","UNKNOWN"):
            raise ValueError("Student statement is not authoritative teacher answer")
        if relation=="CORRECTS" and not isinstance(r.get("supersedes_record_id"),str):
            raise ValueError("Correction requires superseded record ID")
        if type(r.get("text")) is not str or not r["text"].strip():
            raise ValueError("Review record must preserve actual candidate text")
        by_rule[rule].append(r)
    for record_set in by_rule.values():
        ids={r["record_id"] for r in record_set}
        for r in record_set:
            if r["relation"]=="CORRECTS" and r["supersedes_record_id"] not in ids:
                raise ValueError("Correction reference missing from same-rule records")
        record_set.sort(key=lambda x:(x["session"],x["at_seconds"],x["record_id"]))
        # Preserve actual time order; never assume student question = teacher's answer.
        for r in record_set:
            if r["relation"]=="CORRECTS":
                prior=next(x for x in record_set if x["record_id"]==r["supersedes_record_id"])
                if (r["session"],r["at_seconds"]) <= (prior["session"],prior["at_seconds"]):
                    raise ValueError("A correction must occur later than the statement corrected")
    result={}
    for rule in RULE_IDS:
        found=by_rule.get(rule,[])
        questions=[r for r in found if r["speaker"]=="STUDENT"]
        answers=[r for r in found if r["relation"] in ("ANSWERS_QUESTION","CLARIFIES")]
        corrections=[r for r in found if r["relation"]=="CORRECTS"]
        confirmed_questions={r["record_id"] for r in questions
                             if r.get("speaker_verified") is True}
        resolved={r.get("answers_record_id") for r in answers if r.get("speaker_verified") is True
                  and r.get("media_verified") is True and r.get("teacher_answer_reviewed") is True}
        missing_questions=confirmed_questions-resolved
        unverifiable=[r["record_id"] for r in found
                      if r.get("speaker_verified") is not True or
                      r.get("media_verified") is not True]
        unresolved_corrections=[r["record_id"] for r in corrections
                 if r.get("correction_applied_to_code") is not True or
                    not r.get("positive_case_replayed") or not r.get("negative_case_replayed")]
        result[rule]=dict(
            records=len(found),
            declared_questions=len(questions),
            reviewed_answers=sum(r.get("teacher_answer_reviewed") is True and
                                 r.get("media_verified") is True for r in answers),
            unanswered_question_ids=sorted(missing_questions),
            unresolved_correction_ids=unresolved_corrections,
            media_or_speaker_unverified_ids=unverifiable,
            latest_record_id=(found[-1]["record_id"] if found else None),
            latest_text_verified_by_independent_media=False,
            rule_can_trade=False,
            reason=("NO_DIALOGUE_REVIEW_RECORDS" if not found
                    else "STUDENT_QUESTIONS_UNANSWERED" if missing_questions
                    else "TEACHER_CORRECTIONS_NOT_CODE_REPLAYED" if unresolved_corrections
                    else "ORIGINAL_MEDIA_OR_SPEAKER_UNVERIFIED" if unverifiable
                    else "FULL_TEACHER_EXAMPLES_AND_SEMANTICS_UNVERIFIED"),
        )
    return dict(
        schema="artin_classroom_rule_index_v1",
        mode="DIAGNOSTIC_ONLY_NEVER_TRADE_PERMISSION",
        rule_count=len(result), supplied_review_record_count=len(rows),
        independent_media_verified_by_this_program=False,
        rules=result,
    )


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--review-input",type=Path,required=True)
    p.add_argument("--private-index-out",type=Path,required=True)
    args=p.parse_args()
    data=args.review_input.read_bytes()
    report=audit_dialogue_records(json.loads(data.decode("utf-8-sig")))
    report["review_input_sha256"]=hashlib.sha256(data).hexdigest()
    if args.review_input.resolve()==args.private_index_out.resolve():
        p.error("Input and output may not alias")
    args.private_index_out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"review_records":report["supplied_review_record_count"],
                      "rules_with_record":sum(bool(x["records"]) for x in report["rules"].values()),
                      "independently_teacher_verified_rules":0},ensure_ascii=False))


if __name__=="__main__":
    main()
