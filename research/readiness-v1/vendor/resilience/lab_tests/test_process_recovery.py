"""Real termination/restart of owned lab children; never physical power loss."""
from decimal import Decimal
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "tools" / "lab_crash_worker.py"
STORAGE = ROOT / ".lab-test-storage"
SEED = 41207
PROCESS_EVIDENCE = []


class ProcessRecoveryTests(unittest.TestCase):
    def setUp(self):
        STORAGE.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="kill-restart-", dir=STORAGE)
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.journal = self.folder / "synthetic.journal"
        self.marker = self.folder / "ready.json"

    def command(self, mode, *arguments):
        return [sys.executable, "-I", "-S", "-B", str(WORKER), mode,
                "--journal", str(self.journal), "--seed", str(SEED), *arguments]

    def run_child(self, mode="recover", *arguments):
        completed = subprocess.run(self.command(mode, *arguments), cwd=ROOT,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, timeout=15,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def killed_at(self, cut, occurrence=1, *arguments):
        process = subprocess.Popen(self.command("run", "--marker", str(self.marker),
                                                "--cut", cut, "--occurrence", str(occurrence), *arguments),
                                   cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ready = None
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if self.marker.exists():
                    try:
                        ready = json.loads(self.marker.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        pass
                    else:
                        break
                if process.poll() is not None:
                    _, stderr = process.communicate(timeout=2)
                    self.fail("Lab worker exited before cut point: " + stderr)
                time.sleep(.01)
            self.assertIsNotNone(ready, "Timed out waiting for controlled cut point")
            self.assertIsNone(process.poll(), "Child must still be paused before termination")
            process.kill()  # Only this Popen-owned synthetic worker is terminated.
            process.communicate(timeout=5)
            self.assertIsNotNone(process.returncode)
            ready["owned_child_was_terminated"] = True
            return ready
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def assert_amounts(self, report, *, open_risk, unknown_risk, known_notional,
                       unknown_notional, margin, loss="0", markers=1):
        expected = {"open_risk": open_risk, "unknown_risk": unknown_risk,
                    "known_notional": known_notional, "unknown_notional": unknown_notional,
                    "unfilled_margin": margin, "charged_loss": loss}
        for field, value in expected.items():
            self.assertEqual(Decimal(report[field]), Decimal(value), field)
        self.assertEqual(report["durable_attempt_markers"], markers)
        self.assertEqual(Decimal(report["epoch_limit"]), Decimal("30"))
        self.assertTrue(report["replay_equal"])
        self.assertEqual(report["current_stop_observations"], 0)

    def record(self, scenario, ready, recovered):
        PROCESS_EVIDENCE.append({"scenario": scenario, "seed": SEED,
                                 "fault_model": "actual_owned_child_kill_and_fresh_process_restart",
                                 "hardware_power_loss_tested": False,
                                 "cut_point": ready["cut_point"], "occurrence": ready["occurrence"],
                                 "python": recovered["python"],
                                 "actual_mock_attempts_before_kill": ready["actual_mock_attempts"],
                                 "actual_mock_attempts_after_restart": recovered["actual_mock_attempts"],
                                 "committed_state_before_kill": ready["committed_state"],
                                 "recovered_state": recovered, "pass": True})

    def test_kill_after_reserve_or_before_attempt_commit_retains_unknown_without_dispatch(self):
        for cut in ("after_transition_commit:reserve", "before_send_attempt_commit"):
            with self.subTest(cut=cut):
                if self.journal.exists():
                    # Each scenario uses its own newly-created temporary directory.
                    self.temporary.cleanup()
                    self.setUp()
                ready = self.killed_at(cut)
                self.assertEqual(ready["actual_mock_attempts"], 0)
                recovered = self.run_child()
                self.assert_amounts(recovered, open_risk="0", unknown_risk="27.50",
                                    known_notional="0", unknown_notional="20001.00",
                                    margin="50", markers=0)
                self.assertEqual(recovered["actual_mock_attempts"], 0)
                self.assertIn("NO_RESEND", recovered["resend_rejection"])
                self.record("reserved_or_uncommitted_attempt", ready, recovered)

    def test_kill_before_reserve_commit_cannot_create_an_obligation_or_dispatch(self):
        ready = self.killed_at("before_transition_commit:reserve")
        self.assertEqual(ready["actual_mock_attempts"], 0)
        recovered = self.run_child()
        self.assert_amounts(recovered, open_risk="0", unknown_risk="0",
                            known_notional="0", unknown_notional="0", margin="0", markers=0)
        self.assertEqual(recovered["actual_mock_attempts"], 0)
        self.assertEqual(recovered["phases"], ["RISK_APPROVED"])
        self.record("before_durable_reservation", ready, recovered)

    def test_kill_after_durable_attempt_before_mock_never_resends(self):
        for cut in ("after_send_attempt_commit", "before_mock_call"):
            with self.subTest(cut=cut):
                if self.journal.exists():
                    self.temporary.cleanup()
                    self.setUp()
                ready = self.killed_at(cut)
                self.assertEqual(ready["actual_mock_attempts"], 0)
                recovered = self.run_child()
                self.assert_amounts(recovered, open_risk="0", unknown_risk="27.50",
                                    known_notional="0", unknown_notional="20001.00", margin="50")
                self.assertEqual(recovered["actual_mock_attempts"], 0)
                self.record("durable_attempt_before_external_effect", ready, recovered)

    def test_kill_after_mock_or_before_reply_commit_preserves_unconfirmed_whole_risk(self):
        for cut in ("after_mock_call", "before_reply_commit:apply_event"):
            with self.subTest(cut=cut):
                if self.journal.exists():
                    self.temporary.cleanup()
                    self.setUp()
                ready = self.killed_at(cut)
                self.assertEqual(ready["actual_mock_attempts"], 1)
                recovered = self.run_child()
                self.assert_amounts(recovered, open_risk="0", unknown_risk="27.50",
                                    known_notional="0", unknown_notional="20001.00", margin="50")
                self.assertEqual(recovered["actual_mock_attempts"], 0)
                self.record("external_effect_before_durable_reply", ready, recovered)

    def test_kill_after_fill_or_before_close_commit_preserves_numeric_partial(self):
        for cut, occurrence in (("after_reply_commit:apply_event", 1),
                                 ("before_reply_commit:apply_event", 2)):
            with self.subTest(cut=cut, occurrence=occurrence):
                if self.journal.exists():
                    self.temporary.cleanup()
                    self.setUp()
                ready = self.killed_at(cut, occurrence)
                recovered = self.run_child()
                self.assert_amounts(recovered, open_risk="16.50", unknown_risk="11.00",
                                    known_notional="12000.60", unknown_notional="8000.40", margin="20")
                self.record("durable_partial_before_close", ready, recovered)

    def test_kill_after_close_commit_recovers_one_charge_and_exact_remaining_slices(self):
        ready = self.killed_at("after_reply_commit:apply_event", 2)
        recovered = self.run_child()
        self.assert_amounts(recovered, open_risk="11.00", unknown_risk="11.00",
                            known_notional="8000.40", unknown_notional="8000.40",
                            margin="20", loss="2.10")
        repeated = self.run_child()
        self.assert_amounts(repeated, open_risk="11.00", unknown_risk="11.00",
                            known_notional="8000.40", unknown_notional="8000.40",
                            margin="20", loss="2.10")
        self.assertEqual(recovered["actual_mock_attempts"], 0)
        self.assertEqual(repeated["actual_mock_attempts"], 0)
        self.record("durable_partial_close_charge_once", ready, recovered)

    def test_real_restart_invalidates_a_previously_current_synthetic_stop_observation(self):
        ready = self.killed_at("after_transition_commit:observe_stop", 1, "--observe-stop")
        self.assertEqual(ready["committed_state"]["current_stop_observations"], 1)
        recovered = self.run_child()
        self.assert_amounts(recovered, open_risk="11.00", unknown_risk="11.00",
                            known_notional="8000.40", unknown_notional="8000.40",
                            margin="20", loss="2.10")
        self.assertEqual(recovered["current_stop_observations"], 0)
        self.record("restart_invalidates_previously_current_stop", ready, recovered)

    def test_clean_process_exit_then_duplicate_conflict_and_out_of_order_replay(self):
        completed = self.run_child("run")
        self.assertEqual(completed["actual_mock_attempts"], 1)
        self.assert_amounts(completed, open_risk="11.00", unknown_risk="11.00",
                            known_notional="8000.40", unknown_notional="8000.40",
                            margin="20", loss="2.10")
        recovered = self.run_child("recover", "--exercise-events")
        self.assertEqual(Decimal(recovered["duplicate_close_charged_loss"]), Decimal("2.10"))
        self.assertIn("EVENT_ID_PAYLOAD_CONFLICT", recovered["conflicting_close_rejection"])
        self.assertGreaterEqual(recovered["quarantined_events"], 1)
        self.assertEqual(recovered["actual_mock_attempts"], 0)
        self.assert_amounts(recovered, open_risk="11.00", unknown_risk="11.00",
                            known_notional="8000.40", unknown_notional="8000.40",
                            margin="20", loss="2.10")
        PROCESS_EVIDENCE.append({"scenario": "clean_exit_duplicate_conflict_out_of_order",
                                 "seed": SEED, "fault_model": "fresh_process_file_replay",
                                 "hardware_power_loss_tested": False, "pass": True,
                                 "completed": completed, "recovered_state": recovered})


if __name__ == "__main__":
    unittest.main()
