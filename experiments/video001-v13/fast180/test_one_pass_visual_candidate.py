import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from one_pass_visual_candidate import run

class OnePassVisualTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'source.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','testsrc2=size=640x360:rate=10','-t','91',
            '-c:v','mpeg4','-q:v','6',str(self.source)],check=True)
        self.expected=hashlib.sha256(self.source.read_bytes()).hexdigest()
    def test_one_decode_chat_and_board(self):
        out=self.root/'candidate'
        v=run(self.source,out,self.expected)
        self.assertEqual(v['ffmpeg_full_movie_video_decode_passes'],1)
        self.assertEqual(v['chat_frames_one_second'],91)
        self.assertEqual(v['highres_board_frames'],4)
        self.assertEqual(v['board_timestamps_nominal_seconds'],[15,45,75,90.75])
        self.assertEqual(v['tail_source_seeks'],1)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.expected)
    def test_refuse_wrong_sha(self):
        with self.assertRaises(ValueError):run(self.source,self.root/'out','a'*64)
    def test_refuse_to_overwrite(self):
        target=self.root/'out';target.mkdir();(target/'a.txt').write_text('original')
        with self.assertRaises(FileExistsError):run(self.source,target,self.expected)
        self.assertEqual((target/'a.txt').read_text(),'original')

if __name__=='__main__':unittest.main()