#!/usr/bin/env python3
"""Bound six formerly absent Artin citations to recovered original-audio-backed ASR.

No listening/speaker/semantic verification; NEVER permits trading. This module
ONLY reconciles existing source evidence and explicitly labels unresolved cases.
Private text and WAV files must never be committed to the public repository.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

EXPECTED_SPANS = (
    ("STOPPUNCH_OPPOSITE_CONFIRMATION", 20, 4100.0, 4133.0),
    ("STOPPUNCH_SAME_COLOUR", 20, 4201.30, 4208.84),
    ("STOPPUNCH_DOJI_AHEAD", 20, 4210.14, 4214.52),
    ("STOPPUNCH_DOJI_TIED", 20, 4210.14, 4214.52),
    ("STOPPUNCH_OPPOSITE_CONFIRMATION", 20, 4214.52, 4223.26),
    ("STOPPUNCH_OPPOSITE_CONFIRMATION", 22, 4694.0, 4728.0),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(restored: dict, remap: dict, audio_directory: Path, *, verify_excerpt_bytes=True) -> dict:
    windows = restored.get("private_review_windows")
    if not isinstance(windows, list) or len(windows) != 6:
        raise ValueError("exactly six source-linked windows required")
    if restored.get("original_audio_chunk_sha_verification_passed") is not True:
        raise ValueError("unverified original audio provenance")
    if restored.get("video_registry_identity_verified") is not True:
        raise ValueError("unverified video identity")
    if (remap.get("legacy_citation_windows") != 24 or
        remap.get("with_current_asr_overlap") != 18 or
        remap.get("without_current_asr_overlap") != 6):
        raise ValueError("unexpected 13-rule legacy mapping baseline")
    if remap.get("teacher_strategy_rules_certified") != 0 or remap.get("m15_trade_backtest_authorized") is not False:
        raise ValueError("unsafe teacher trading baseline")
    actual = [(w.get("entry_rule_id"),w.get("queue_video"),w.get("start_seconds"),w.get("end_seconds")) for w in windows]
    if actual != list(EXPECTED_SPANS):
        raise ValueError("recovered original citations altered or out of order")
    covered = set()
    for rule in remap.get("rules", []):
        for cite in rule.get("source_citations", []):
            covered.add((rule["rule_id"], cite["current_queue_video"], cite["start_seconds"],cite["end_seconds"]))
    if not set(actual).issubset(covered):
        raise ValueError("a recovered citation has no original legacy engine reference")
    timeline = defaultdict(list)
    for i,w in enumerate(windows):
        if not w.get("source_identity_sha_verified") or w.get("teacher_meaning_verified") or w.get("teacher_speaker_verified"):
            raise ValueError("unexpected source authority claims")
        if not w.get("source_audio_sha256") or len(w["source_audio_sha256"]) != 64:
            raise ValueError("missing source audio digest")
        rows = w.get("recovered_machine_asr_segments")
        if not isinstance(rows, list) or not rows:
            raise ValueError("missing recovered machine text")
        if any(not isinstance(r.get("text_unverified"),str) or not r["text_unverified"].strip() or
               r.get("speaker_status") != "UNKNOWN" for r in rows):
            raise ValueError("unreviewed speaker cannot be silently assigned")
        if not any(r["start"] < w["end_seconds"] and r["end"] > w["start_seconds"] for r in rows):
            raise ValueError("no correctly timed overlapping text")
        file = audio_directory / w["audio_excerpt_file"]
        if verify_excerpt_bytes and (not file.is_file() or sha256(file) != w["audio_excerpt_sha256"]):
            raise ValueError("recovered WAV excerpt digest mismatch")
        timeline[w["queue_video"]].append(w)
    unique = {(w["queue_video"],w["start_seconds"],w["end_seconds"]) for w in windows}
    if len(unique) != 5:
        raise ValueError("five unique time intervals expected; one is reused by two hypotheses")
    # Identical time and ASR of two DOJI hypotheses cannot establish distinct teacher rules.
    dojis = [w for w in windows if w["entry_rule_id"].startswith("STOPPUNCH_DOJI_")]
    if (len(dojis) != 2 or dojis[0]["recovered_machine_asr_segments"] != dojis[1]["recovered_machine_asr_segments"] or
        dojis[0]["audio_excerpt_sha256"] != dojis[1]["audio_excerpt_sha256"]):
        raise ValueError("shared ASR evidence for the two day-count hypotheses changed")
    # These are topic-linked snippets, NOT a certified conditional trading rule.
    context_links = [
      {"topic":"zone_condition_and_possible_between_zones_exception",
       "source_window_ids":["ARTIN-RESTORED-02","ARTIN-RESTORED-03","ARTIN-RESTORED-05","ARTIN-RESTORED-06"],
       "interpretation":"PROVISIONAL_ASR_CONTRAST_REQUIRES_ORIGINAL_AUDIO_VISUAL_SPEAKER_REVIEW",
       "candidate_clue":"A zone/gerah qualification appears in video20; full punch between two zones is discussed in video22",
       "must_not_infer":"universal zone veto or unconditional trade permission"},
      {"topic":"day_count_doji_branch_cannot_be_proved_from_shared_segment",
       "source_window_ids":["ARTIN-RESTORED-03","ARTIN-RESTORED-04"],
       "interpretation":"SAME_AUDIO_AND_TEXT_TWO_DIFFERENT_OLD_RULE_IDS_NOT_INDEPENDENT_SUPPORT",
       "must_not_infer":"ahead/tied day counting, confirmations, threshold, risk budget"},
      {"topic":"close_above_reference_ambiguous",
       "source_window_ids":["ARTIN-RESTORED-01"],
       "interpretation":"REQUIRES_BOARD_REFERENT_AND_ORIGINAL_SPEECH_REVIEW",
       "must_not_infer":"which price level, buy/sell direction, SL, TP"},
    ]
    checks = []
    for w in windows:
        checks.append({
            "source_window_id":w["source_window_id"],
            "rule_id":w["entry_rule_id"],
            "queue_video":w["queue_video"],
            "time_seconds":[w["start_seconds"],w["end_seconds"]],
            "video_sha256":w["video_sha256"],
            "source_audio_sha256":w["source_audio_sha256"],
            "original_asr_artifact_id":w["original_asr_artifact_id"],
            "original_audio_artifact_id":w["original_audio_artifact_id"],
            "asr_segment_count":len(w["recovered_machine_asr_segments"]),
            "source_bytes_and_time_verified":True,
            "spoken_words_independently_verified":False,
            "teacher_speaker_independently_verified":False,
            "semantic_rule_verified":False,
            "market_execution_allowed":False,
        })
    return {
      "schema":"artin_v13_six_recovered_teacher_source_audit_v1",
      "legacy_total_source_citations":24,
      "previous_machine_speech_citations":18,
      "newly_recovered_citations":6,
      "machine_speech_citations_now_present":24,
      "unique_new_timed_intervals":5,
      "unique_original_audio_chunks":3,
      "citations_without_machine_asr_after_recovery":0,
      "audio_and_asr_provenance_verified":True,
      "independent_audio_listening_complete":False,
      "video_frame_teacher_semantics_verified":False,
      "teacher_rule_verified_count":0,
      "mt5_entries_authorized":0,
      "rules_requiring_audio_review":["STOPPUNCH_SAME_COLOUR","STOPPUNCH_DOJI_AHEAD","STOPPUNCH_DOJI_TIED","STOPPUNCH_OPPOSITE_CONFIRMATION"],
      "windows":checks,"context_links":context_links,
      "note":"ASR recovery improves source coverage only. The 24/24 count is NOT speaker or teacher-rule verification, and the two DOJI hypotheses share the same source interval."
    }


def write_reports(restored_path: Path, remap_path: Path, audio_dir: Path, output_dir: Path) -> dict:
    restored = json.loads(restored_path.read_text(encoding="utf-8"))
    remap = json.loads(remap_path.read_text(encoding="utf-8"))
    report = inspect(restored,remap,audio_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    # Private: direct original-ASR excerpts, no teacher semantic certification.
    private={**report,"raw_machine_asr_review_windows":[{
       "source_window_id":w["source_window_id"],
       "source_audio_excerpt_file":w["audio_excerpt_file"],
       "source_audio_excerpt_sha256":w["audio_excerpt_sha256"],
       "raw_timed_asr":w["recovered_machine_asr_segments"],
     } for w in restored["private_review_windows"]]}
    (output_dir/"ARTIN_SIX_RECOVERED_SOURCE_REVIEW_PRIVATE.json").write_text(
        json.dumps(private,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (output_dir/"ARTIN_SIX_RECOVERED_SOURCE_REVIEW_PUBLIC.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--recovered",type=Path,required=True)
    p.add_argument("--legacy-map",type=Path,required=True)
    p.add_argument("--audio-dir",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=write_reports(a.recovered,a.legacy_map,a.audio_dir,a.out)
    print(json.dumps({"recovered":r["newly_recovered_citations"],"machine_asr_now_present":r["machine_speech_citations_now_present"],"verified_teacher_rules":r["teacher_rule_verified_count"],"trade_authorized":r["mt5_entries_authorized"]}))