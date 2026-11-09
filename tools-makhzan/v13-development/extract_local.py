"""Run a registered V13 film in a new private directory on one prepared host.

Usage: python extract_local.py ENTRY_JSON NEW_DIRECTORY [--asr 2 --ocr 2]
Requires git, ffmpeg, Persian+English tesseract, faster-whisper and PaddleOCR.
Pinned engines are unpacked from this repository before starting the source clock.
The result is machine-extracted text. No production queue or semantic receipt is written.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
ENGINE = Path("research/artin-film-engine-v3-1")
PREP = "27e184447480925cd814e0b604bf2924b9c460b7"
MODEL = "bfbaa2b1bffc3346253e2605d699a8c9de367193"
VERIFY = "982bc660722c4167fbcea64b223b8698593a4d80"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def engine_at(commit, root):
    git = ["git", "-C", str(REPO)]
    if subprocess.run(git + ["cat-file", "-e", commit], stderr=subprocess.DEVNULL).returncode:
        subprocess.run(git + ["fetch", "--depth=1", "origin", commit], check=True)
    # Materialize trusted pinned Python sources, including their sibling imports.
    dest = root / commit
    dest.mkdir()
    names = subprocess.check_output(git + ["ls-tree", "--name-only", commit + ":" + str(ENGINE)], text=True)
    for name in names.splitlines():
        if name.endswith(".py"):
            (dest / name).write_bytes(subprocess.check_output(git + ["show", f"{commit}:{ENGINE}/{name}"]))
    return dest


def run(script, *args):
    subprocess.run([sys.executable, str(script), *map(str, args)], check=True)


def extract(root, prep_engine, worker, verifier, entry):
    prepared = root / "media/prepared"
    source_summary = prepared / "safe_source_prep_summary.json"
    source = read(source_summary)
    speech = source["source_audio_worker_count"]
    images = source["original_ocr_workers"]
    chat_index = prepared / "full_chat/chat_selected_index.json"
    board = prepared / "board_review"
    board_text = root / "board_text"
    asr = root / "asr"
    ocr = root / "ocr"
    # Resolve the same model from the local cache before attempting a network
    # lookup. Keep the original model name and normal download on a cold host.
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError
    model = "large-v3-turbo"
    try:
        snapshot = Path(snapshot_download("mobiuslabsgmbh/faster-whisper-large-v3-turbo",
                                          local_files_only=True))
        if all((snapshot / f).is_file() for f in ("model.bin", "config.json", "tokenizer.json", "preprocessor_config.json")):
            model = str(snapshot)
    except (FileNotFoundError, LocalEntryNotFoundError):
        pass
    asr.mkdir()
    jobs = []
    with ThreadPoolExecutor(max_workers=speech + images + 1) as pool:
        jobs.append(pool.submit(run, prep_engine / "video001_v13_board_text_worker.py",
                                "--board-root", board, "--out", board_text, "--workers", 2))
        for i in range(speech):
            jobs.append(pool.submit(run, worker / "artin_parallel_asr_worker_v5.py",
                                    "--prepped-root", prepared / f"asr_shards/worker_{i:02d}",
                                    "--out", root / f"speech-{i}", "--index", i, "--partitions", speech,
                                    "--expected-sha256", source["source_video_sha256"], "--model", model))
        for i in range(images):
            shard = prepared / f"ocr_shards/worker_{i:02d}"
            jobs.append(pool.submit(run, worker / "artin_persian_full_chat_ocr_v7.py",
                                    "--visual-root", shard, "--visual-index", shard / "chat_selected_index.json",
                                    "--partition-index", i, "--partition-count", images,
                                    "--out", ocr / f"video001-fast-ocr-{i}"))
        for job in jobs:
            job.result()
    for i in range(speech):
        for path in (root / f"speech-{i}/asr_evidence").iterdir():
            os.link(path, asr / path.name)
    evidence = root / "verified"
    run(verifier / "video001_fast_verify_v1.py", "--asr-root", asr, "--ocr-root", ocr,
        "--source-index", chat_index, "--board-root", board, "--source-summary", source_summary,
        "--out", evidence, "--audio-workers", speech, "--ocr-workers", images)
    for original, result in zip(read(board / "visual_timeline_v6.json")["rows"],
                                read(board_text / "board_ocr_candidates_PRIVATE.json")["results"], strict=True):
        if (original["frame_id"], original["time_seconds"], original["board"]["sha256"]) != (
                result["frame_id"], result["time_original_video_seconds"], result["source_frame_sha256"]):
            raise ValueError("Board OCR provenance mismatch")
    proof = evidence / "private_fast_verify_summary.json"
    export = root / "export"
    run(REPO / ENGINE / "video001_fast_export_v12.py", "--proof-path", proof,
        "--source-path", source_summary, "--asr-path", evidence / "asr_verified/complete_unverified_qa_evidence.json",
        "--ocr-root", ocr, "--chat-index", chat_index, "--board-root", board,
        "--temporal-index", prepared / "original_second_by_second_chat_index.json",
        "--chat-images", prepared / "full_chat", "--out", export, "--audio-workers", speech, "--ocr-workers", images)
    run(REPO / ENGINE / "video001_v13_text_archive_ready.py", "--out", root / "machine-text.zip",
        "--source-summary", source_summary, "--source-proof", proof, "--asr-root", asr, "--ocr-root", ocr,
        "--board-ocr-root", board_text, "--export-root", export, "--magazine-id", entry["magazine_id"],
        "--queue-id", entry["queue_id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entry", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--asr", type=int, choices=range(1, 18), default=1)
    parser.add_argument("--ocr", type=int, choices=range(1, 17), default=1)
    args = parser.parse_args()
    entry = read(args.entry)
    if entry.get("submitted_by_user") is not True or not re.fullmatch(
            r"https://my\.uupload\.ir/p/[A-Za-z0-9_-]+/?", entry["source_page"]):
        raise ValueError("Registered Uupload entry required")
    langs = subprocess.check_output(["tesseract", "--list-langs"], text=True).splitlines()
    if not {"fas", "eng"}.issubset(langs):
        raise RuntimeError("Persian and English Tesseract models required")
    root = args.output.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    engines = [engine_at(commit, root) for commit in (PREP, MODEL, VERIFY)]
    request = root / "request.json"
    request.write_text(json.dumps(dict(schema="video001_fast_source_request_v1", source_page=entry["source_page"],
                                       expected_sha256=entry.get("expected_sha256"), audio_workers=args.asr,
                                       ocr_workers=args.ocr)), encoding="utf-8")
    start = time.monotonic()
    report = {"queue_id": entry["queue_id"], "archive_verified": False, "semantic_review_verified": False}
    try:
        run(Path(__file__).with_name("receive_parallel.py"), engines[0], "--request", request, "--out", root / "media")
        report["receive_and_prepare_seconds"] = time.monotonic() - start
        extract(root, *engines, entry)
        report["archive_verified"] = True
    finally:
        report["elapsed_seconds"] = time.monotonic() - start
        report["machine_text_within_180_seconds"] = report["archive_verified"] and report["elapsed_seconds"] <= 180
        (root / "timing.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
