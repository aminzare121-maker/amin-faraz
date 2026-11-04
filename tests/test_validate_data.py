"""All CSV fixtures below are generated synthetic data in temporary directories.

No raw market data, network, downloader, dependencies or trading SDK are used.
"""
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import validate_data as v

ROOT = Path(__file__).resolve().parents[1]
BASE = 1762214400000
STEP = 900000
HEADER = "timestamp,open,high,low,close\n"


class DataAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="faraz-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rawdir = self.root / "raw"
        self.rawdir.mkdir()
        self.reports = self.root / "reports"
        self.reports.mkdir()
        self.input = self.rawdir / "SYNTHETIC.csv"
        self.schema_path = self.root / "schema.json"
        self.manifest_path = self.root / "manifest.json"
        self.schema = json.loads((ROOT / "data_schema.json").read_text(encoding="utf-8"))
        self.manifest = json.loads((ROOT / "data_manifest.json").read_text(encoding="utf-8"))
        self.manifest["dataset_id"] = "SYNTHETIC_UNIT_TEST_ONLY"
        self.manifest["source_claims"] = {"fixture": "SYNTHETIC; no market provenance"}
        self.write_input(HEADER + f"{BASE},100,102,99,101\n{BASE+STEP},101,103,100,102\n")

    def save_configs(self):
        self.schema_path.write_text(json.dumps(self.schema), encoding="utf-8")
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def write_input(self, text):
        self.input.write_bytes(text.encode("utf-8"))
        self.bind()

    def bind(self):
        self.manifest["expected_input"] = v.fingerprint(self.input)
        self.save_configs()

    def audit(self):
        self.save_configs()
        before = self.input.read_bytes()
        result = v.audit_file(self.input, self.schema_path, self.manifest_path)
        self.assertEqual(before, self.input.read_bytes())
        self.assertTrue(result["input"]["unchanged"])
        self.assertFalse(result["financial_use"]["authorized"])
        return result

    def cli(self, output):
        args = ["--input", str(self.input), "--schema", str(self.schema_path),
                "--manifest", str(self.manifest_path), "--output", str(output)]
        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
            code = v.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_three_exact_epoch_ms_examples(self):
        self.assertEqual(v.utc_ms(1762214400000), "2025-11-04T00:00:00.000+00:00")
        self.assertEqual(v.utc_ms(1777952700000), "2026-05-05T03:45:00.000+00:00")
        self.assertEqual(v.utc_ms(1793663100000), "2026-11-02T23:45:00.000+00:00")

    def test_structural_pass_never_authorizes_unknown_source(self):
        result = self.audit()
        self.assertEqual(result["structure"]["status"], "PASS")
        self.assertEqual(result["provenance_session_summary"], "UNVERIFIED")
        self.assertEqual(result["audit"]["counts"]["session_unknown_records"], 2)
        self.assertEqual(result["audit"]["counts"]["records_read"], 2)

    def test_seconds_nanoseconds_decimal_and_malformed_timestamp(self):
        for value, category in [(str(BASE//1000), "TIMESTAMP_OUT_OF_RANGE"),
                                (str(BASE*1000000), "TIMESTAMP_OUT_OF_RANGE"),
                                (str(BASE)+".0", "TIMESTAMP_NOT_INTEGER"),
                                ("not-a-date", "TIMESTAMP_NOT_INTEGER"),
                                ("+"+str(BASE), "TIMESTAMP_NOT_INTEGER")]:
            with self.subTest(value=value):
                self.write_input(HEADER + f"{value},100,102,99,101\n")
                r = self.audit()
                self.assertEqual(r["structure"]["status"], "FAIL")
                self.assertEqual(r["audit"]["category_counts"][category], 1)

    def test_range_exclusive_alignment_and_bool_config(self):
        for timestamp, category in [(BASE-STEP, "TIMESTAMP_OUT_OF_RANGE"),
                                    (self.schema["timestamp"]["maximum_ms_exclusive"], "TIMESTAMP_OUT_OF_RANGE"),
                                    (BASE+1, "TIMESTAMP_NOT_ALIGNED")]:
            self.write_input(HEADER + f"{timestamp},100,102,99,101\n")
            self.assertIn(category, self.audit()["audit"]["category_counts"])
        self.schema["timestamp"]["interval_ms"] = True
        self.assertIn("SCHEMA_TIMESTAMP_BOUNDS_INVALID", self.audit()["critical_errors"])

    def test_malformed_evidence_and_calendar_configs_fail_closed(self):
        original = copy.deepcopy(self.manifest)
        for status in ([], {}, "UNKNOWN", True):
            self.manifest = copy.deepcopy(original)
            self.manifest["evidence"]["timezone"]["status"] = status
            self.assertIn("MANIFEST_EVIDENCE_INVALID", self.audit()["critical_errors"])
        self.manifest = copy.deepcopy(original)
        self.manifest["calendar"]["closed_intervals"] = [[BASE, BASE+STEP]]
        self.assertIn("CALENDAR_COVERAGE_INVALID", self.audit()["critical_errors"])

    def test_verified_needs_reference_and_never_authorizes_finance(self):
        self.manifest["evidence"]["timezone"].update(status="VERIFIED", references=[])
        self.assertIn("VERIFIED_DECLARATION_WITHOUT_REFERENCE", self.audit()["critical_errors"])
        for item in self.manifest["evidence"].values():
            item.update(status="VERIFIED", reason="Synthetic declaration only", references=["SYNTHETIC fixture"])
        r = self.audit()
        self.assertEqual(r["provenance_session_summary"], "DECLARED_VERIFIED_NOT_INDEPENDENTLY_AUTHENTICATED")
        self.assertFalse(r["financial_use"]["authorized"])

    def test_contradicted_and_not_applicable_never_pass_as_verified(self):
        for state, summary in [("CONTRADICTED", "CONTRADICTED"), ("NOT_APPLICABLE", "UNVERIFIED")]:
            self.manifest["evidence"]["price_side"]["status"] = state
            self.assertEqual(self.audit()["provenance_session_summary"], summary)

    def test_invalid_prices_ohlc_and_wrong_column_count(self):
        cases = [("100,99,98,101", "OHLC_INCONSISTENT"),
                 ("100,NaN,99,101", "PRICE_NOT_FINITE_POSITIVE"),
                 ("100,Infinity,99,101", "PRICE_NOT_FINITE_POSITIVE"),
                 ("0,102,0,101", "PRICE_NOT_FINITE_POSITIVE"),
                 ("100,bad,99,101", "PRICE_NOT_NUMERIC"),
                 ("100,102,99", "ROW_FIELD_COUNT_INVALID")]
        for fields, category in cases:
            with self.subTest(category=category):
                self.write_input(HEADER+f"{BASE},{fields}\n")
                r = self.audit()
                self.assertEqual(r["structure"]["status"], "FAIL")
                self.assertEqual(r["audit"]["category_counts"][category], 1)
                self.assertEqual(r["audit"]["examples"][category][0]["physical_line_end"], 2)

    def test_duplicate_conflict_order_and_overlapping_counts(self):
        self.write_input(HEADER + f"{BASE},100,102,99,101\n" +
                         f"{BASE},100,102,99,101\n" +
                         f"{BASE},100,103,99,101\n" +
                         f"{BASE+STEP},101,103,100,102\n" +
                         f"{BASE},100,102,99,101\n")
        r = self.audit()["audit"]
        self.assertEqual(r["counts"]["records_read"], 5)
        self.assertEqual(r["counts"]["schema_valid_records"], 5)
        self.assertEqual(r["counts"]["records_requiring_quarantine_review"], 3)
        self.assertEqual(r["category_counts"]["DUPLICATE_IDENTICAL"], 2)
        self.assertEqual(r["category_counts"]["DUPLICATE_CONFLICTING"], 1)
        self.assertEqual(r["category_counts"]["TIME_DESCENDING"], 1)
        self.assertEqual(r["counts"]["unique_valid_timestamps"], 2)

    def test_flat_gap_are_observations_not_auto_quarantine(self):
        self.write_input(HEADER+f"{BASE},100,100,100,100\n{BASE+3*STEP},100,100,100,100\n")
        r = self.audit()
        a = r["audit"]
        self.assertEqual(r["structure"]["status"], "PASS")
        self.assertEqual(a["counts"]["flat_records"], 2)
        self.assertEqual(a["counts"]["gap_events_over_interval"], 1)
        self.assertEqual(a["counts"]["unobserved_grid_slots_between_rows"], 2)
        self.assertEqual(a["gap_calendar_classifications"], {"UNKNOWN": 1})
        self.assertEqual(a["counts"]["records_requiring_quarantine_review"], 0)

    def test_supplied_synthetic_calendar_vs_no_calendar_evidence(self):
        self.write_input(HEADER+f"{BASE},100,102,99,101\n{BASE+4*STEP},101,103,100,102\n")
        for key in ("session_calendar", "timezone", "bar_timing"):
            self.manifest["evidence"][key].update(
                status="VERIFIED", reason="SYNTHETIC test calendar", references=["SYNTHETIC fixture"])
        self.manifest["calendar"] = {"coverage_start_ms": BASE, "coverage_end_ms": BASE+10*STEP,
                                     "closed_intervals": [[BASE+STEP, BASE+4*STEP]], "synthetic": True}
        self.assertEqual(self.audit()["audit"]["gap_calendar_classifications"],
                         {"ALL_UNOBSERVED_SLOTS_CLOSED_IN_DECLARED_CALENDAR": 1})
        self.manifest["calendar"]["closed_intervals"] = [[BASE+STEP, BASE+2*STEP]]
        self.assertEqual(self.audit()["audit"]["gap_calendar_classifications"],
                         {"HAS_UNOBSERVED_OPEN_SLOTS_IN_DECLARED_CALENDAR": 1})
        self.manifest["evidence"]["session_calendar"]["status"] = "UNVERIFIED"
        self.assertEqual(self.audit()["audit"]["gap_calendar_classifications"], {"UNKNOWN": 1})

    def test_invalid_timestamp_never_bridges_adjacent_rows(self):
        self.write_input(HEADER+f"{BASE},100,102,99,101\ninvalid,100,102,99,101\n{BASE+3*STEP},100,102,99,101\n")
        r = self.audit()["audit"]
        self.assertEqual(r["counts"]["gap_events_over_interval"], 0)
        self.assertEqual(r["counts"]["schema_invalid_records"], 1)

    def test_empty_header_encoding_and_malformed_csv(self):
        for text, code in [("", "CSV_EMPTY"), ("timestamp,close\n", "CSV_HEADER_MISMATCH")]:
            self.write_input(text)
            self.assertIn(code, self.audit()["critical_errors"])
        self.input.write_bytes(b"\xff\xfe")
        self.bind()
        self.assertIn("CSV_ENCODING_INVALID", self.audit()["critical_errors"])
        self.write_input(HEADER)
        self.assertEqual(self.audit()["structure"]["status"], "FAIL")
        self.write_input(HEADER+'"unterminated')
        r = self.audit()
        self.assertEqual(r["structure"]["status"], "FAIL")
        self.assertEqual(r["audit"]["counts"]["parsing_stopped_before_end"], 1)

    def test_wrong_hash_and_size_stop_before_scan(self):
        for field, value in [("sha256", "0"*64), ("bytes", 1)]:
            self.bind()
            self.manifest["expected_input"][field] = value
            r = self.audit()
            self.assertIn("INPUT_HASH_OR_SIZE_MISMATCH", r["critical_errors"])
            self.assertNotIn("audit", r)

    def test_size_limit_and_unsupported_unit(self):
        self.schema["max_input_bytes"] = 1
        self.assertIn("INPUT_SIZE_LIMIT_EXCEEDED", self.audit()["critical_errors"])
        self.schema["timestamp"]["unit"] = "s"
        self.assertIn("SCHEMA_TIMESTAMP_UNIT_UNSUPPORTED", self.audit()["critical_errors"])

    def test_config_duplicate_keys_and_nan_are_rejected(self):
        for text, error in [('{"a":1,"a":2}', "CONFIG_DUPLICATE_KEY"),
                            ('{"a": NaN}', "CONFIG_NONFINITE_NUMBER")]:
            self.schema_path.write_text(text, encoding="utf-8")
            result = v.audit_file(self.input, self.schema_path, self.manifest_path)
            self.assertIn(error, result["critical_errors"])
            self.assertTrue(result["input"]["unchanged"])

    def test_change_during_read_and_after_audit_is_critical(self):
        original = v.fingerprint
        calls = 0

        def altered_fingerprint(path):
            nonlocal calls
            data = original(path)
            if path == self.input:
                calls += 1
                if calls > 1:
                    return {"sha256": "0"*64, "bytes": data["bytes"]}
            return data

        with patch.object(v, "fingerprint", side_effect=altered_fingerprint):
            result = v.audit_file(self.input, self.schema_path, self.manifest_path)
        self.assertIn("INPUT_CHANGED_CRITICAL", result["critical_errors"])
        self.assertFalse(result["input"]["unchanged"])
        self.assertEqual(result["structure"]["status"], "FAIL")

    def test_different_bytes_in_parse_read_stop_before_scan(self):
        original = Path.read_bytes

        def changed_bytes(path):
            data = original(path)
            return data + b"\n" if path == self.input else data

        with patch.object(Path, "read_bytes", changed_bytes):
            r = v.audit_file(self.input, self.schema_path, self.manifest_path)
        self.assertIn("INPUT_CHANGED_DURING_READ", r["critical_errors"])
        self.assertNotIn("audit", r)
        self.assertTrue(r["input"]["unchanged"])

    def test_overlapping_schema_errors_count_one_record(self):
        self.write_input(HEADER+"bad-time,100,99,98,101\n")
        a = self.audit()["audit"]
        self.assertEqual(a["counts"]["records_read"], 1)
        self.assertEqual(a["counts"]["schema_invalid_records"], 1)
        self.assertEqual(a["counts"]["records_requiring_quarantine_review"], 1)
        self.assertEqual(sum(a["category_counts"].values()), 2)

    def test_missing_input_fails_without_private_path_leak(self):
        r = v.audit_file(self.rawdir/"MISSING.csv", self.schema_path, self.manifest_path)
        self.assertEqual(r["structure"]["status"], "FAIL")
        self.assertIsNone(r["input"]["unchanged"])
        self.assertNotIn(str(self.root), json.dumps(r))

    def test_reproducibility_and_future_mutation_binding(self):
        first, second = self.audit(), self.audit()
        self.assertEqual(first["reproducible_content_sha256"], second["reproducible_content_sha256"])
        before = self.input.read_bytes()
        self.input.write_bytes(before + f"{BASE+2*STEP},102,104,101,103\n".encode())
        r = v.audit_file(self.input, self.schema_path, self.manifest_path)
        self.assertIn("INPUT_HASH_OR_SIZE_MISMATCH", r["critical_errors"])
        self.bind()
        third = self.audit()
        self.assertNotEqual(first["reproducible_content_sha256"], third["reproducible_content_sha256"])

    def test_explicit_input_ignores_other_csv(self):
        (self.rawdir / "Z_OTHER_SYNTHETIC.csv").write_text("invalid", encoding="utf-8")
        r = self.audit()
        self.assertEqual(r["structure"]["status"], "PASS")
        self.assertEqual(r["audit"]["counts"]["records_read"], 2)

    def test_cli_new_report_then_refuses_overwrite(self):
        output = self.reports / "audit.json"
        code, stdout, _ = self.cli(output)
        self.assertEqual(code, 0)
        saved = output.read_bytes()
        self.assertFalse(json.loads(saved)["financial_use"]["authorized"])
        code, _, stderr = self.cli(output)
        self.assertEqual(code, 2)
        self.assertIn("NO_OVERWRITE", stderr)
        self.assertEqual(saved, output.read_bytes())
        self.assertNotIn(str(self.root), stdout + stderr)

    def test_cli_input_and_raw_directory_overlap_refused(self):
        before = self.input.read_bytes()
        for output in (self.input, self.rawdir / "report.json", self.schema_path):
            self.assertEqual(self.cli(output)[0], 2)
        self.assertEqual(before, self.input.read_bytes())
        self.assertFalse((self.rawdir / "report.json").exists())

    def test_existing_hardlink_report_is_not_overwritten(self):
        alias = self.reports / "alias.json"
        try:
            os.link(self.input, alias)
        except OSError as exc:
            self.skipTest("Hardlinks unavailable in test filesystem: " + type(exc).__name__)
        before = self.input.read_bytes()
        self.assertEqual(self.cli(alias)[0], 2)
        self.assertEqual(before, self.input.read_bytes())

    def test_exclusive_report_creation_survives_race(self):
        output = self.reports / "race.json"
        checks = 0
        original = v.check_output_path

        def race(path, protected):
            nonlocal checks
            original(path, protected)
            checks += 1
            if checks == 2:
                path.write_text("SYNTHETIC competing writer", encoding="utf-8")

        with patch.object(v, "check_output_path", side_effect=race):
            code, _, _ = self.cli(output)
        self.assertEqual(code, 2)
        self.assertEqual(output.read_text(), "SYNTHETIC competing writer")

    def test_examples_are_capped_but_counts_complete(self):
        self.schema["max_examples_per_category"] = 2
        self.write_input(HEADER + "".join(f"{BASE+i*STEP},100,100,100,100\n" for i in range(7)))
        r = self.audit()["audit"]
        self.assertEqual(r["category_counts"]["FLAT_OBSERVED"], 7)
        self.assertEqual(len(r["examples"]["FLAT_OBSERVED"]), 2)
        self.assertEqual(r["counts"]["longest_contiguous_flat_run_records"], 7)

    def test_real_cli_process_exit_codes_and_fingerprints(self):
        # Runs this stage-B CLI on synthetic data only, never the source project.
        output = self.reports / "process.json"
        result = subprocess.run([sys.executable, "-B", str(ROOT/"validate_data.py"),
                                 "--input", str(self.input), "--schema", str(self.schema_path),
                                 "--manifest", str(self.manifest_path), "--output", str(output)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(output.read_text())
        self.assertEqual(data["input"]["before"], data["input"]["after"])
        self.assertNotIn(str(self.root), output.read_text())
        self.write_input(HEADER+f"{BASE},100,99,98,101\n")
        self.assertEqual(self.cli(self.reports / "invalid.json")[0], 1)
        self.manifest["expected_input"]["sha256"] = "0"*64
        self.save_configs()
        self.assertEqual(self.cli(self.reports / "critical.json")[0], 2)


if __name__ == "__main__":
    unittest.main()
