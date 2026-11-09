import json
import pathlib
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from artin_restore_six_archived_speech_windows import WINDOWS, ARTIFACTS, REGISTRY_VIDEO_SHA, read_verified_chunk, audio_excerpt, restore

ROOT=pathlib.Path('/mnt/data')

class SourceValidationTests(unittest.TestCase):
    def test_six_proposed_windows_five_distinct_times(self):
        self.assertEqual(len(WINDOWS),6)
        self.assertEqual(len({(w[1],w[2],w[3]) for w in WINDOWS}),5)
    def test_original_20_and_22_registries_pinned(self):
        self.assertEqual(len(REGISTRY_VIDEO_SHA),2)
        self.assertEqual(len(ARTIFACTS),3)
    def test_source_not_a_trade(self):
        from artin_restore_six_archived_speech_windows import digest
        self.assertEqual(digest(b'test'), '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08')

@unittest.skipUnless(all((ROOT/c['asr']).is_file() and (ROOT/c['audio']).is_file() for c in ARTIFACTS.values()), 'private original sources absent in public GitHub runner')
class PrivateOriginalArtifactTests(unittest.TestCase):
    def test_three_audio_chunks_match_source_audio_sha(self):
        for key in ARTIFACTS:
            d=read_verified_chunk(ROOT,key)
            self.assertEqual(d['asr']['source_audio_sha256'],d['audio_sha256'])
            self.assertEqual(d['asr']['source_video_sha256'],REGISTRY_VIDEO_SHA[d['queue_video']])
    def test_six_windows_have_original_audio_and_speech(self):
        with tempfile.TemporaryDirectory() as x:
            report=restore(ROOT,pathlib.Path(x))
            self.assertEqual(report['restored_citation_windows'],6)
            self.assertEqual(report['unique_restored_windows'],5)
            self.assertFalse(report['teacher_speech_independently_heard_and_verified'])
            self.assertFalse(report['financial_backtest_authorized'])
            for w in report['private_review_windows']:
                self.assertTrue(w['recovered_machine_asr_segments'])
                self.assertTrue((pathlib.Path(x)/w['audio_excerpt_file']).is_file())
                self.assertFalse(w['trade_permitted'])
    def test_mutated_sha_fail_closed(self):
        with tempfile.TemporaryDirectory() as x:
            root=pathlib.Path(x)
            cfg=ARTIFACTS['20-15']
            with zipfile.ZipFile(ROOT/cfg['asr']) as zi,zipfile.ZipFile(root/cfg['asr'],'w') as zo:
                for member in zi.namelist():
                    data=zi.read(member)
                    if member.startswith('part_'):
                        j=json.loads(data);j['source_audio_sha256']='0'*64
                        data=json.dumps(j,ensure_ascii=False).encode('utf8')
                    zo.writestr(member,data)
            (root/cfg['audio']).write_bytes((ROOT/cfg['audio']).read_bytes())
            with self.assertRaisesRegex(ValueError,'original WAV bytes'):
                read_verified_chunk(root,'20-15')
    def test_identity_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as x:
            root=pathlib.Path(x)
            cfg=ARTIFACTS['22-16']
            with zipfile.ZipFile(ROOT/cfg['asr']) as zi,zipfile.ZipFile(root/cfg['asr'],'w') as zo:
                for member in zi.namelist():
                    data=zi.read(member)
                    if member.startswith('part_'):
                        j=json.loads(data);j['source_video_sha256']='1'*64
                        data=json.dumps(j,ensure_ascii=False).encode('utf8')
                    zo.writestr(member,data)
            (root/cfg['audio']).write_bytes((ROOT/cfg['audio']).read_bytes())
            with self.assertRaisesRegex(ValueError,'video source identity'):
                read_verified_chunk(root,'22-16')

if __name__=='__main__':unittest.main()