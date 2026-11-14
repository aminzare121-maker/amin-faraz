#!/usr/bin/env python3
"""Rebuild 23,643 genuine Eplanet M15 OHLCV bars from audited XZ/base64 parts.

Only research: no broker access, login, keys, trading or market orders.
Run in GitHub Actions on a throwaway workspace.
"""
from __future__ import annotations
import base64
import csv
import hashlib
import json
import lzma
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
MANIFEST = DATA / "transfer_manifest.json"
EXPECTED_SHA = "06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604"
EXPECTED_ROWS = 23643
EXPECTED_START = 1762340400
EXPECTED_END = 1793875500

def rebuild():
    meta = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert meta["raw_sha256"] == EXPECTED_SHA
    assert meta["rows"] == EXPECTED_ROWS
    assert meta["compressed_encoding"] == "lzma_xz_then_base64"
    pieces = []
    for item in meta["parts"]:
        name = item["file"]
        if Path(name).name != name:
            raise ValueError("Invalid component filename")
        payload = (DATA / name).read_bytes()
        if len(payload) != item["length"]:
            raise ValueError(f"Part size mismatch: {name}")
        if hashlib.sha256(payload).hexdigest() != item["decoded_text_sha256"]:
            raise ValueError(f"Part SHA mismatch: {name}")
        pieces.append(b"".join(payload.split()))
    decompressed = lzma.decompress(base64.b64decode(b"".join(pieces), validate=True))
    if len(decompressed) != meta["raw_size_bytes"]:
        raise ValueError("Raw length mismatch")
    digest = hashlib.sha256(decompressed).hexdigest()
    if digest != EXPECTED_SHA:
        raise ValueError(f"Raw SHA mismatch: {digest}")
    output = BASE / "data" / meta["raw_filename"]
    output.write_bytes(decompressed)
    with output.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert set(("time","open","high","low","close","tick_volume","spread")) <= set(reader.fieldnames)
        times = [int(row["time"]) for row in reader]
    if len(times) != EXPECTED_ROWS:
        raise ValueError(f"Expected {EXPECTED_ROWS} candles, got {len(times)}")
    if times[0] != EXPECTED_START or times[-1] != EXPECTED_END:
        raise ValueError(f"Unexpected times: {times[0]}, {times[-1]}")
    print(f"DATA_VERIFIED rows={len(times)} sha256={digest} first={times[0]} last={times[-1]}")
    return output

if __name__ == "__main__":
    rebuild()
