"""Validate reusable user video jobs without fetching any real media."""
import unittest
from artin_generic_video_job_v6 import validate_job

BASE={'schema':'artin_private_video_job_v6',
      'job_id':'class-0001','source_url':'https://my.uupload.ir/p/aGgKYdpL',
      'mode':'SOURCE_AND_FAST_AUDIO'}


class GenericJobTests(unittest.TestCase):
    def test_exact_user_share_page_allowed(self):
        j=validate_job(BASE)
        self.assertEqual(j['source_url'],BASE['source_url'])
        self.assertEqual(j['sample_seconds'],30)

    def test_approved_visual_mode_allowed(self):
        j=validate_job({**BASE,'mode':'SOURCE_AUDIO_AND_CHAT','sample_seconds':20})
        self.assertEqual(j['sample_seconds'],20)

    def test_no_server_side_request_forgery_to_localhost(self):
        for u in ('http://127.0.0.1:8080/secrets',
                  'https://my.uupload.ir.evil.com/p/fake',
                  'https://evil.com/p/fake',
                  'https://my.uupload.ir/p/a?redirect=http://localhost',
                  'https://my.uupload.ir@evil.com/p/fake'):
            with self.subTest(u=u), self.assertRaises(ValueError):
                validate_job({**BASE,'source_url':u})

    def test_no_magic_execute_python_mode(self):
        with self.assertRaisesRegex(ValueError,'safe evidence-only'):
            validate_job({**BASE,'mode':'RUN_REAL_TRADE'})

    def test_no_unapproved_workflow_arguments(self):
        with self.assertRaisesRegex(ValueError,'unapproved'):
            validate_job({**BASE,'source_path':'../../config.py'})

    def test_hash_must_be_sha256(self):
        with self.assertRaisesRegex(ValueError,'SHA256'):
            validate_job({**BASE,'expected_sha256':'some-sha'})

    def test_id_must_be_safe(self):
        with self.assertRaisesRegex(ValueError,'job ID'):
            validate_job({**BASE,'job_id':'../../unsafe'})


if __name__=='__main__':unittest.main()
