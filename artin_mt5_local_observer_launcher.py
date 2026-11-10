#!/usr/bin/env python3
"""Read-only local launcher from MT5 FILE_COMMON CSV into the existing V5 outbox.

This does not install/compile/attach an MQL5 Expert Advisor or make a broker
connection. Presence of a CSV named "demo" is not account authentication.
The MQL5 recovery V2 collector must already be running on the owner's DEMO chart.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from artin_mt5_durable_outbox_v5 import ObserverBlocked, run as v5_run

FILENAME = re.compile(r"artin_v13_demo_[A-Za-z0-9._-]+_[0-9]+_XAUUSD[A-Za-z0-9._-]*_M15_recovery_v2\.csv\Z")

class LaunchBlocked(ValueError):
    pass


def common_files_root(appdata: str | None = None) -> Path:
    """MQL5 FILE_COMMON is the per-user common MetaTrader Terminal Files dir."""
    base = appdata if appdata is not None else os.getenv("APPDATA")
    if not base:
        raise LaunchBlocked("APPDATA_NOT_AVAILABLE: specify --csv explicitly")
    return Path(base) / "MetaQuotes" / "Terminal" / "Common" / "Files"


def select_source(explicit_csv: Path | None = None, *, common_dir: Path | None = None) -> Path:
    if explicit_csv is not None:
        source = Path(explicit_csv)
        if not FILENAME.fullmatch(source.name):
            raise LaunchBlocked("NOT_AN_ARTIN_V2_RECOVERY_CSV_FILENAME")
        if not source.is_file():
            raise LaunchBlocked("EXPLICIT_CSV_NOT_FOUND")
        return source.resolve()
    root = Path(common_dir) if common_dir is not None else common_files_root()
    if not root.is_dir():
        raise LaunchBlocked("MT5_COMMON_FILES_NOT_FOUND: run the DEMO V2 collector first or pass --csv")
    matches = sorted(p.resolve() for p in root.iterdir() if p.is_file() and FILENAME.fullmatch(p.name))
    if not matches:
        raise LaunchBlocked("NO_ARTIN_V2_DEMO_CSV_FOUND: collector not detected")
    if len(matches) != 1:
        raise LaunchBlocked("MULTIPLE_ARTIN_V2_DEMO_CSV_FILES: pass --csv for the chosen account")
    return matches[0]


def user_output_root(localappdata: str | None = None) -> Path:
    base = localappdata if localappdata is not None else os.getenv("LOCALAPPDATA")
    if not base:
        raise LaunchBlocked("LOCALAPPDATA_NOT_AVAILABLE: specify --output-root")
    return Path(base) / "ArtinV13" / "read-only-live"


def state_paths(source: Path, output_root: Path) -> tuple[Path, Path, str]:
    source = Path(source).resolve()
    fingerprint = hashlib.sha256(os.path.normcase(str(source)).encode("utf-8")).hexdigest()[:20]
    base = Path(output_root).resolve() / ("source_" + fingerprint)
    if source == base / "progress.json" or base in source.parents:
        raise LaunchBlocked("OUTPUT_FOLDER_CONTAINS_SOURCE_CSV")
    return base / "progress.json", base / "evidence", fingerprint


def verify_quiet_snapshot(source: Path, settle_seconds: float) -> None:
    try:
        a = source.stat()
        if not source.is_file() or a.st_size == 0:
            raise LaunchBlocked("SOURCE_CSV_EMPTY_OR_NOT_REGULAR")
        if settle_seconds:
            time.sleep(settle_seconds)
        b = source.stat()
    except OSError as exc:
        raise LaunchBlocked("SOURCE_CSV_UNAVAILABLE") from exc
    if (a.st_size, a.st_mtime_ns, a.st_ino) != (b.st_size, b.st_mtime_ns, b.st_ino):
        raise LaunchBlocked("SOURCE_CSV_STILL_BEING_WRITTEN")


def poll_once(source: Path, output_root: Path, *, settle_seconds: float = 0.25) -> dict:
    verify_quiet_snapshot(source, settle_seconds)
    state, outbox, fingerprint = state_paths(source, output_root)
    result = v5_run(source, state, outbox)
    if result.get("orders_sent") != 0 or result.get("teacher_semantics_certified") is not False:
        raise LaunchBlocked("IMPOSSIBLE_TRADING_OR_TEACHER_CLAIM")
    return {"source_id": fingerprint,
            "mode": "LOCAL_MT5_FILE_COMMON_CSV_READ_ONLY_UNAUTHENTICATED",
            "mt5_compiled_or_live_demo_attested": False,
            **result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Artin V13 V2 collector CSV -> V5 durable observer (NO TRADES)")
    parser.add_argument("--csv", type=Path, help="Exact Artin V2 collector CSV; otherwise auto-discover unique MT5 FILE_COMMON file")
    parser.add_argument("--output-root", type=Path, help="Persistent separate state/outbox base; default LOCALAPPDATA\\ArtinV13\\read-only-live")
    parser.add_argument("--watch", action="store_true", help="Continue polling for new closed M15 bars until stopped")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--settle-seconds", type=float, default=0.25)
    parser.add_argument("--max-polls", type=int, default=0, help="Testing: stop after N watches; 0=unlimited")
    a = parser.parse_args(argv)
    if not 0 <= a.settle_seconds <= 10 or not 0.1 <= a.poll_seconds <= 3600 or a.max_polls < 0:
        parser.error("invalid settle/poll/max-polls parameter")
    try:
        source = select_source(a.csv)
        output_root = a.output_root if a.output_root is not None else user_output_root()
        done = 0
        while True:
            try:
                result = poll_once(source, output_root, settle_seconds=a.settle_seconds)
            except (LaunchBlocked, ObserverBlocked) as exc:
                # A collector write can temporarily expose an incomplete CSV row.
                # Retry only this known incomplete-write condition. Corrupt history,
                # invalid prices, duplicate rows and all other faults remain fatal.
                transient = str(exc) in ("SOURCE_CSV_STILL_BEING_WRITTEN", "SOURCE_HAS_UNCOMMITTED_PARTIAL_ROW")
                if not transient or not a.watch:
                    raise
                done += 1
                if done >= 6:
                    raise LaunchBlocked("SOURCE_REPEATEDLY_UNSTABLE_STOPPED") from exc
                time.sleep(a.poll_seconds)
                continue
            done = 0
            if not a.watch or result.get("new_closed_bars", 0) or result.get("recovered_uncommitted_receipts", 0):
                print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
            if not a.watch:
                return 0
            if a.max_polls:
                a.max_polls -= 1
                if a.max_polls == 0:
                    return 0
            time.sleep(a.poll_seconds)
    except KeyboardInterrupt:
        print("STOPPED_BY_OPERATOR_NO_TRADES", file=sys.stderr)
        return 0
    except (LaunchBlocked, ObserverBlocked, OSError, ValueError) as exc:
        print(json.dumps({"status":"BLOCKED_NO_TRADES", "reason":str(exc), "orders_sent":0}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())