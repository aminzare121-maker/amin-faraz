import unittest
from datetime import datetime, timedelta, timezone
from artin_real_cycle_receipt_gate import STAGES, REQUIRED_EVIDENCE, audit

class CycleReceiptTests(unittest.TestCase):
    def receipt(self, seconds=179):
        start = datetime(2026, 11, 10, tzinfo=timezone.utc)
        offsets = [0, 10, 20, 50, 80, 100, seconds]
        return {"video_id": "real-film-id",
                "timestamps": {k: (start + timedelta(seconds=v)).isoformat() for k,v in zip(STAGES, offsets)},
                "evidence": {k: True for k in REQUIRED_EVIDENCE}}

    def test_strict_under_180(self):
        self.assertTrue(audit(self.receipt(179))["passed"])
        self.assertFalse(audit(self.receipt(180))["passed"])

    def test_missing_semantics_fails(self):
        r = self.receipt()
        r["evidence"]["teacher_semantics_verified"] = False
        self.assertFalse(audit(r)["passed"])

    def test_missing_handoff_fails(self):
        r = self.receipt()
        del r["timestamps"]["next_handoff_complete"]
        self.assertFalse(audit(r)["passed"])

    def test_naive_timestamps_fail(self):
        r = self.receipt()
        r["timestamps"]["received"] = "2026-11-10T00:00:00"
        self.assertFalse(audit(r)["passed"])

    def test_out_of_order_fails(self):
        r = self.receipt()
        r["timestamps"]["speech_complete"] = "2026-11-09T00:00:00+00:00"
        self.assertFalse(audit(r)["passed"])

if __name__ == "__main__":
    unittest.main()
