"""DAG scheduler regression: no edits to V12, and no source-media fixtures."""
import threading
import unittest
from video001_source_overlap_scheduler_v1 import overlap_sources

class OverlapSchedulerTests(unittest.TestCase):
    def test_source_evidence_is_preserved(self):
        manifest={"source":"same","parts":17}
        scan={"source":"same","frames":4821}
        result=overlap_sources(lambda:manifest,lambda:scan,
            lambda m:("board",m["parts"]),lambda s:("chat",s["frames"]))
        self.assertEqual(result,(manifest,scan,("board",17),("chat",4821)))

    def test_board_branch_starts_without_waiting_for_scan(self):
        started=threading.Event()
        def scan():
            if not started.wait(.8):
                raise RuntimeError("unnecessary source barrier")
            return 2
        result=overlap_sources(lambda:1,scan,
             lambda _:started.set() or 3,lambda _:4)
        self.assertEqual(result,(1,2,3,4))

    def test_chat_branch_starts_without_waiting_for_audio(self):
        started=threading.Event()
        def audio():
            if not started.wait(.8):
                raise RuntimeError("unnecessary source barrier")
            return 1
        result=overlap_sources(audio,lambda:2,
              lambda _:3,lambda _:started.set() or 4)
        self.assertEqual(result,(1,2,3,4))

    def test_audio_source_failure_blocks_unsafe_board(self):
        happened=[]
        def bad():
            raise ValueError("original source SHA mismatch")
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):
            overlap_sources(bad,lambda:2,
              lambda _:happened.append("board"),lambda _:4)
        self.assertEqual(happened,[])

    def test_chat_stage_failure_is_not_hidden(self):
        def bad(_):
            raise RuntimeError("source image failure")
        with self.assertRaisesRegex(RuntimeError,"source image failure"):
            overlap_sources(lambda:1,lambda:2,lambda _:3,bad)

if __name__=="__main__":
    unittest.main()
