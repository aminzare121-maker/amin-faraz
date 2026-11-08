"""Offline regressions for V13 Artin film-3 source coverage.

Run with: python -m unittest discover -s experiments/video001-v13 -p 'test_*.py'
Authentic source/artifact acceptance is separate; no private video is committed.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from film3_evidence_audit import validate_original_parts


def manifest(duration, chunks):
    parts = []
    for i in range(chunks):
        a = i * 300.0
        b = min((i + 1) * 300.0, duration)
        parts.append({"chunk": i + 1, "core_start": a, "core_end": b,
                      "cut_start": max(0, a - 12), "cut_end": min(duration, b + 12)})
    return {"duration_seconds": duration, "parts": parts}


class Film3SourceCoverageTests(unittest.TestCase):
    def test_real_film3_duration_18_chunks(self):
        self.assertEqual(validate_original_parts(manifest(5157.198367, 18)), 18)

    def test_90_minute_exact_boundary(self):
        self.assertEqual(validate_original_parts(manifest(5400.0, 18)), 18)

    def test_90_minute_plus_fraction_needs_19_chunks(self):
        with self.assertRaises(ValueError):
            validate_original_parts(manifest(5400.01, 18))
        self.assertEqual(validate_original_parts(manifest(5400.01, 19)), 19)

    def test_worker_count_does_not_limit_parts(self):
        items = manifest(5157.198367, 18)["parts"]
        assignments = [[p["chunk"] for p in items if (p["chunk"] - 1) % 17 == worker]
                       for worker in range(17)]
        self.assertEqual(assignments[0], [1, 18])
        self.assertEqual(sorted(n for group in assignments for n in group),
                         list(range(1, 19)))

    def test_missing_final_chunk_rejected(self):
        with self.assertRaises(ValueError):
            validate_original_parts(manifest(5157.198367, 17))

    def test_duplicate_or_reordered_chunk_rejected(self):
        data = manifest(5157.198367, 18)
        data["parts"][-1]["chunk"] = 17
        with self.assertRaises(ValueError):
            validate_original_parts(data)

    def test_middle_timeline_gap_rejected(self):
        data = manifest(5157.198367, 18)
        data["parts"][4]["core_start"] += 1.0
        with self.assertRaises(ValueError):
            validate_original_parts(data)

    def test_no_data_or_bogus_duration_rejected(self):
        for d in (0, -1, float("inf")):
            with self.subTest(d=d), self.assertRaises(ValueError):
                validate_original_parts(manifest(d, 1))
        with self.assertRaises(ValueError):
            validate_original_parts({"duration_seconds": 500, "parts": None})


if __name__ == "__main__":
    unittest.main()
