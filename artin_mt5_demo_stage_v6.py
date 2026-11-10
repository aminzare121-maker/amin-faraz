#!/usr/bin/env python3
"""Stage verified V3 compile-output files for manual attachment in MT5 DEMO.

This is OFFLINE, FILE-ONLY preparation. It NEVER attaches an Expert Advisor,
opens MetaTrader, authenticates a broker, authorizes orders, or sends trades.
The original V2--V5 programs and source hashes are not modified.

Synthetic tests only check the staging contract, NOT a genuine MetaEditor run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from artin_compile_receipt_verifier import SOURCE_NAME, LOG_NAME, EX5_NAME, SOURCE_SHA, check_receipt

SUBFOLDER = "ArtinV13_ReadOnly"
COMPILE_RELATIVE = Path("ArtinV13") / "compile-check-v3"
RECEIPT_NAME = "artin_v13_metaeditor_compile_receipt.json"
MAX_EX5_BYTES = 50 * 1024 * 1024


class StageBlocked(ValueError):
    """Fail closed; no MT5 trading, no fallback to another terminal."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bounded(path: Path, limit: int, description: str) -> bytes:
    if not path.is_file():
        raise StageBlocked(f"MISSING_{description}")
    if path.stat().st_size > limit:
        raise StageBlocked(f"OVERSIZED_{description}")
    data = path.read_bytes()
    if len(data) > limit:
        raise StageBlocked(f"OVERSIZED_{description}")
    return data


def _compile_evidence(bundle: Path, compile_root: Path) -> tuple[bytes, dict]:
    source = _read_bounded(bundle / SOURCE_NAME, 200_000, "ORIGINAL_V2_SOURCE")
    if _sha(source) != SOURCE_SHA:
        raise StageBlocked("V2_ORIGINAL_SOURCE_HASH_MISMATCH")
    receipt_raw = _read_bounded(compile_root / RECEIPT_NAME, 100_000, "COMPILE_RECEIPT")
    try:
        receipt = json.loads(receipt_raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise StageBlocked("INVALID_COMPILE_RECEIPT") from exc
    log = _read_bounded(compile_root / LOG_NAME, 5_000_000, "METAEDITOR_LOG")
    ex5 = _read_bounded(compile_root / EX5_NAME, MAX_EX5_BYTES, "COMPILED_EX5")
    check = check_receipt(receipt, source, log, ex5)
    if not check["passed"]:
        raise StageBlocked("COMPILE_RECEIPT_NOT_VERIFIED:" + ",".join(check["reasons"]))
    # A successful receipt does not prove the named MetaEditor actually ran;
    # additionally reject nonzero/invalid exit statuses rather than guessing.
    if type(receipt.get("compiler_exit_code")) is not int or receipt["compiler_exit_code"] != 0:
        raise StageBlocked("COMPILER_EXIT_CODE_NOT_ZERO")
    return ex5, {"source_sha256": _sha(source), "log_sha256": _sha(log), "ex5_sha256": _sha(ex5)}


def terminal_roots(appdata: Path) -> list[Path]:
    """Only discover existing MT5 data directories, not install directories."""
    root = Path(appdata) / "MetaQuotes" / "Terminal"
    if not root.is_dir():
        return []
    found = []
    for folder in root.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            continue
        if (folder / "MQL5" / "Experts").is_dir():
            found.append(folder)
    return sorted(found, key=lambda p: p.name.lower())


def select_terminal(appdata: Path, explicit: Path | None = None) -> Path:
    if explicit is not None:
        folder = Path(explicit)
        if not (folder / "MQL5" / "Experts").is_dir():
            raise StageBlocked("EXPLICIT_TERMINAL_DATA_MISSING_MQL5_EXPERTS")
    else:
        candidates = terminal_roots(appdata)
        if len(candidates) == 0:
            raise StageBlocked("NO_MT5_TERMINAL_DATA_FOUND")
        if len(candidates) != 1:
            raise StageBlocked("MULTIPLE_MT5_TERMINALS_REQUIRE_EXPLICIT_TERMINAL_DATA")
        folder = candidates[0]
    if folder.is_symlink() or (folder / "MQL5").is_symlink() or (folder / "MQL5" / "Experts").is_symlink():
        raise StageBlocked("SYMLINK_TERMINAL_DATA_NOT_ALLOWED")
    return folder


def stage_compiled_collector(bundle: Path, compile_root: Path, appdata: Path, *,
                             terminal_data: Path | None = None, report_path: Path | None = None) -> dict:
    """Non-destructive stage of EX5 only. Terminal, chart, login are untouched."""
    ex5, hashes = _compile_evidence(Path(bundle), Path(compile_root))
    folder = select_terminal(Path(appdata), terminal_data)
    experts = folder / "MQL5" / "Experts"
    target_dir = experts / SUBFOLDER
    if target_dir.is_symlink():
        raise StageBlocked("SYMLINK_STAGE_FOLDER_NOT_ALLOWED")
    target_dir.mkdir(exist_ok=True)
    if target_dir.resolve().parent != experts.resolve():
        raise StageBlocked("STAGE_FOLDER_ESCAPES_EXPERTS")
    target = target_dir / EX5_NAME
    if target.is_symlink():
        raise StageBlocked("SYMLINK_COMPILED_EX5_NOT_ALLOWED")
    if target.exists():
        if not target.is_file() or _sha(_read_bounded(target, MAX_EX5_BYTES, "STAGED_EX5")) != hashes["ex5_sha256"]:
            raise StageBlocked("DIFFERENT_STAGED_EX5_REFUSE_OVERWRITE")
        installed = "ALREADY_PRESENT_SAME_HASH"
    else:
        # 'xb' is exclusive creation on Windows and Linux: a different EX5
        # cannot be silently overwritten, even when another process races.
        try:
            with target.open("xb") as f:
                f.write(ex5)
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError as exc:
            raise StageBlocked("STAGED_EX5_CREATED_CONCURRENTLY_RECHECK_MANUALLY") from exc
        if _sha(target.read_bytes()) != hashes["ex5_sha256"]:
            raise StageBlocked("STAGED_EX5_READBACK_HASH_MISMATCH")
        installed = "NEW_EX5_STAGED_NOT_ATTACHED"
    result = {
        "schema": "artin_v13_mt5_local_ex5_stage_receipt_v6",
        "status": installed,
        "source_sha256": hashes["source_sha256"],
        "compile_log_sha256": hashes["log_sha256"],
        "staged_ex5_sha256": hashes["ex5_sha256"],
        "terminal_data_path_sha256": _sha(os.path.normcase(str(folder.resolve())).encode("utf-8")),
        "mt5_chart_attached": False,
        "mt5_demo_account_confirmed": False,
        "broker_connection_verified": False,
        "live_m15_csv_verified": False,
        "teacher_semantics_certified": False,
        "orders_sent": 0,
        "next_step": "In this MT5 terminal, open XAUUSD M15 on DEMO and manually attach ArtinV13_ReadOnly collector",
        "important": "Receipt validates local files only; a fabricated zero-error log/EX5 cannot prove MetaEditor execution",
    }
    if report_path is not None:
        p = Path(report_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Receipt is diagnostic only; never include account login/server/paths.
        with p.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage Artin V13 V2 DEMO-only collector EX5 for MANUAL MT5 attachment")
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--compile-root", type=Path)
    parser.add_argument("--appdata", type=Path)
    parser.add_argument("--localappdata", type=Path)
    parser.add_argument("--terminal-data", type=Path, help="Select exact MT5 data folder when several terminals exist")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        appdata = args.appdata or (Path(os.environ["APPDATA"]) if os.getenv("APPDATA") else None)
        localappdata = args.localappdata or (Path(os.environ["LOCALAPPDATA"]) if os.getenv("LOCALAPPDATA") else None)
        if appdata is None or localappdata is None:
            raise StageBlocked("WINDOWS_APPDATA_ENV_MISSING")
        compile_root = args.compile_root or localappdata / COMPILE_RELATIVE
        report = args.report or (localappdata / "ArtinV13" / "stage-v6" /
                                 f"stage_{time.time_ns()}_{os.getpid()}.json")
        result = stage_compiled_collector(args.bundle, compile_root, appdata,
                terminal_data=args.terminal_data, report_path=report)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("LOCAL_STAGE_REPORT: " + str(report))
        return 0
    except (StageBlocked, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED_NO_TRADES", "reason": str(exc), "orders_sent": 0}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())