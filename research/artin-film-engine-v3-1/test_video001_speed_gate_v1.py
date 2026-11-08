import unittest
from video001_speed_gate_v1 import select_speed_mode

def sample(seconds):
    return dict(source_video_sha256='a'*64,hardware_id='runner-x',
      asr_model='whisper',ocr_model='paddle',source_evidence_digest='b'*64,
      gold_reference_sha256='c'*64,coverage_complete=True,
      source_evidence_loss=0,original_video_unchanged=True,
      independently_human_reference_checked=True,gold_reference_count=30,
      critical_semantic_mismatches=0,speech_gold_wer=.01,image_gold_cer=.01,
      total_seconds=seconds)

class SpeedGateTests(unittest.TestCase):
    def test_three_repeated_valid_improvements(self):
        x=select_speed_mode([sample(1100),sample(1090),sample(1110)],
                            [sample(880),sample(900),sample(870)])
        self.assertTrue(x['approved'])
    def test_one_trial_not_enough(self):
        self.assertFalse(select_speed_mode([sample(1100)],[sample(800)])['approved'])
    def test_one_slower_trial_blocks(self):
        self.assertFalse(select_speed_mode([sample(1100),sample(1090),sample(1110)],
                            [sample(800),sample(850),sample(1100)])['approved'])
    def test_swapped_source_blocks(self):
        x=[sample(880),sample(890),sample(870)]
        x[0]['source_video_sha256']='d'*64
        self.assertFalse(select_speed_mode([sample(1100)]*3,x)['approved'])
    def test_different_hardware_blocks(self):
        x=[sample(880),sample(890),sample(870)]
        x[0]['hardware_id']='another'
        self.assertFalse(select_speed_mode([sample(1100)]*3,x)['approved'])
    def test_source_loss_blocks(self):
        x=[sample(880),sample(890),sample(870)]
        x[0]['source_evidence_loss']=1
        self.assertFalse(select_speed_mode([sample(1100)]*3,x)['approved'])
    def test_no_independent_reference_blocks(self):
        x=[sample(880),sample(890),sample(870)]
        x[0]['independently_human_reference_checked']=False
        self.assertFalse(select_speed_mode([sample(1100)]*3,x)['approved'])
    def test_negation_error_blocks(self):
        x=[sample(880),sample(890),sample(870)]
        x[0]['critical_semantic_mismatches']=1
        self.assertFalse(select_speed_mode([sample(1100)]*3,x)['approved'])
    def test_worse_speech_quality_blocks(self):
        x=[sample(880),sample(890),sample(870)]
        x[0]['speech_gold_wer']=.4
        self.assertFalse(select_speed_mode([sample(1100)]*3,x)['approved'])
    def test_evidence_hash_mismatch_blocks(self):
        x=[sample(880),sample(890),sample(870)]
        x[0]['source_evidence_digest']='e'*64
        self.assertFalse(select_speed_mode([sample(1100)]*3,x)['approved'])
    def test_small_speed_gain_blocks(self):
        self.assertFalse(select_speed_mode([sample(1100)]*3,[sample(1080)]*3)['approved'])

if __name__=='__main__':unittest.main()
