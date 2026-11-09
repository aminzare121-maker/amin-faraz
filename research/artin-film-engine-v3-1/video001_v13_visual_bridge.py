"""V13 accelerated visual source bridge. New evidence only; never rewrites V12/raw media.

The pilot creates the original 1-Hz chat-change index plus the scheduled
board/scene crops, retaining each source SHA. This stage does NOT do OCR,
transcription, teacher understanding, or rule confirmation.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil

from PIL import Image, ImageEnhance, ImageFilter

from artin_chat_temporal_v8 import FRAME_SIZE
from artin_film_pipeline import file_sha256
from artin_visual_timeline_v6 import frame_times, validate_visual_index
from video001_v13_one_pass_visual import run as one_pass_run


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def scan_chat_and_board_once(video, output, source_sha256, duration_seconds):
    """Run real video once; losslessly reconstruct the prior INDEX contract."""
    root = Path(output)
    result = one_pass_run(video, root, source_sha256,
                          duration=duration_seconds, board_sample_s=30)
    raw = _read(root / "original_chat_change_timestamps_review_only.json")
    if not isinstance(raw, list) or len(raw) != result["chat_frames_one_second"]:
        raise ValueError("V13_CHAT_INDEX_MISSING_OR_SHORT")
    items = []
    last_selected = -30
    for i, entry in enumerate(raw):
        if entry.get("second") != i:
            raise ValueError("V13_CHAT_FRAME_ORDER_CHANGED")
        if i > float(duration_seconds) + .5:
            raise ValueError("V13_CHAT_TIME_OUT_OF_SOURCE")
        val = entry.get("change_score")
        if type(val) not in (int, float) or not math.isfinite(val) or val < 0:
            raise ValueError("V13_INVALID_CHAT_CHANGE_SCORE")
        is_changed = val >= .02
        periodic = i - last_selected >= 30
        selected = i == 0 or is_changed or periodic
        if entry.get("source_frame_selected") is not selected:
            raise ValueError("V13_CHAT_SELECTION_DRIFT")
        if selected:
            last_selected = i
        items.append({
            "source_time_seconds": float(i), "global_part":i//300+1,
            "frame_ordinal":i, "change_score":round(float(val), 6),
            "priority_capture": selected,
            "reason": "FIRST" if i==0 else "CHAT_CHANGED" if is_changed else
                      "PERIODIC_ANCHOR" if periodic else "NOT_SELECTED",
            "chat_text_verified":False, "question_verified":False,
        })
    timeline = {
        "schema":"artin_source_chat_temporal_index_v8",
        "source_video_sha256":source_sha256,
        "video_duration_seconds":duration_seconds,
        "sample_interval_seconds":1,
        "chat_region":"[0.71,0.11,0.90,0.95] normalized source video",
        "sampled_source_frames":len(items),
        "selected_frames_for_high_resolution_recheck":sum(
            row["priority_capture"] for row in items),
        "changed_chat_frames":sum(row["reason"]=="CHAT_CHANGED" for row in items),
        "first_frame_seconds":items[0]["source_time_seconds"],
        "last_frame_seconds":items[-1]["source_time_seconds"],
        "ground_truth_all_chat_messages_found":False,
        "printed_persian_chat_recognized":False,
        "teacher_answers_verified":0, "rules_executable":0,
        "rows":items,
    }
    if timeline["selected_frames_for_high_resolution_recheck"] != result["change_selected_chat_frames"]:
        raise ValueError("V13_SELECTED_FRAME_COUNT_MISMATCH")
    return timeline, result


def create_compatible_board_index(visual_root, out, manifest, scan,
                                  *, board_bounds=(0,.14,.71,.91),
                                  chat_bounds=(.71,.11,.90,.95), upscale=2):
    """Produce NEW, individually SHA-verified board/scene images using one-pass frames.

    The original source images previously extracted by V12 are not touched.
    Sample timestamps and original V6 board schema are checked before return.
    """
    visual_root=Path(visual_root).resolve()
    out=Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("V13_WILL_NOT_REWRITE_EXISTING_BOARD_EVIDENCE")
    expected=frame_times(manifest["parts"], 30)
    rows=[]
    images=sorted((visual_root/"board_uninterpreted").glob("board_frame_*.jpg"))
    nominal=scan.get("board_timestamps_nominal_seconds", [])
    if (len(images)!=len(expected) or len(nominal)!=len(expected)
            or scan.get("highres_board_frames")!=len(expected)):
        raise ValueError("V13_BOARD_COUNT_DIFFERS_FROM_ORIGINAL_SAMPLING")
    for plan, t in zip(expected, nominal):
        if abs(float(plan["time_seconds"])-float(t))>.01:
            raise ValueError("V13_BOARD_TIMESTAMP_DIFFERS_FROM_ORIGINAL_GRID")
    out.mkdir(parents=True,exist_ok=True)
    for plan, source in zip(expected, images):
        stem=plan["frame_id"]
        original=out/"frames"/(stem+"_original.jpg")
        board=out/"board"/(stem+"_board.png")
        chat=out/"chat"/(stem+"_chat.png")
        for path in (original, board, chat):
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                raise FileExistsError("V13_SOURCE_FRAME_WOULD_BE_OVERWRITTEN")
        if file_sha256(source)!=scan["board_frames_sha256"][len(rows)]:
            raise ValueError("V13_BOARD_SOURCE_HASH_MISMATCH")
        shutil.copy2(source,original)
        if file_sha256(original)!=file_sha256(source):
            raise ValueError("V13_BOARD_COPY_HASH_MISMATCH")
        with Image.open(original) as im:
            frame=im.convert("RGB")
            w,h=frame.size
            if w<320 or h<200:
                raise ValueError("V13_BOARD_FRAME_TOO_SMALL")
            def crop(bounds):
                l,t,r,b=bounds
                return frame.crop((int(l*w),int(t*h),int(r*w),int(b*h)))
            bd=crop(board_bounds)
            ch=crop(chat_bounds)
            if upscale>1:
                ch=ch.resize((ch.width*upscale,ch.height*upscale),
                             Image.Resampling.LANCZOS)
                ch=ImageEnhance.Contrast(ch).enhance(1.35)
                ch=ch.filter(ImageFilter.UnsharpMask(
                    radius=1.2,percent=125,threshold=2))
            bd.save(board,format="PNG",optimize=True)
            ch.save(chat,format="PNG",optimize=True)
        rows.append({**plan,
            "video_frame":{"path":original.relative_to(out).as_posix(),
                           "sha256":file_sha256(original),
                           "original_width":w,"original_height":h},
            "board":{"path":board.relative_to(out).as_posix(),
                     "sha256":file_sha256(board)},
            "chat":{"path":chat.relative_to(out).as_posix(),
                    "sha256":file_sha256(chat)},
            "typed_student_question_verified":False,
            "speaker_role_verified":False,
            "chart_meaning_verified":False,
            "any_rule_executable":False,
        })
    index={
        "schema":"artin_classroom_visual_v6",
        "source_video_sha256":manifest["video_sha256"],
        "source_duration_seconds":manifest["duration_seconds"],
        "sample_seconds":30,
        "frame_count":len(rows),
        "regions":{"board":list(board_bounds),"typed_chat":list(chat_bounds)},
        "rows":rows, "capture_notice":"SAMPLED_FRAMES_NOT_ALL_CHAT_MESSAGES",
        "vision_model_ran":False,"ocr_model_ran":False,
        "speaker_identity_verified":False,"teacher_rules_verified":0,
        "v13_new_extraction_from_immutable_source":True,
        "v12_original_archived_frames_replaced":False,
    }
    validate_visual_index(out,manifest,index,verify_files=True)
    (out/"visual_timeline_v6.json").write_text(
        json.dumps(index,ensure_ascii=False,indent=2),encoding="utf8")
    return index
