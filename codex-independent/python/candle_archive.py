"""Durable, read-only-trading XAU M15 archive; Python standard library only.

Native MT5 bar timestamps are kept as integers without local-time conversion.
An independently stored head is needed against coordinated archive+anchor rollback.
No hash-only design can prove authenticity after all copies are rewritten.
"""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

ZERO = "0" * 64
VERSION = 1

class ArchiveError(ValueError): pass
class IntegrityError(ArchiveError): pass
class InvalidCandle(ArchiveError): pass
class ConflictingCandle(ArchiveError): pass
class WriterBusy(ArchiveError): pass

def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")

def digest(value): return hashlib.sha256(canonical(value)).hexdigest()

def _integer(value, field, minimum=0):
    # numpy scalar integers are accepted via __index__, floats never are.
    if isinstance(value, bool): raise InvalidCandle(f"INVALID_INTEGER:{field}")
    try: result = value.__index__()
    except (AttributeError, TypeError): raise InvalidCandle(f"INVALID_INTEGER:{field}") from None
    result = int(result)
    if result < minimum: raise InvalidCandle(f"OUT_OF_RANGE:{field}")
    return result

def _price(value, field):
    if isinstance(value, bool): raise InvalidCandle(f"INVALID_PRICE:{field}")
    try: price = Decimal(str(value))
    except (InvalidOperation, ValueError): raise InvalidCandle(f"INVALID_PRICE:{field}") from None
    if not price.is_finite() or price <= 0: raise InvalidCandle(f"INVALID_PRICE:{field}")
    return format(price.normalize(), "f")

def normalize_bar(bar, current_bar_open):
    """Validate complete closed bar. current_bar_open must come from bar zero.

    Timestamp grid alignment is not forced to epoch%900: broker-native opening
    boundaries are validated relative to its current bar's opening boundary.
    """
    current = _integer(current_bar_open, "current_bar_open", 1)
    try:
        stamp = _integer(bar["time"], "time", 1)
        values = {key: _price(bar[key], key) for key in ("open", "high", "low", "close")}
        result = {"time": stamp, **values,
                  "tick_volume": _integer(bar["tick_volume"], "tick_volume"),
                  "spread": _integer(bar["spread"], "spread"),
                  "real_volume": _integer(bar["real_volume"], "real_volume")}
    except KeyError as error: raise InvalidCandle(f"MISSING_FIELD:{error.args[0]}") from None
    if stamp >= current or stamp + 900 > current: raise InvalidCandle("BAR_NOT_CLOSED")
    if (current - stamp) % 900: raise InvalidCandle("M15_BOUNDARY_MISMATCH")
    o, h, l, c = (Decimal(values[k]) for k in ("open", "high", "low", "close"))
    if h < max(o, c) or l > min(o, c) or l > h: raise InvalidCandle("MALFORMED_OHLC")
    return result

def _atomic(path, value):
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as out:
        out.write(canonical(value) + b"\n"); out.flush(); os.fsync(out.fileno())
    os.replace(tmp, path)

def _read_json(path):
    try: return json.loads(path.read_bytes())
    except (OSError, ValueError, TypeError): raise IntegrityError(f"INVALID_METADATA:{path.name}") from None

@contextlib.contextmanager
def writer_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / "writer.lock").open("a+b")
    try:
        lock.seek(0, 2)
        if lock.tell() == 0: lock.write(b"0"); lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError: raise WriterBusy("ARCHIVE_WRITER_BUSY") from None
        yield
    finally:
        # close releases the OS lock even after an exception or process death.
        lock.close()

def _scan(root):
    path = root / "candles.jsonl"
    if not path.exists(): raise IntegrityError("ARCHIVE_MISSING")
    bars = {}; records = []; previous = ZERO
    try:
        with path.open("rb") as source:
            for index, line in enumerate(source, 1):
                if not line.endswith(b"\n"): raise IntegrityError("TORN_ARCHIVE_TAIL")
                item = json.loads(line)
                if canonical(item) + b"\n" != line: raise IntegrityError("NONCANONICAL_RECORD")
                if set(item) != {"version", "index", "previous", "symbol", "timeframe", "bar", "sha256"}:
                    raise IntegrityError("RECORD_SCHEMA")
                given = item["sha256"]; content = {k:v for k,v in item.items() if k != "sha256"}
                if item["index"] != index or item["previous"] != previous or digest(content) != given:
                    raise IntegrityError("CHAIN_MISMATCH")
                if item["version"] != VERSION or item["timeframe"] != "M15" or not item["symbol"].startswith("XAUUSD"):
                    raise IntegrityError("SCOPE_MISMATCH")
                bar = item["bar"]
                if normalize_bar(bar, bar["time"] + 900) != bar: raise IntegrityError("NONCANONICAL_CANDLE")
                if bar["time"] in bars: raise IntegrityError("DUPLICATE_ARCHIVED_TIMESTAMP")
                if bars and (bar['time']-next(iter(bars)))%900:raise IntegrityError('MIXED_NATIVE_M15_GRIDS')
                if records and item["symbol"] != records[0]["symbol"]: raise IntegrityError("MIXED_SYMBOLS")
                bars[bar["time"]] = bar; previous = given; records.append(item)
    except IntegrityError: raise
    except (ValueError, KeyError, TypeError, ArchiveError, OSError): raise IntegrityError("INVALID_ARCHIVE_RECORD") from None
    head = {"version": VERSION, "count": len(records), "head_sha256": previous,
            "latest_time": max(bars) if bars else None,
            "symbol": records[0]["symbol"] if records else None, "timeframe": "M15"}
    return records, bars, head

def unresolved_gaps(bars):
    times = sorted(bars)
    return [{"after": a, "before": b, "absent_grid_slots": (b-a)//900-1,
             "status": "GAP_UNRESOLVED", "cause": "UNKNOWN_NOT_AUTOMATIC_DATA_LOSS_OR_FVG"}
            for a,b in zip(times,times[1:]) if b-a > 900]

def verify_archive(root, expected_head=None):
    """Independent full scan, no repair or writes. Optional externally pinned head.

    Returns row count, chain head, native latest time and unresolved time gaps.
    A pending transaction requires the writer's recovery path before verification.
    """
    root = Path(root)
    if (root/"pending.json").exists(): raise IntegrityError("RECOVERY_REQUIRED")
    records, bars, head = _scan(root)
    for name in ("checkpoint.json", "anchor.json"):
        if _read_json(root/name) != head: raise IntegrityError(f"HEAD_ANCHOR_MISMATCH:{name}")
    if expected_head is not None:
        # External pin may describe a historical prefix, allowing valid growth.
        count = expected_head["count"]; pin = expected_head["head_sha256"]
        actual = ZERO if count == 0 else records[count-1]["sha256"] if 0 < count <= len(records) else None
        if actual != pin: raise IntegrityError("EXTERNAL_PIN_MISMATCH")
    return {**head, "gaps": unresolved_gaps(bars), "verified": True,
            "coordinated_rewrite_without_external_pin_detectable": False}

class CandleArchive:
    """One bounded transaction per ingest. No always-running process."""
    def __init__(self, root): self.root = Path(root)

    def _recover(self):
        root = self.root; pending_path = root/"pending.json"
        if not pending_path.exists(): return False
        pending = _read_json(pending_path)
        if set(pending) != {"content", "sha256"} or digest(pending["content"]) != pending["sha256"]:
            raise IntegrityError("PENDING_HASH_MISMATCH")
        plan = pending["content"]; path=root/"candles.jsonl"
        if set(plan) != {"before", "after", "prefix_bytes", "append_hex", "prefix_sha256"}:
            raise IntegrityError("PENDING_SCHEMA")
        data=path.read_bytes(); prefix_size=plan["prefix_bytes"]
        prefix=data[:prefix_size]; tail=data[prefix_size:]
        try: expected=bytes.fromhex(plan["append_hex"])
        except (ValueError, TypeError): raise IntegrityError("PENDING_BYTES_INVALID") from None
        if len(prefix)!=prefix_size or hashlib.sha256(prefix).hexdigest()!=plan["prefix_sha256"]:
            raise IntegrityError("PENDING_PREFIX_CHANGED")
        if not expected.startswith(tail): raise IntegrityError("PENDING_TAIL_CONFLICT")
        for name in ("checkpoint.json", "anchor.json"):
            value=_read_json(root/name)
            if value not in (plan["before"],plan["after"]): raise IntegrityError("PENDING_HEAD_CONFLICT")
            # An advanced anchor means all append bytes were durable already.
            if value==plan["after"] and tail!=expected: raise IntegrityError("ANCHORED_TAIL_TRUNCATED")
        with path.open("ab") as out:
            out.write(expected[len(tail):]); out.flush(); os.fsync(out.fileno())
        _,_,actual = _scan(root)
        if actual != plan["after"]: raise IntegrityError("PENDING_POSTCONDITION_MISMATCH")
        _atomic(root/"checkpoint.json", actual); _atomic(root/"anchor.json", actual)
        pending_path.unlink()
        return True

    def ingest(self, bars, *, current_bar_open, symbol="XAUUSD.st", timeframe="M15"):
        started=time.perf_counter(); root=self.root
        if timeframe!="M15" or not isinstance(symbol,str) or not symbol.startswith("XAUUSD") or len(symbol)>64:
            raise InvalidCandle("ONLY_XAUUSD_M15_SUPPORTED")
        if any(ch in symbol for ch in "\r\n\x00"): raise InvalidCandle("INVALID_SYMBOL")
        with writer_lock(root):
            files=[root/name for name in ("candles.jsonl","checkpoint.json","anchor.json")]
            if not any(p.exists() for p in files):
                (root/"candles.jsonl").touch()
                _,_,empty=_scan(root)
                _atomic(root/"checkpoint.json",empty);_atomic(root/"anchor.json",empty)
            elif not all(p.exists() for p in files): raise IntegrityError("ARCHIVE_COMPONENT_MISSING")
            recovered=self._recover()
            verify_archive(root)
            records, existing, before=_scan(root)
            if before["symbol"] not in (None,symbol): raise InvalidCandle("ARCHIVE_SYMBOL_MISMATCH")
            validate_started=time.perf_counter(); normalized=[]; seen={}; duplicates=0
            for raw in bars:
                row=normalize_bar(raw,current_bar_open);stamp=row["time"]
                if existing and (stamp-next(iter(existing)))%900:raise InvalidCandle('ARCHIVE_NATIVE_GRID_MISMATCH')
                prior=seen.get(stamp,existing.get(stamp))
                if prior is not None:
                    if prior!=row:raise ConflictingCandle(f"CONFLICTING_CANDLE:{stamp}")
                    duplicates+=1;continue
                seen[stamp]=row;normalized.append(row)
            validation_seconds=time.perf_counter()-validate_started
            processing_started=time.perf_counter()
            was_out_of_order=any(a["time"]>b["time"] for a,b in zip(normalized,normalized[1:]))
            normalized.sort(key=lambda x:x["time"])
            backfilled=sum(before["latest_time"] is not None and b["time"]<before["latest_time"] for b in normalized)
            new_records=[];previous=before["head_sha256"]
            for row in normalized:
                content={"version":VERSION,"index":len(records)+len(new_records)+1,"previous":previous,
                         "symbol":symbol,"timeframe":"M15","bar":row}
                item={**content,"sha256":digest(content)};previous=item["sha256"];new_records.append(item)
            merged={**existing,**{r["time"]:r for r in normalized}}
            after={**before,"count":len(records)+len(new_records),"head_sha256":previous,
                   "latest_time":max(merged) if merged else None,"symbol":symbol if merged else None}
            processing_seconds=time.perf_counter()-processing_started
            storage_started=time.perf_counter()
            if new_records:
                archive_path=root/"candles.jsonl";prefix=archive_path.read_bytes()
                append=b"".join(canonical(r)+b"\n" for r in new_records)
                plan={"before":before,"after":after,"prefix_bytes":len(prefix),
                      "prefix_sha256":hashlib.sha256(prefix).hexdigest(),"append_hex":append.hex()}
                _atomic(root/"pending.json",{"content":plan,"sha256":digest(plan)})
                with archive_path.open("ab") as out:out.write(append);out.flush();os.fsync(out.fileno())
                _atomic(root/"checkpoint.json",after);_atomic(root/"anchor.json",after)
                (root/"pending.json").unlink()
            storage_seconds=time.perf_counter()-storage_started
            verification_started=time.perf_counter(); verified=verify_archive(root)
            verification_seconds=time.perf_counter()-verification_started
            return {"added":len(new_records),"duplicates":duplicates,"backfilled":backfilled,
                    "out_of_order_input":was_out_of_order,"recovered_transaction":recovered,
                    "head":{k:v for k,v in verified.items() if k not in ("gaps","verified","coordinated_rewrite_without_external_pin_detectable")},
                    "gaps":verified["gaps"],"timings_seconds":{"validation":validation_seconds,
                        "processing":processing_seconds,"storage":storage_seconds,"verification":verification_seconds,
                        "total":time.perf_counter()-started},"orders_enabled":False}

    def verify(self, expected_head=None):return verify_archive(self.root,expected_head)

    def latest_time(self):return self.verify()["latest_time"]

    def read_bars(self):
        self.verify()
        _,bars,_=_scan(self.root)
        return [bars[t] for t in sorted(bars)]
