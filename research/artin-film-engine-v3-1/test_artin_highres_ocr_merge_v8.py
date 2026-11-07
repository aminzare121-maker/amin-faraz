"""All 276 high-res chat images must be source-hashed and exactly once assigned."""
import copy
import unittest
from artin_highres_ocr_merge_v8 import merge

SOURCE="a"*64
def pack():
    rows=[{"frame_id":f"frame_{i}","time_seconds":float(i*30),
           "global_chunk":i//10+1,"chat":{"sha256":f"{i+1:064x}"}}
          for i in range(9)]
    index={"schema":"artin_change_selected_chat_v8",
           "source_video_sha256":SOURCE,"rows":rows}
    reports=[]
    for worker in range(4):
        chosen=[r for i,r in enumerate(rows) if i%4==worker]
        reports.append({"schema":"artin_full_original_chat_ocr_v7",
         "source_video_sha256":SOURCE,
         "frames_total":len(rows),"frames_targeted":len(chosen),
         "frames_attempted":len(chosen),"complete":True,
         "partition_index":worker,"partition_count":4,
         "results":[{"frame_id":r["frame_id"],
                     "time_original_video_seconds":r["time_seconds"],
                     "global_chunk":r["global_chunk"],
                     "source_frame_sha256":r["chat"]["sha256"],
                     "state":"OCR_TEXT_CANDIDATES",
                     "source_text_verified":False,
                     "teacher_answer_verified":False,
                     "possible_typed_questions":[]} for r in chosen]})
    return index,reports

class SourceMergeTests(unittest.TestCase):
    def test_complete_partition_merge_preserves_order(self):
        i,r=pack()
        summary,full=merge(i,r)
        self.assertEqual(summary["frames_ocr_completed"],9)
        self.assertEqual([x["frame_id"] for x in full["results"]],
                         [x["frame_id"] for x in i["rows"]])
        self.assertEqual(summary["teacher_answers_verified"],0)
        self.assertFalse(summary["covers_each_video_frame"])

    def test_duplicate_worker_fails(self):
        i,r=pack();r[1]["partition_index"]=0
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            merge(i,r)

    def test_missing_one_source_screenshot_fails(self):
        i,r=pack();r[0]["results"].pop()
        with self.assertRaisesRegex(ValueError,"complete"):
            merge(i,r)

    def test_hash_and_time_substitution_fail(self):
        i,r=pack();r[0]["results"][0]["source_frame_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"source frame"):
            merge(i,r)

    def test_invented_human_certification_fails(self):
        i,r=pack();r[0]["results"][0]["source_text_verified"]=True
        with self.assertRaisesRegex(ValueError,"cannot self-certify"):
            merge(i,r)

    def test_partial_failed_ocr_retained_as_not_ready(self):
        i,r=pack();r[0]["results"][0]["state"]="OCR_FAILED_REVIEW_REQUIRED"
        summary,full=merge(i,r)
        self.assertEqual(summary["frames_ocr_failed"],1)
        self.assertEqual(summary["status"],"REVIEW_REQUIRED")

if __name__=="__main__":
    unittest.main()
