"""Stage B: read-only CSV audit. Standard library; no strategy or network code."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION = "1.0.0"
STATES = {"VERIFIED", "UNVERIFIED", "CONTRADICTED", "NOT_APPLICABLE"}
DIMENSIONS = ("source_provenance", "bar_timing", "timezone", "session_calendar",
              "price_side", "data_license")
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z", re.ASCII)
SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


class AuditError(ValueError):
    """Safe public error code: never echo private paths or arbitrary input values."""


def fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            size += len(block)
            digest.update(block)
    return {"sha256": digest.hexdigest(), "bytes": size}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuditError("CONFIG_DUPLICATE_KEY")
        result[key] = value
    return result


def read_config(path: Path) -> tuple[dict, dict]:
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              AuditError("CONFIG_NONFINITE_NUMBER")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError("CONFIG_INVALID_JSON_OR_ENCODING") from exc
    if not isinstance(data, dict):
        raise AuditError("CONFIG_NOT_OBJECT")
    return data, {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _int(value, minimum=None):
    return type(value) is int and (minimum is None or value >= minimum)


def validate_configs(schema: dict, manifest: dict):
    required = {"schema_version", "encoding", "delimiter", "columns", "timestamp",
                "price", "max_input_bytes", "max_examples_per_category"}
    if set(schema) != required or type(schema["schema_version"]) is not int or schema["schema_version"] != 1:
        raise AuditError("SCHEMA_KEYS_OR_VERSION_INVALID")
    if schema["encoding"] != "utf-8" or schema["delimiter"] != ",":
        raise AuditError("SCHEMA_ENCODING_OR_DELIMITER_UNSUPPORTED")
    if schema["columns"] != ["timestamp", "open", "high", "low", "close"]:
        raise AuditError("SCHEMA_COLUMNS_UNSUPPORTED")
    ts = schema["timestamp"]
    if not isinstance(ts, dict) or set(ts) != {"unit", "origin", "interval_ms",
                                               "minimum_ms", "maximum_ms_exclusive"}:
        raise AuditError("SCHEMA_TIMESTAMP_INVALID")
    if ts["unit"] != "ms" or ts["origin"] != "unix":
        raise AuditError("SCHEMA_TIMESTAMP_UNIT_UNSUPPORTED")
    if (not _int(ts["interval_ms"], 1) or
            not _int(ts["minimum_ms"]) or not _int(ts["maximum_ms_exclusive"]) or
            ts["minimum_ms"] >= ts["maximum_ms_exclusive"]):
        raise AuditError("SCHEMA_TIMESTAMP_BOUNDS_INVALID")
    try:
        utc_ms(ts["minimum_ms"])
        utc_ms(ts["maximum_ms_exclusive"])
    except (OverflowError, ValueError) as exc:
        raise AuditError("SCHEMA_TIMESTAMP_BOUNDS_INVALID") from exc
    if (not isinstance(schema["price"], dict) or
            set(schema["price"]) != {"require_positive", "require_finite"} or
            any(value is not True for value in schema["price"].values())):
        raise AuditError("SCHEMA_PRICE_RULE_UNSUPPORTED")
    if not _int(schema["max_input_bytes"], 1) or not _int(
            schema["max_examples_per_category"], 1):
        raise AuditError("SCHEMA_LIMIT_INVALID")
    if schema["max_examples_per_category"] > 100:
        raise AuditError("SCHEMA_EXAMPLE_LIMIT_EXCEEDED")
    keys = {"manifest_version", "dataset_id", "expected_input", "evidence",
            "source_claims", "calendar", "review_notes"}
    if set(manifest) != keys or type(manifest["manifest_version"]) is not int or manifest["manifest_version"] != 1:
        raise AuditError("MANIFEST_KEYS_OR_VERSION_INVALID")
    if not isinstance(manifest["dataset_id"], str) or not manifest["dataset_id"]:
        raise AuditError("MANIFEST_DATASET_ID_INVALID")
    expected = manifest["expected_input"]
    if (not isinstance(expected, dict) or set(expected) != {"bytes", "sha256"} or
            not _int(expected["bytes"], 0) or
            not isinstance(expected["sha256"], str) or
            not SHA256.fullmatch(expected["sha256"])):
        raise AuditError("MANIFEST_INPUT_BINDING_INVALID")
    evidence = manifest["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != set(DIMENSIONS):
        raise AuditError("MANIFEST_EVIDENCE_DIMENSIONS_INVALID")
    for item in evidence.values():
        if (not isinstance(item, dict) or set(item) != {"status", "reason", "references"}
                or not isinstance(item["status"], str) or item["status"] not in STATES or not isinstance(item["reason"], str)
                or not item["reason"].strip() or not isinstance(item["references"], list)
                or not all(isinstance(x, str) and x.strip() for x in item["references"])):
            raise AuditError("MANIFEST_EVIDENCE_INVALID")
        if item["status"] == "VERIFIED" and not item["references"]:
            raise AuditError("VERIFIED_DECLARATION_WITHOUT_REFERENCE")
    if not isinstance(manifest["source_claims"], dict) or not isinstance(
            manifest["review_notes"], list):
        raise AuditError("MANIFEST_NOTES_INVALID")
    calendar = manifest["calendar"]
    if (not isinstance(calendar, dict) or set(calendar) !=
            {"coverage_start_ms", "coverage_end_ms", "closed_intervals", "synthetic"}
            or type(calendar["synthetic"]) is not bool):
        raise AuditError("CALENDAR_INVALID")
    closed = calendar["closed_intervals"]
    if not isinstance(closed, list):
        raise AuditError("CALENDAR_INTERVALS_INVALID")
    start, end = calendar["coverage_start_ms"], calendar["coverage_end_ms"]
    if start is None and end is None and not closed:
        return
    if not _int(start) or not _int(end) or start >= end:
        raise AuditError("CALENDAR_COVERAGE_INVALID")
    prior_end = start
    for interval in closed:
        if (not isinstance(interval, list) or len(interval) != 2 or
                not all(_int(x) for x in interval) or
                not (start <= interval[0] < interval[1] <= end) or
                interval[0] < prior_end):
            raise AuditError("CALENDAR_INTERVALS_INVALID")
        prior_end = interval[1]


def utc_ms(value: int) -> str:
    """Exact integer arithmetic. This is an interpretation, not source-clock proof."""
    return (EPOCH + timedelta(milliseconds=value)).isoformat(timespec="milliseconds")


def _session(manifest: dict, timestamp: int) -> str:
    """Only classifications according to supplied, declared calendar evidence."""
    c = manifest["calendar"]
    e = manifest["evidence"]
    if any(e[k]["status"] != "VERIFIED" for k in
           ("session_calendar", "timezone", "bar_timing")):
        return "UNKNOWN"
    if c["coverage_start_ms"] is None or not (
            c["coverage_start_ms"] <= timestamp < c["coverage_end_ms"]):
        return "UNKNOWN"
    if any(a <= timestamp < b for a, b in c["closed_intervals"]):
        return "CLOSED_ACCORDING_TO_DECLARED_CALENDAR"
    return "OPEN_ACCORDING_TO_DECLARED_CALENDAR"


def _scan(raw: bytes, schema: dict, manifest: dict) -> dict:
    """Preserve raw record order. No sorting, deduplication or data repair."""
    try:
        text = raw.decode(schema["encoding"], errors="strict")
    except UnicodeError as exc:
        raise AuditError("CSV_ENCODING_INVALID") from exc
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=",", strict=True)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise AuditError("CSV_EMPTY") from exc
    except csv.Error as exc:
        raise AuditError("CSV_HEADER_MALFORMED") from exc
    if header != schema["columns"]:
        raise AuditError("CSV_HEADER_MISMATCH")
    counts = Counter()
    categories = Counter()
    examples = {}
    interval = schema["timestamp"]["interval_ms"]
    lower = schema["timestamp"]["minimum_ms"]
    upper = schema["timestamp"]["maximum_ms_exclusive"]
    maximum_examples = schema["max_examples_per_category"]
    seen = {}
    prior_ts = None
    prior_close = None
    flat_run = 0
    longest_flat_run = 0
    gap_histogram = Counter()
    gap_session_counts = Counter()
    sessions = Counter()
    weekdays = Counter()
    flat_weekdays = Counter()
    min_ts = max_ts = None

    def finding(code, record, line, **context):
        categories[code] += 1
        bucket = examples.setdefault(code, [])
        if len(bucket) < maximum_examples:
            bucket.append({"record": record, "physical_line_end": line, **context})

    try:
        for record, row in enumerate(reader, 1):
            counts["records_read"] += 1
            line = reader.line_num
            errors = []
            ts = None
            prices = None
            if len(row) != 5:
                errors.append("ROW_FIELD_COUNT_INVALID")
            else:
                if not INTEGER.fullmatch(row[0]):
                    errors.append("TIMESTAMP_NOT_INTEGER")
                else:
                    try:
                        ts = int(row[0])
                    except ValueError:
                        errors.append("TIMESTAMP_NOT_INTEGER")
                    if ts is not None and not lower <= ts < upper:
                        errors.append("TIMESTAMP_OUT_OF_RANGE")
                        ts = None
                    elif ts is not None and ts % interval:
                        errors.append("TIMESTAMP_NOT_ALIGNED")
                        ts = None
                try:
                    prices = [Decimal(x) for x in row[1:]]
                    if not all(p.is_finite() and p > 0 for p in prices):
                        errors.append("PRICE_NOT_FINITE_POSITIVE")
                        prices = None
                    elif not (prices[2] <= min(prices[0], prices[3]) <=
                              max(prices[0], prices[3]) <= prices[1]):
                        errors.append("OHLC_INCONSISTENT")
                        prices = None
                except (InvalidOperation, ValueError):
                    errors.append("PRICE_NOT_NUMERIC")
                    prices = None
            if not errors:
                counts["schema_valid_records"] += 1
            else:
                counts["schema_invalid_records"] += 1
            if ts is not None:
                counts["valid_time_records"] += 1
                min_ts = ts if min_ts is None else min(min_ts, ts)
                max_ts = ts if max_ts is None else max(max_ts, ts)
                weekday = (EPOCH + timedelta(milliseconds=ts)).strftime("%A")
                weekdays[weekday] += 1
                session = _session(manifest, ts)
                sessions[session] += 1
                if session == "UNKNOWN":
                    counts["session_unknown_records"] += 1
                elif session.startswith("CLOSED_"):
                    finding("BAR_IN_DECLARED_CLOSED_SESSION", record, line,
                            timestamp_ms=ts)
                if ts in seen:
                    first_record, first_row = seen[ts]
                    code = "DUPLICATE_IDENTICAL" if row == first_row else "DUPLICATE_CONFLICTING"
                    errors.append(code)
                    finding(code, record, line, first_record=first_record, timestamp_ms=ts)
                else:
                    seen[ts] = (record, row)
                if prior_ts is not None and ts < prior_ts:
                    errors.append("TIME_DESCENDING")
                    finding("TIME_DESCENDING", record, line, timestamp_ms=ts)
                if prior_ts is not None and ts - prior_ts > interval:
                    delta = ts - prior_ts
                    missing = (delta // interval) - 1
                    counts["gap_events_over_interval"] += 1
                    counts["unobserved_grid_slots_between_rows"] += missing
                    counts["maximum_gap_ms"] = max(counts["maximum_gap_ms"], delta)
                    gap_histogram[str(delta)] += 1
                    # Bounded by schema/file limits; classify only supplied calendar coverage.
                    if missing <= 100000:
                        labels = {_session(manifest, t)
                                  for t in range(prior_ts + interval, ts, interval)}
                        if labels == {"CLOSED_ACCORDING_TO_DECLARED_CALENDAR"}:
                            gap_class = "ALL_UNOBSERVED_SLOTS_CLOSED_IN_DECLARED_CALENDAR"
                        elif "UNKNOWN" in labels:
                            gap_class = "UNKNOWN"
                        else:
                            gap_class = "HAS_UNOBSERVED_OPEN_SLOTS_IN_DECLARED_CALENDAR"
                    else:
                        gap_class = "UNKNOWN_CLASSIFICATION_LIMIT"
                    gap_session_counts[gap_class] += 1
                    finding("GAP_OBSERVED", record, line, previous_timestamp_ms=prior_ts,
                            timestamp_ms=ts, delta_ms=delta, unobserved_slots=missing,
                            classification=gap_class)
                if prices is not None and prices[1] == prices[2]:
                    counts["flat_records"] += 1
                    flat_weekdays[weekday] += 1
                    finding("FLAT_OBSERVED", record, line, timestamp_ms=ts)
                    flat_run = flat_run + 1 if prior_ts is not None and ts - prior_ts == interval else 1
                    longest_flat_run = max(longest_flat_run, flat_run)
                    if prior_close is not None and prices[3] == prior_close:
                        counts["flat_matching_previous_close"] += 1
                else:
                    flat_run = 0
            else:
                flat_run = 0
            for error in errors:
                if error not in ("DUPLICATE_IDENTICAL", "DUPLICATE_CONFLICTING", "TIME_DESCENDING"):
                    finding(error, record, line)
            if errors:
                counts["records_requiring_quarantine_review"] += 1
            else:
                counts["records_without_structural_findings"] += 1
            # Never bridge invalid timestamps using a fabricated time.
            prior_ts = ts
            prior_close = prices[3] if prices is not None else None
    except csv.Error as exc:
        finding("CSV_MALFORMED_RECORD", counts["records_read"] + 1, reader.line_num)
        counts["malformed_records_unparsed"] += 1
        counts["parsing_stopped_before_end"] = 1
    counts["unique_valid_timestamps"] = len(seen)
    counts["longest_contiguous_flat_run_records"] = longest_flat_run
    if not counts["records_read"]:
        counts["empty_data_after_header"] = 1
    keys = ("records_read", "schema_valid_records", "schema_invalid_records",
            "records_requiring_quarantine_review", "records_without_structural_findings",
            "valid_time_records", "unique_valid_timestamps", "session_unknown_records",
            "flat_records", "flat_matching_previous_close", "gap_events_over_interval",
            "unobserved_grid_slots_between_rows", "maximum_gap_ms",
            "longest_contiguous_flat_run_records", "malformed_records_unparsed",
            "parsing_stopped_before_end", "empty_data_after_header")
    return {"counts": {k: counts[k] for k in keys}, "category_counts": dict(sorted(categories.items())),
            "examples": examples, "examples_are_capped_per_category": maximum_examples,
            "counting_note": "Categories overlap. records_read = schema_valid_records + schema_invalid_records. "
                             "Quarantine review is a union of record-level structural findings, not their sum. "
                             "Unknown session and flat/gap observations are separate, overlapping dimensions. "
                             "Duplicate identity compares raw fields; textual differences require review, not proved price disagreement. "
                             "Malformed unparsed records are separately counted; do not claim full coverage after parse failure.",
            "timestamp_interpretation": {"unit": "unix milliseconds", "source_clock_verified_by_conversion": False,
                                         "minimum_ms": min_ts, "maximum_ms": max_ts,
                                         "first_interpreted_utc": utc_ms(min_ts) if min_ts is not None else None,
                                         "last_interpreted_utc": utc_ms(max_ts) if max_ts is not None else None},
            "gap_histogram_ms": dict(sorted(gap_histogram.items())),
            "gap_calendar_classifications": dict(sorted(gap_session_counts.items())),
            "weekday_records": dict(sorted(weekdays.items())),
            "weekday_flat_records": dict(sorted(flat_weekdays.items())),
            "calendar_classification_note": "Classification is conditional on supplied declarations, not independent "
                                            "source/calendar verification. Flat observations never imply fabricated data."}


def audit_file(input_path: Path, schema_path: Path, manifest_path: Path) -> dict:
    started = time.perf_counter()
    report = {"tool": {"name": "faraz-stage-b-validator", "version": VERSION,
                        "python": sys.version.split()[0], "code_sha256": fingerprint(Path(__file__))["sha256"]},
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "input": {"name": input_path.name}, "critical_errors": [],
              "execution": {"network_used": False, "packages_installed": False,
                            "strategy_or_backtest_run": False, "raw_input_written": False},
              "structure": {"status": "NOT_EVALUATED"},
              "financial_use": {"status": "NOT_AUTHORIZED", "authorized": False,
                                "reason": "Stage B never authorizes financial evaluation, strategy ranking or trading."}}
    before = after = None
    try:
        before = fingerprint(input_path)
        report["input"]["before"] = before
        schema, schema_fingerprint = read_config(schema_path)
        manifest, manifest_fingerprint = read_config(manifest_path)
        report["configuration"] = {"schema": schema_fingerprint, "manifest": manifest_fingerprint}
        validate_configs(schema, manifest)
        report["dataset_id"] = manifest["dataset_id"]
        report["evidence"] = manifest["evidence"]
        report["evidence_note"] = ("Statuses and references are reviewed manifest declarations; this offline tool "
                                   "does not authenticate external evidence or certify source clocks.")
        report["provenance_session_summary"] = (
            "CONTRADICTED" if any(x["status"] == "CONTRADICTED" for x in manifest["evidence"].values())
            else "UNVERIFIED" if any(x["status"] != "VERIFIED" for x in manifest["evidence"].values())
            else "DECLARED_VERIFIED_NOT_INDEPENDENTLY_AUTHENTICATED")
        if before != manifest["expected_input"]:
            raise AuditError("INPUT_HASH_OR_SIZE_MISMATCH")
        if before["bytes"] > schema["max_input_bytes"]:
            raise AuditError("INPUT_SIZE_LIMIT_EXCEEDED")
        raw = input_path.read_bytes()
        if {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} != before:
            raise AuditError("INPUT_CHANGED_DURING_READ")
        scan = _scan(raw, schema, manifest)
        report["audit"] = scan
        c = scan["counts"]
        failed = (c["records_requiring_quarantine_review"] or c["parsing_stopped_before_end"]
                  or c["empty_data_after_header"])
        report["structure"]["status"] = "FAIL" if failed else "PASS"
        report["structure"]["scope"] = "Declared field/time/OHLC/ordering rules only; not source authenticity or completeness."
    except AuditError as exc:
        report["critical_errors"].append(str(exc))
        report["structure"]["status"] = "FAIL"
    except (OSError, OverflowError) as exc:
        report["critical_errors"].append("INPUT_OR_CONFIG_IO_ERROR:" + type(exc).__name__)
        report["structure"]["status"] = "FAIL"
    finally:
        if before is not None:
            try:
                after = fingerprint(input_path)
                report["input"]["after"] = after
            except OSError:
                report["critical_errors"].append("INPUT_AFTER_FINGERPRINT_UNAVAILABLE")
            report["input"]["unchanged"] = before == after
            if before != after:
                report["critical_errors"].append("INPUT_CHANGED_CRITICAL")
                report["structure"]["status"] = "FAIL"
        else:
            report["input"]["unchanged"] = None
        stable = {k: v for k, v in report.items() if k not in ("generated_at_utc",)}
        report["reproducible_content_sha256"] = hashlib.sha256(json.dumps(
            stable, sort_keys=True, ensure_ascii=False, allow_nan=False,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        report["duration_seconds"] = round(time.perf_counter() - started, 6)
    return report


def check_output_path(output: Path, protected: tuple[Path, ...]):
    resolved = output.resolve()
    if os.path.lexists(output):
        raise AuditError("OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    for path in protected:
        if resolved == path.resolve():
            raise AuditError("OUTPUT_OVERLAPS_PROTECTED_INPUT")
    # A report must be outside the raw dataset directory, including symlink aliases.
    data_dir = protected[0].resolve().parent
    if resolved.parent == data_dir or data_dir in resolved.parents:
        raise AuditError("OUTPUT_INSIDE_RAW_INPUT_DIRECTORY")
    if not resolved.parent.is_dir():
        raise AuditError("OUTPUT_PARENT_MUST_ALREADY_EXIST")


def write_new_report(output: Path, report: dict, protected: tuple[Path, ...]):
    check_output_path(output, protected)
    payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    # Exclusive creation also refuses a file/symlink created after the preflight check.
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--schema", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    protected = (args.input, args.schema, args.manifest)
    try:
        check_output_path(args.output, protected)
        report = audit_file(*protected)
        write_new_report(args.output, report, protected)
    except (AuditError, OSError) as exc:
        code = str(exc) if isinstance(exc, AuditError) else type(exc).__name__
        print(json.dumps({"report_written": False, "error": code}), file=sys.stderr)
        return 2
    code = 2 if report["critical_errors"] else 1 if report["structure"]["status"] == "FAIL" else 0
    print(json.dumps({"report_written": True, "structure": report["structure"]["status"],
                      "provenance_session": report.get("provenance_session_summary", "UNVERIFIED"),
                      "financial_use_authorized": False, "input_unchanged": report["input"]["unchanged"],
                      "exit_code": code}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
