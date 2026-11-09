from datetime import datetime,timedelta,timezone
import copy
import unittest
from speed_acceptance import evaluate_run,evaluate_repeated,REQUIRED_STAGES

T=datetime(2026,11,8,12,0,0,tzinfo=timezone.utc)
def iso(n):return (T+timedelta(seconds=n)).isoformat()

def fixture(elapsed=175):
    # SYNTHETIC TEST DATA ONLY; not a claim that a film passed.
    return {
      'source_video_sha256':'a'*64,'hardware_id':'gpu-runner-a',
      'asr_model':'large-v3-turbo','ocr_model':'paddleocr','visual_model':'qwen3-vl',
      'actual_original_source_downloaded_this_run':True,'archive_replay_only':False,
      'source_unchanged':True,'production_v12_unchanged':True,'raw_transcripts_unchanged':True,
      'receipt_started_utc':iso(0),'text_archive_committed_utc':iso(elapsed),
      'original_duration_seconds':5400,
      'stages':{name:{'started_utc':iso(i*3),'completed_utc':iso(i*3+7)} for i,name in enumerate(REQUIRED_STAGES)},
      'asr_global_chunks':18,'all_asr_chunks_source_sha_verified':True,'asr_spoken_segments':1900,
      'chat_frames_selected':300,'chat_frames_ocr_attempted':300,'chat_ocr_failed_frames':0,
      'one_second_chat_frames_scanned':5400,
      'board_frames_selected':180,'board_frames_textualized':180,
      'visual_actions_textualized':True,'typed_question_text_retained':True,
      'raw_text_evidence_loss':0,'source_and_text_hashes_verified':True,
      'private_text_archive_committed':True,
      'independent_quality_review':{
        'speech_gold_pass':True,'visual_gold_pass':True,'speaker_and_qa_gold_pass':True,
        'critical_negation_mismatches':0,'teacher_rule_attribution_pass':True,
        'independently_annotated_reference_count':50}}

class StrictGates(unittest.TestCase):
    def test_synthetic_success_is_only_a_test(self):
        self.assertTrue(evaluate_run(fixture())['full_video_under_three_minutes_verified'])
    def test_slow_run_fails(self):
        self.assertIn('WALL_CLOCK_EXCEEDS_180_SECONDS',evaluate_run(fixture(265))['blocking_reasons'])
    def test_source_replay_fails(self):
        x=fixture(); x['actual_original_source_downloaded_this_run']=False;x['archive_replay_only']=True
        self.assertFalse(evaluate_run(x)['full_video_under_three_minutes_verified'])
    def test_missing_board_text_fails(self):
        x=fixture();x['board_frames_textualized']=0
        self.assertIn('BOARD_NOT_ALL_TEXTUALIZED',evaluate_run(x)['blocking_reasons'])
    def test_missing_qa_fails(self):
        x=fixture();x['typed_question_text_retained']=False
        self.assertFalse(evaluate_run(x)['full_video_under_three_minutes_verified'])
    def test_bad_negation_fails(self):
        x=fixture();x['independent_quality_review']['critical_negation_mismatches']=1
        self.assertFalse(evaluate_run(x)['full_video_under_three_minutes_verified'])
    def test_gold_missing_fails(self):
        x=fixture();x['independent_quality_review']=None
        self.assertFalse(evaluate_run(x)['full_video_under_three_minutes_verified'])
    def test_missing_last_stage_fails(self):
        x=fixture();del x['stages']['persist_text_evidence']
        self.assertFalse(evaluate_run(x)['full_video_under_three_minutes_verified'])
    def test_overlapping_stages_permitted(self):
        x=fixture();x['stages']['read_chat']['started_utc']=iso(4)
        self.assertTrue(evaluate_run(x)['full_video_under_three_minutes_verified'])
    def test_incomplete_chat_scan_fails(self):
        x=fixture();x['one_second_chat_frames_scanned']=5300
        self.assertFalse(evaluate_run(x)['full_video_under_three_minutes_verified'])
    def test_chunks_90min_plus_fragment(self):
        x=fixture();x['original_duration_seconds']=5400.01
        self.assertFalse(evaluate_run(x)['full_video_under_three_minutes_verified'])
        x['asr_global_chunks']=19
        self.assertTrue(evaluate_run(x)['full_video_under_three_minutes_verified'])
    def test_three_repeat_requirement(self):
        self.assertFalse(evaluate_repeated([fixture(),fixture()])['approved'])
        self.assertTrue(evaluate_repeated([fixture(),fixture(),fixture()])['approved'])
        self.assertFalse(evaluate_repeated([fixture(),fixture(),fixture(181)])['approved'])
    def test_hardware_drift_fails(self):
        x=fixture();x['hardware_id']='cpu-worker'
        self.assertFalse(evaluate_repeated([fixture(),fixture(),x])['approved'])
    def test_source_mutation_fails(self):
        x=fixture();x['source_unchanged']=False
        self.assertFalse(evaluate_run(x)['full_video_under_three_minutes_verified'])
    def test_raw_rewrite_fails(self):
        x=fixture();x['raw_transcripts_unchanged']=False
        self.assertFalse(evaluate_run(x)['full_video_under_three_minutes_verified'])

if __name__=='__main__': unittest.main()