from hypothesis_engine import update_hypotheses
import unittest

EDGES=[{"source":"inflation_surprise","target":"rate_expectations","sign":1,"weight":0.6,
        "evidence_id":"HYPOTHESIS-ONLY-01","rationale":"Illustrative assumption, not empirical evidence"}]
class HypothesisTests(unittest.TestCase):
    def test_positive_revision(self):
        out=update_hypotheses({},[{"id":"inflation_surprise","delta":1,"confidence":0.5,"verified":True}],EDGES)
        self.assertAlmostEqual(out["pressure_by_target"]["rate_expectations"],0.3)
    def test_negative_news_subtracts(self):
        out=update_hypotheses({"rate_expectations":0.3},
             [{"id":"inflation_surprise","delta":-1,"confidence":0.5,"verified":True}],EDGES)
        self.assertAlmostEqual(out["pressure_by_target"]["rate_expectations"],0.0)
    def test_unverified_ignored(self):
        out=update_hypotheses({},[{"id":"inflation_surprise","delta":1,"confidence":1,"verified":False}],EDGES)
        self.assertEqual(out["pressure_by_target"],{})
    def test_requires_evidence_record(self):
        with self.assertRaises(ValueError):
            update_hypotheses({},[{"id":"inflation_surprise","delta":1,"confidence":1,"verified":True}],
                [{**EDGES[0],"evidence_id":""}])
if __name__=="__main__":
    unittest.main()
