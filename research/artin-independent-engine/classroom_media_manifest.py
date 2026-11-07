"""Local-only media inventory for Artin classroom evidence.

This verifies FILE existence, SHA256, size, and cautious session hints. It does
NOT watch or transcribe a video, diarize student/teacher voices, confirm any
lesson rule, or grant permission for paper/live trading. Do not commit private
media or the resulting absolute filenames to GitHub.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

VIDEO={".mp4",".mkv",".mov",".avi",".webm"}
AUDIO={".wav",".mp3",".m4a",".flac",".ogg",".aac"}
PERSIAN_DIGITS=str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")
SESSION_HINT=re.compile(
    r"(?:^|[^a-z0-9])(?:session|lesson|class|جلسه|کلاس)[ _\-.]*(0?[1-9]|1\d|2[0-6])(?=$|[^0-9])",
    re.IGNORECASE,
)


def session_candidates(path,root):
    """Extract only explicit lesson/session markers from path components."""
    rel=path.relative_to(root)
    numbers=set()
    for part in rel.parts:
        s=part.translate(PERSIAN_DIGITS)
        numbers.update(int(m.group(1)) for m in SESSION_HINT.finditer(s))
    return sorted(numbers)


def digest(path):
    hasher=hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda:fh.read(1024*1024),b""):
            hasher.update(block)
    return hasher.hexdigest()


def inventory(root,declared_sessions=26):
    root=Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Original media folder not available")
    if type(declared_sessions) is not int or declared_sessions<1 or declared_sessions>999:
        raise ValueError("Invalid session count")
    records=[]
    ignored_symlinks=0
    # Path.rglob does not open media: report is local metadata only.
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.is_symlink():
            ignored_symlinks+=1
            continue
        ext=path.suffix.lower()
        if ext not in VIDEO|AUDIO:
            continue
        size=path.stat().st_size
        candidates=session_candidates(path,root)
        in_range= [x for x in candidates if 1<=x<=declared_sessions]
        records.append(dict(
            private_relative_path=str(path.relative_to(root)),
            kind="VIDEO" if ext in VIDEO else "AUDIO",
            bytes=size, sha256=digest(path),
            session_candidates=in_range,
            matching_rule="EXPLICIT_SESSION_MARKER_ONLY",
            identity_verified_from_content=False,
            speaker_identified=False,
            teacher_content_reviewed=False,
            available_for_trading_rules=False,
        ))
    records.sort(key=lambda r:r["private_relative_path"])
    by_session=[]
    for s in range(1,declared_sessions+1):
        assigned=[r for r in records if r["session_candidates"]==[s]]
        by_session.append(dict(
            session=s,unambiguous_media_files=len(assigned),
            video_candidates=sum(r["kind"]=="VIDEO" for r in assigned),
            audio_candidates=sum(r["kind"]=="AUDIO" for r in assigned),
            full_lesson_verified=False,
            teacher_question_answer_verified=False,
        ))
    return dict(
        mode="PRIVATE_MEDIA_FILES_HASHED_NOT_WATCHED",
        declared_sessions=declared_sessions,
        media_files_hashed=len(records),
        media_kind_counts=dict(Counter(r["kind"] for r in records)),
        ambiguous_or_unassigned_files=sum(len(r["session_candidates"])!=1 for r in records),
        ignored_symlinks=ignored_symlinks,
        sessions_without_unambiguous_media=[r["session"] for r in by_session
                                            if r["unambiguous_media_files"]==0],
        sessions=by_session, media=records,
        original_audio_video_reviewed=False,
        video_speaker_diarization_complete=False,
        approved_teacher_rules=0, broker_connected=False, orders_sent=0,
    )


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--media-root",type=Path,required=True)
    p.add_argument("--private-out",type=Path,required=True)
    p.add_argument("--sessions",type=int,default=26)
    a=p.parse_args()
    result=inventory(a.media_root,a.sessions)
    out=a.private_out.resolve()
    if out.is_relative_to(a.media_root.resolve()):
        p.error("Output file must be outside original media folder")
    if not out.parent.is_dir():
        p.error("Output directory must exist")
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print(json.dumps({k:result[k] for k in (
        "declared_sessions","media_files_hashed",
        "ambiguous_or_unassigned_files","sessions_without_unambiguous_media",
        "approved_teacher_rules","orders_sent"
    )},ensure_ascii=False))


if __name__=="__main__":
    main()
