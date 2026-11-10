"""Regression tests: malformed rule kinds must fail closed, never crash."""
import unittest

from artin_semantic_gate import audit


class InvalidKindTests(unittest.TestCase):
    def test_unhashable_kind_does_not_crash(self):
        for kind in ([], {}, ["entry"], {"type": "entry"}):
            with self.subTest(kind=kind):
                result = audit({"sessions": [{"session": 1, "rules": [
                    {"kind": kind, "status": "VERIFIED"}
                ]}]})
                self.assertFalse(result["complete"])
                self.assertEqual(result["sessions"][0]["status"], "UNVERIFIED")
                self.assertEqual(result["sessions"][0]["verified_rules"], 0)
                self.assertTrue(any("unsupported VERIFIED" in e for e in result["errors"]))

    def test_valid_kind_with_no_evidence_stays_unverified(self):
        result = audit({"sessions": [{"session": 1, "rules": [
            {"kind": "entry", "status": "VERIFIED"}
        ]}]})
        self.assertFalse(result["complete"])
        self.assertEqual(result["sessions"][0]["verified_rules"], 0)


if __name__ == "__main__":
    unittest.main()
