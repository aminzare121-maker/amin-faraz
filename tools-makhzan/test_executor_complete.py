"""Guarantee that new video ingestion cannot masquerade as full ASR/OCR processing."""
import copy
import json
from pathlib import Path
import unittest

from executor import validate

REGISTRY=Path(__file__).with_name("REGISTRY.json")
def registry():return json.loads(REGISTRY.read_text(encoding="utf8"))
def command(action="complete_session",mode="SOURCE_AUDIO_AND_CHAT"):
    return {"schema":"makhzan_tool_execution_request_v1",
       "tool_id":"VIDEO-001","action":action,"job_id":"full_video_real_01",
       "source_url":"https://my.uupload.ir/p/aGgKYdpL",
       "ingest_mode":mode}

class FullSessionRequestValidation(unittest.TestCase):
    def test_full_session_has_distinct_safe_command(self):
        self.assertEqual(validate(command(),registry()),"complete_session")

    def test_extraction_only_source_mode_cannot_be_called_complete(self):
        with self.assertRaisesRegex(ValueError,"Full lesson requires"):
            validate(command(mode="SOURCE_AND_FAST_AUDIO"),registry())

    def test_unknown_video_domain_rejected(self):
        v=command();v["source_url"]="https://evil.example/steal?url=x"
        with self.assertRaisesRegex(ValueError,"user share"):
            validate(v,registry())

    def test_no_authorized_source_video_rejected(self):
        v=command();del v["source_url"]
        with self.assertRaisesRegex(ValueError,"user supplied video"):
            validate(v,registry())

    def test_status_must_never_accept_remote_source_fields(self):
        v=command(action="status")
        v["source_id"]="TEACHER_J2_2026_11_07"
        with self.assertRaisesRegex(ValueError,"Source link cannot"):
            validate(v,registry())

    def test_complete_session_cannot_inject_trading_instruction(self):
        v=command();v["send_order"]="BUY"
        with self.assertRaisesRegex(ValueError,"Unapproved request keys"):
            validate(v,registry())

if __name__=="__main__":unittest.main()
