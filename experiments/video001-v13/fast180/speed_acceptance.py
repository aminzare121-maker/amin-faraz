"""VIDEO-001 V13 strict acceptance of an actual end-to-end <=180s extraction.

Pure verification; NEVER changes a source file or extracted raw evidence.
A fast source index/ASR/OCR run is not a verified teacher lesson. Evidence
must come from the actual run, not a replay or an archive-only benchmark.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median

SHA = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_STAGES = (
    "receive_source", "prepare_source", "transcribe_audio", "read_chat",
    "read_board_and_actions", "verify_source_and_meaning", "persist_text_evidence",
)
TARGET_SECONDS = 180.0


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Missing authenticated UTC run timestamp")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Malformed UTC run timestamp") from exc
    if d.tzinfo is None or d.utcoffset().total_seconds() != 0:
        raise ValueError("UTC offset-aware timestamp required")
    return d.astimezone(timezone.utc)


def _positive_int(v):
    return type(v) is int and v > 0


def evaluate_run(record):
    """Return conservative machine-auditable verdict for one measured film.

    PASS requires independent human-verified speech/visual references, full
    source-to-text coverage, actual storage receipt, and 180s wall clock.
    Synthetic/archived replay and omitted stages always FAIL CLOSED.
    """
    reasons = []
    if not isinstance(record, dict):
        raise ValueError("Run record must be a dictionary")
    ident = record.get("source_video_sha256")
    if not isinstance(ident, str) or not SHA.fullmatch(ident):
        reasons.append("SOURCE_SHA256_MISSING")
    if record.get("actual_original_source_downloaded_this_run") is not True:
        reasons.append("SOURCE_NOT_RECEIVED_IN_THIS_RUN")
    if record.get("source_unchanged") is not True:
        reasons.append("SOURCE_MUTATION_OR_UNVERIFIED")
    if record.get("archive_replay_only") is not False:
        reasons.append("ARCHIVED_REPLAY_NOT_END_TO_END")
    if record.get("production_v12_unchanged") is not True:
        reasons.append("PRODUCTION_V12_NOT_PROTECTED")
    if record.get("raw_transcripts_unchanged") is not True:
        reasons.append("RAW_TRANSCRIPTS_NOT_PROTECTED")
    duration = record.get("original_duration_seconds")
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        reasons.append("VIDEO_DURATION_INVALID")
        duration = 0
    if duration and not (4800 <= duration <= 5700):
        reasons.append("NOT_80_TO_95_MINUTE_FILM")
    start, done = None, None
    try:
        start = _timestamp(record.get("receipt_started_utc"))
        done = _timestamp(record.get("text_archive_committed_utc"))
    except ValueError:
        reasons.append("MISSING_COMPLETE_WALL_CLOCK")
    wall = (done - start).total_seconds() if start and done else None
    if wall is not None and (wall <= 0 or wall > TARGET_SECONDS):
        reasons.append("WALL_CLOCK_EXCEEDS_180_SECONDS" if wall > TARGET_SECONDS else "WALL_CLOCK_INVALID")
    stages = record.get("stages")
    if not isinstance(stages, dict):
        reasons.append("STAGE_TIMESTAMPS_MISSING")
        stages = {}
    for stage in REQUIRED_STAGES:
        item = stages.get(stage)
        if not isinstance(item, dict):
            reasons.append("MISSING_STAGE_" + stage.upper())
            continue
        try:
            s = _timestamp(item.get("started_utc")); e = _timestamp(item.get("completed_utc"))
            if s > e or (start and s < start) or (done and e > done):
                raise ValueError("Stage outside full wall clock")
        except ValueError:
            reasons.append("INVALID_STAGE_TIME_" + stage.upper())
    # An image index alone cannot certify that the content in the image was
    # converted to text: reject image-only output or skipped handwriting.
    expected_parts = math.ceil(duration / 300) if duration else None
    if record.get("asr_global_chunks") != expected_parts or not expected_parts:
        reasons.append("INCOMPLETE_AUDIO_PARTS")
    if record.get("all_asr_chunks_source_sha_verified") is not True:
        reasons.append("AUDIO_PROVENANCE_UNVERIFIED")
    if record.get("asr_spoken_segments", 0) <= 0:
        reasons.append("NO_SPOKEN_TEXT")
    chat = record.get("chat_frames_selected")
    if not _positive_int(chat) or record.get("chat_frames_ocr_attempted") != chat:
        reasons.append("INCOMPLETE_CHAT_OCR")
    if record.get("chat_ocr_failed_frames") != 0:
        reasons.append("FAILED_CHAT_OCR")
    if record.get("one_second_chat_frames_scanned", 0) < math.floor(duration):
        reasons.append("INCOMPLETE_ONE_SECOND_CHAT_SCAN")
    board = record.get("board_frames_selected")
    if not _positive_int(board) or record.get("board_frames_textualized") != board:
        reasons.append("BOARD_NOT_ALL_TEXTUALIZED")
    if record.get("visual_actions_textualized") is not True:
        reasons.append("VISUAL_ACTIONS_NOT_TEXTUALIZED")
    if record.get("typed_question_text_retained") is not True:
        reasons.append("TYPED_QUESTIONS_NOT_RETAINED")
    if record.get("raw_text_evidence_loss") != 0:
        reasons.append("RAW_TEXT_LOSS")
    if record.get("source_and_text_hashes_verified") is not True:
        reasons.append("TEXT_PROVENANCE_UNVERIFIED")
    if record.get("private_text_archive_committed") is not True:
        reasons.append("FINAL_TEXT_ARCHIVE_NOT_PERSISTED")
    # Validate accuracy independently; OCR engine 'completed' only proves
    # that inference ran, NOT that instructions, negations or screenshots
    # were interpreted correctly.
    audit = record.get("independent_quality_review")
    if not isinstance(audit, dict):
        reasons.append("NO_INDEPENDENT_QUALITY_REVIEW")
    else:
        if audit.get("speech_gold_pass") is not True:
            reasons.append("SPEECH_GOLD_REVIEW_NOT_PASSED")
        if audit.get("visual_gold_pass") is not True:
            reasons.append("VISUAL_GOLD_REVIEW_NOT_PASSED")
        if audit.get("speaker_and_qa_gold_pass") is not True:
            reasons.append("QUESTION_ANSWER_REVIEW_NOT_PASSED")
        if audit.get("critical_negation_mismatches") != 0:
            reasons.append("CRITICAL_NEGATION_ERRORS")
        if audit.get("teacher_rule_attribution_pass") is not True:
            reasons.append("TEACHER_RULE_ATTRIBUTION_NOT_PASSED")
        if not _positive_int(audit.get("independently_annotated_reference_count")):
            reasons.append("GOLD_REFERENCE_UNAVAILABLE")
    return {
        "schema": "video001_v13_real_under_180_gate_v1",
        "source_video_sha256": ident,
        "measured_full_wall_clock_seconds": wall,
        "target_seconds": TARGET_SECONDS,
        "full_video_under_three_minutes_verified": not reasons,
        "status": "REAL_END_TO_END_QUALITY_VERIFIED_PASS" if not reasons else "NOT_VERIFIED_NOT_3MIN_PASS",
        "blocking_reasons": sorted(set(reasons)),
        "source_media_or_raw_text_changed": False,
        "raw_teacher_rules_promoted": False,
    }


def evaluate_repeated(records):
    if not isinstance(records, list) or len(records) < 3:
        return {"approved": False, "reason": "THREE_REAL_REPEAT_RUNS_REQUIRED"}
    checks = [evaluate_run(r) for r in records]
    ids = {(r.get("source_video_sha256"),r.get("hardware_id"),r.get("asr_model"),r.get("ocr_model"),r.get("visual_model")) for r in records}
    if len(ids) != 1 or any(not all(x for x in identity) for identity in ids):
        return {"approved": False, "reason": "INCOMPARABLE_HARDWARE_OR_MODELS", "runs": checks}
    if not all(c["full_video_under_three_minutes_verified"] for c in checks):
        return {"approved": False, "reason": "AT_LEAST_ONE_REAL_RUN_FAILED", "runs": checks}
    return {"approved": True, "reason": "THREE_REAL_FULL_QUALITY_RUNS_UNDER_180", "median_seconds": median(c["measured_full_wall_clock_seconds"] for c in checks), "runs": checks}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True, help="JSON list containing 3 real source-to-saved-text run receipts")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    x = evaluate_repeated(json.loads(args.receipts.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("V13_REAL_180_SECONDS=" + x["reason"])
    raise SystemExit(0 if x["approved"] else 2)


if __name__ == "__main__":
    main()