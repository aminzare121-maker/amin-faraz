"""Regression for variable-length Artin class movies. No real media or trading."""
import unittest
from artin_parallel_asr_worker_v5 import verified_global_source_chunk_count

def manifest(duration, count):
    return {"duration_seconds": duration, "parts": [{"chunk": i} for i in range(1, count+1)]}

class OriginalAudioChunkCoverageTests(unittest.TestCase):
    def test_first_80_minute_film_17_chunks(self):
        self.assertEqual(verified_global_source_chunk_count(manifest(4820.5452, 17)), 17)

    def test_next_85_minute_film_18_chunks_with_same_17_workers(self):
        m = manifest(5157.198367, 18)
        self.assertEqual(verified_global_source_chunk_count(m), 18)
        assignments = [[p["chunk"] for p in m["parts"] if (p["chunk"]-1) % 17 == shard]
                       for shard in range(17)]
        self.assertEqual(assignments[0], [1, 18])
        self.assertEqual(sorted(n for a in assignments for n in a), list(range(1,19)))

    def test_short_movie_has_short_final_chunk(self):
        self.assertEqual(verified_global_source_chunk_count(manifest(721.0, 3)), 3)
        self.assertEqual(verified_global_source_chunk_count(manifest(300.0, 1)), 1)

    def test_reject_missing_18th_part(self):
        with self.assertRaises(ValueError):
            verified_global_source_chunk_count(manifest(5157.198367, 17))

    def test_reject_reordered_or_duplicate_parts(self):
        m = manifest(5157.198367, 18)
        m["parts"][-1]["chunk"] = 17
        with self.assertRaises(ValueError):
            verified_global_source_chunk_count(m)

    def test_reject_invalid_duration(self):
        for duration in [0, -1, float("inf")]:
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                verified_global_source_chunk_count(manifest(duration, 1))

if __name__ == "__main__":
    unittest.main()
