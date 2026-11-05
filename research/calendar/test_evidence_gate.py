import unittest
from evidence_gate import assess, deduplicate, parse_number

BASE = {
    "id":"cpi", "title":"CPI", "publisher":"Fixture authority",
    "source_url":"https://example.org/report", "event_at":"2026-11-05T12:00:00Z",
    "observed_at":"2026-11-05T12:10:00Z", "actual":"۳٫۲",
    "forecast":"3.0", "previous":"2.9", "unit":"percent", "period":"2026-10",
    "forecast_asof":"2026-11-04T13:00:00Z", "verified_primary":True
}
NOW = "2026-11-05T12:20:00Z"

class CalendarTest(unittest.TestCase):
    def test_valid_fixture(self):
        r=assess(BASE,NOW)
        self.assertEqual(r["status"],"VERIFIED_CURRENT")
        self.assertAlmostEqual(r["data"]["surprise"], .2)
        self.assertIsNone(r["foresight"]["scenarios"][0]["probability"])
    def test_unverified(self):
        self.assertIn("PRIMARY_SOURCE_UNVERIFIED",assess({**BASE,"verified_primary":False},NOW)["reasons"])
    def test_stale(self):
        self.assertIn("STALE",assess(BASE,"2026-11-06T12:20:00Z")["reasons"])
    def test_missing_actual(self):
        self.assertIn("NO_ACTUAL",assess({**BASE,"actual":None},NOW)["reasons"])
    def test_snapshot_after_event(self):
        self.assertIn("FORECAST_SNAPSHOT_INVALID",assess({**BASE,"forecast_asof":NOW},NOW)["reasons"])
    def test_negative_and_zero(self):
        self.assertEqual(parse_number("−۲٫۰"),-2.0)
        self.assertEqual(parse_number("۰"),0.0)
    def test_revisions_retained(self):
        self.assertEqual(len(deduplicate([BASE,BASE,{**BASE,"revision":1}])),2)
    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            assess(BASE,"2026-11-05T12:20:00")
if __name__=="__main__":
    unittest.main()
