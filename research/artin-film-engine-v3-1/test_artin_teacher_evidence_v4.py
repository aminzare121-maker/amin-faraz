import unittest
from artin_teacher_evidence_v4 import line_identity,linked_qa_candidates,review_rule_eligibility,evaluate_paper_rule
SHA='a'*64

def evidence(t, id, txt, part):return {'id':id,'start':t,'end':t+4,'text':txt,'part_global':part}

class TeacherV4Tests(unittest.TestCase):
 def test_cross_boundary_question_answer_candidate_is_not_verification(self):
  a=evidence(295,'q1','اگر کندل برگشت کند، آیا بخریم؟',1)
  b=evidence(305,'a1','این حالت نیاز به بررسی دارد',2)
  r=linked_qa_candidates(SHA,[b,a])
  self.assertEqual(len(r['question_candidates']),1)
  self.assertEqual(r['question_candidates'][0]['possible_following_utterances'][0]['time'],305)
  self.assertEqual(r['teacher_answers_verified'],0)
  self.assertFalse(r['question_candidates'][0]['can_change_artin_engine'])
 def test_same_source_question_answer_not_assumed_teacher_role(self):
  a=evidence(100,'q','چرا وارد میشویم؟',1)
  b=evidence(108,'a','به خاطر اینکه',1)
  r=linked_qa_candidates(SHA,[a,b]);self.assertEqual(r['question_candidates'][0]['answer_speaker'],'UNKNOWN')
 def test_missing_voice_or_speaker_blocks_rule(self):
  id='u1';rule=self.rule(id);ledger={id:{'confirmed_role':'TEACHER','speaker_human_verified':True,'audio_reviewed_against_original':False,'text_human_corrected_or_verified':True}}
  r=review_rule_eligibility(rule,ledger);self.assertEqual(r['status'],'REVIEW')
  self.assertIn('ORIGINAL_AUDIO_UNREVIEWED',r['issues'])
  self.assertEqual(evaluate_paper_rule(rule,ledger,{'close':101})['paper_decision'],'BLOCKED')
 def test_missing_answer_from_student_question_blocks(self):
  rule=self.rule('t1');rule['question_answer_references']=[{'question_line':'student','teacher_answer_line':'t1'}]
  ledger={'t1':self.teacher(),'student':{'audio_reviewed_against_original':False}}
  self.assertIn('UNVERIFIED_QUESTION_ANSWER',review_rule_eligibility(rule,ledger)['issues'])
 def test_later_correction_blocks(self):
  rule=self.rule('t1');rule['later_correction_unresolved']=True
  self.assertIn('LATER_CORRECTION_NOT_RECONCILED',review_rule_eligibility(rule,{'t1':self.teacher()})['issues'])
 def test_visual_example_must_be_human_verified(self):
  rule=self.rule('t1');rule['requires_visual_example']=True;rule['reference_frames']=['frame_001']
  self.assertIn('CHART_VISUAL_UNVERIFIED',review_rule_eligibility(rule,{'t1':self.teacher()})['issues'])
 def test_paper_only_with_explicit_human_confirmed_evidence(self):
  rule=self.rule('t1');ledger={'t1':self.teacher()}
  self.assertEqual(review_rule_eligibility(rule,ledger)['status'],'PAPER_ONLY')
  a=evaluate_paper_rule(rule,ledger,{'close':101})
  self.assertEqual(a['paper_decision'],'BUY');self.assertIsNone(a['broker_action'])
  self.assertEqual(evaluate_paper_rule(rule,ledger,{'close':99})['paper_decision'],'NO_TRADE')
 def test_unsupported_arbitrary_python_cannot_run(self):
  rule=self.rule('t1');rule['conditions']={'field':'os.system','op':'gt','value':10}
  self.assertIn('CONDITIONS_NOT_EXECUTABLE',review_rule_eligibility(rule,{'t1':self.teacher()})['issues'])
 def rule(self,source):return {'decision':'BUY','conditions':{'field':'close','op':'gt','value':100},
    'source_line_ids':[source],'reviewed_by_user':True,'positive_example_reviewed':True,
    'negative_example_reviewed':True,'later_correction_unresolved':False}
 def teacher(self):return {'confirmed_role':'TEACHER','speaker_human_verified':True,
                           'audio_reviewed_against_original':True,'text_human_corrected_or_verified':True}

if __name__=='__main__':unittest.main()