"""Scoring must never confuse fallback documentation with real model success."""
import unittest

from real_source_benchmark import BENCHMARK, score_case
from real_model_smoke import has_first_source_citation


class ActualProjectBenchmarkTests(unittest.TestCase):
    def test_positive_requires_actual_model_output(self):
        case = BENCHMARK[0]
        answer = {
            "answer": "طبق سند [1] معامله واقعی مجاز نیست.",
            "model_used": True,
            "needs_human": False,
            "sources": [{"path": "FARAZ_STATUS_AND_HANDOFF_FA.md", "section": 0}],
        }
        self.assertTrue(score_case(case, answer)["passed"])
        self.assertFalse(score_case(case, dict(answer, model_used=False))["passed"])
        self.assertFalse(score_case(case, dict(answer, sources=[]))["passed"])

    def test_correct_source_is_insufficient_without_correct_fact(self):
        case = BENCHMARK[1]
        invalid = {
            "answer": "طبق سند [1] تایم فریم ۵ دقیقه است.",
            "model_used": True, "needs_human": False,
            "sources": [{"path": "FARAZ_STATUS_AND_HANDOFF_FA.md", "section": 0}],
        }
        self.assertFalse(score_case(case, invalid)["passed"])
        self.assertTrue(score_case(case, dict(
            invalid, answer="بر اساس سند [1] کندل ۱۵ دقیقه‌ای لازم است."
        ))["passed"])

    def test_cross_project_query_must_escalate_without_model(self):
        case = BENCHMARK[-1]
        empty = {"answer": "شواهد کافی نیست", "model_used": False,
                 "needs_human": True, "sources": []}
        self.assertTrue(score_case(case, empty)["passed"])
        self.assertFalse(score_case(case, dict(empty, model_used=True))["passed"])
        self.assertFalse(score_case(case, dict(
            empty, sources=[{"path": "INDEX_FA.md", "section": 0}]))["passed"])

    def test_raw_live_model_citation_metric_is_not_false_negative(self):
        self.assertTrue(has_first_source_citation("شماره پورت 8765 است. [1]"))
        self.assertFalse(has_first_source_citation("شماره پورت 8765 است."))
        self.assertFalse(has_first_source_citation("[12]"))

    def test_cases_use_two_real_projects_with_clear_provenance(self):
        self.assertEqual({c["project"] for c in BENCHMARK}, {"faraz", "artin"})
        self.assertEqual(len({c["id"] for c in BENCHMARK}), len(BENCHMARK))
        self.assertTrue(all(c.get("source") or c.get("expected") == "escalation"
                            for c in BENCHMARK))


if __name__ == "__main__":
    unittest.main()
