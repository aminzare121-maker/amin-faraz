"""Offline classroom ASR coverage and question/correction review queue for Artin.

No network, broker, media upload, or automatic trading permission. In particular:
- A text question does not identify its speaker.
- The segment following a question is NOT automatically the teacher's answer.
- A guessed correction does not supersede an approved teaching rule.
- Matching SHA-256 proves the ASR file matches the *registered ASR file*, not
  that its transcription is accurate or that the video was watched.
All emitted dialogue is a PRIVATE LOCAL REVIEW QUEUE, not a trading rule.
"""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

QUESTION_WORDS = re.compile(
    r"(چرا|چطور|چگونه|کجا|کی|آیا|میشه|می‌شه|می شه|یعنی چی|چه موقع|کدوم|کدام|مگه|can you|why|how)",
    re.IGNORECASE,
)
CORRECTION_WORDS = re.compile(
    r"(نه[،, ]|اشتباه|تصحیح|درستش|اصلاح|منظورم|نه این|یعنی باید|actually|instead|correction)",
    re.IGNORECASE,
)
SPEECH_FILE = re.compile(r"^speech-(\d{6})\.json$", re.IGNORECASE)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _load_asr(data):
    doc = json.loads(data.decode("utf-8-sig"))
    if isinstance(doc, list):
        entries = doc
    elif isinstance(doc, dict) and isinstance(doc.get("segments"), list):
        entries = doc["segments"]
    else:
        raise ValueError("ASR JSON must be a segment list or an object with segments list")
    out = []
    for n, seg in enumerate(entries):
        if not isinstance(seg, dict):
            raise ValueError("ASR segment must be an object")
        txt, start, end = seg.get("text"), seg.get("start"), seg.get("end")
        if type(txt) is not str or not txt.strip():
            raise ValueError("ASR segment requires text")
        if type(start) not in (int, float) or type(end) not in (int, float):
            raise ValueError("ASR timestamps are required")
        if not (0 <= start < end) or end > 1e7:
            raise ValueError("Invalid ASR time interval")
        out.append((n, float(start), float(end), txt.strip()))
    return out


def _speech_pool(root):
    """Indexed only by exact basename; content hash selects the correct session."""
    root = Path(root)
    if not root.is_dir():
        raise ValueError("ASR directory missing")
    pool = defaultdict(list)
    for path in root.rglob("speech-*.json"):
        if path.is_file() and SPEECH_FILE.fullmatch(path.name):
            pool[path.name].append(path)
    return pool


def inspect_course(asr_root, source_inventory, timebase="relative", allow_partial=True):
    """Return a strictly evidence-labelled local report; never infer speaker roles."""
    if timebase not in ("relative", "absolute"):
        raise ValueError("Choose explicit relative or absolute segment timebase")
    if not isinstance(source_inventory, dict) or not isinstance(source_inventory.get("sessions"), list):
        raise ValueError("Invalid session inventory")
    pool = _speech_pool(asr_root)
    expected_files, loaded_files, failures = 0, 0, []
    by_session, questions = [], []
    hash_cache = {}
    for session in source_inventory["sessions"]:
        sid = session["session"]
        utterances = []
        registered = session.get("transcript_files", [])
        expected_files += len(registered)
        for f in registered:
            filename, expected = f["file"], f["sha256"]
            if not SPEECH_FILE.fullmatch(filename) or not re.fullmatch("[0-9a-f]{64}", expected):
                raise ValueError("Malformed source inventory entry")
            matches = []
            for path in pool.get(filename, []):
                if path not in hash_cache:
                    hash_cache[path] = _sha256(path.read_bytes())
                if hash_cache[path] == expected:
                    matches.append(path)
            if len(matches) != 1:
                failures.append(dict(session=sid, file=filename,
                                     reason=("NOT_FOUND_OR_HASH_MISMATCH" if not matches else "AMBIGUOUS_DUPLICATE_MATCH")))
                continue
            path = matches[0]
            data = path.read_bytes()
            try:
                segments = _load_asr(data)
            except (ValueError, UnicodeDecodeError, KeyError, TypeError) as exc:
                failures.append(dict(session=sid, file=filename,
                                     reason="ASR_PARSE_ERROR:" + type(exc).__name__))
                continue
            if f.get("segment_count") != len(segments):
                failures.append(dict(session=sid, file=filename, reason="SEGMENT_COUNT_MISMATCH"))
                continue
            offset = int(SPEECH_FILE.fullmatch(filename).group(1))
            if any((e > 610 if timebase == "relative" else
                    (s < offset - 2 or e > offset + 610))
                   for _, s, e, _ in segments):
                failures.append(dict(session=sid, file=filename, reason="TIMEBASE_UNCERTAIN"))
                continue
            for n, start, end, text in segments:
                start_abs = round(start + (offset if timebase == "relative" else 0), 3)
                end_abs = round(end + (offset if timebase == "relative" else 0), 3)
                uid = _sha256((expected + ":" + str(n) + ":" + text).encode("utf8"))[:24]
                utterances.append(dict(
                    utterance_id=uid, session=sid, start_seconds=start_abs,
                    end_seconds=end_abs, source_asr_sha256=expected,
                    source_file=filename, text=text,
                    speaker="UNKNOWN", speaker_verified=False,
                    asr_not_audio_verified=True,
                ))
            loaded_files += 1
        utterances.sort(key=lambda u:(u["start_seconds"], u["end_seconds"],u["utterance_id"]))
        for i, utt in enumerate(utterances):
            tags = []
            if "؟" in utt["text"] or "?" in utt["text"] or QUESTION_WORDS.search(utt["text"]):
                tags.append("QUESTION_LANGUAGE_CANDIDATE")
            if CORRECTION_WORDS.search(utt["text"]):
                tags.append("POSSIBLE_CORRECTION_LANGUAGE")
            if tags:
                questions.append(dict(
                    session=sid, utterance_id=utt["utterance_id"],
                    start_seconds=utt["start_seconds"], end_seconds=utt["end_seconds"],
                    text=utt["text"], machine_tags=tags,
                    context_before=[x["utterance_id"] for x in utterances[max(0, i-2):i]],
                    context_after=[x["utterance_id"] for x in utterances[i+1:i+4]],
                    speaker="UNKNOWN", teacher_answer_turn_id=None,
                    visual_frame_ref=None, latest_rule_id=None,
                    review_state="NEEDS_DIRECT_AUDIO_VISUAL_AND_SPEAKER_REVIEW",
                ))
        by_session.append(dict(
            session=sid, registered_asr_files=len(registered),
            verified_asr_files=sum(1 for f in registered if
                not any(x["session"]==sid and x["file"]==f["file"] for x in failures)),
            verified_asr_utterances=len(utterances),
            potential_question_or_correction_segments=sum(1 for q in questions if q["session"]==sid),
            inventory_audio_available=session.get("audio_available",False),
            inventory_video_available=session.get("video_available",False),
            original_media_reviewed_by_this_tool=False,
            dialogue_speakers_confirmed=0,
            trading_rules_approved=0,
        ))
    report=dict(
        mode="LOCAL_ASR_INDEX_NOT_VERIFIED_CLASSROOM_TEACHING",
        registered_sessions=len(by_session), expected_asr_files=expected_files,
        hash_verified_asr_files=loaded_files, failures=failures,
        registered_asr_files_missing_or_invalid=expected_files-loaded_files,
        candidate_qa_or_correction_segments=len(questions),
        sessions=by_session,
        all_original_audio_video_watched=False,
        teacher_speaker_diarized=False, teacher_rules_verified=0,
        can_change_trading_engine=False,
    )
    if not allow_partial and (failures or expected_files != loaded_files or
                              any(x["registered_asr_files"]==0 for x in by_session)):
        raise ValueError("Incomplete course input: see partial audit; not suitable as complete evidence")
    return report, questions


def _write_local_json(path, data):
    path = Path(path)
    if path.parent == Path() or not path.parent.is_dir():
        raise ValueError("Existing output directory required")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asr-root",type=Path,required=True)
    p.add_argument("--inventory",type=Path,default=Path(__file__).resolve().parent/"docs"/"SOURCE_COVERAGE.json")
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--private-review-queue",type=Path,required=True)
    p.add_argument("--timebase",choices=("relative","absolute"),required=True)
    p.add_argument("--require-all-registered-asr",action="store_true")
    a=p.parse_args()
    inventory=json.loads(a.inventory.read_text(encoding="utf-8-sig"))
    report,queue=inspect_course(a.asr_root,inventory,timebase=a.timebase)
    if a.report.resolve()==a.private_review_queue.resolve():
        p.error("Private queue and summary report must have different paths")
    if a.require_all_registered_asr and (
        report["registered_asr_files_missing_or_invalid"]>0 or
        any(s["registered_asr_files"]==0 for s in report["sessions"])):
        p.error("Full-course ASR not available; partial report not accepted")
    _write_local_json(a.report,report)
    _write_local_json(a.private_review_queue,dict(
        kind="PRIVATE_REVIEW_QUEUE_DO_NOT_PUBLISH",
        candidate_utterances=queue,
        speaker_role_inferred=False,
        teacher_answers_confirmed=0,
        trading_rules_generated=0,
    ))
    print(json.dumps({
        "registered_sessions":report["registered_sessions"],
        "hash_verified_asr_files":report["hash_verified_asr_files"],
        "expected_asr_files":report["expected_asr_files"],
        "question_or_correction_candidates":len(queue),
        "teacher_rules_verified":0,
    },ensure_ascii=False))


if __name__=="__main__":
    main()
