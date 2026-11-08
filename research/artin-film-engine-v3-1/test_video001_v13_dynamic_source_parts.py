"""V13 regression: preserve 17/18+ five-minute source parts while using <=17 ASR workers.
These are synthetic manifests. No claim of actual ASR or teacher understanding.
"""
import unittest
from artin_parallel_asr_worker_v5 import verified_global_source_chunk_count


def sample(duration, count):
    return {'duration_seconds': duration,
            'parts': [{'chunk': i} for i in range(1, count + 1)]}


class RealSourceCoverageContract(unittest.TestCase):
    def test_80min_and_85min(self):
        self.assertEqual(verified_global_source_chunk_count(sample(4820.5452, 17)), 17)
        self.assertEqual(verified_global_source_chunk_count(sample(5157.198367, 18)), 18)

    def test_90min_exact_and_slightly_over(self):
        self.assertEqual(verified_global_source_chunk_count(sample(5400.0, 18)), 18)
        self.assertEqual(verified_global_source_chunk_count(sample(5400.01, 19)), 19)

    def test_18_parts_over_17_workers(self):
        parts = sample(5157.198367, 18)['parts']
        assigned = [[p['chunk'] for p in parts if (p['chunk']-1) % 17 == worker]
                    for worker in range(17)]
        self.assertEqual(assigned[0], [1, 18])
        self.assertEqual(sorted(n for each in assigned for n in each),
                         list(range(1, 19)))

    def test_short_movie_and_last_partial_part(self):
        self.assertEqual(verified_global_source_chunk_count(sample(1, 1)), 1)
        self.assertEqual(verified_global_source_chunk_count(sample(721, 3)), 3)

    def test_missing_or_duplicate_parts_rejected(self):
        with self.assertRaises(ValueError):
            verified_global_source_chunk_count(sample(5157.198367, 17))
        bad = sample(5157.198367, 18)
        bad['parts'][-1]['chunk'] = 17
        with self.assertRaises(ValueError):
            verified_global_source_chunk_count(bad)

    def test_invalid_duration_or_parts_rejected(self):
        for duration in (0, -1, float('inf'), 'invalid'):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                verified_global_source_chunk_count(sample(duration, 1))
        with self.assertRaises(ValueError):
            verified_global_source_chunk_count({'duration_seconds': 600, 'parts': None})


if __name__ == '__main__':
    unittest.main()
