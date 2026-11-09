import unittest
from artin_cumulative_apprentice import build
class TestApprentice(unittest.TestCase):
 def test_cumulative_no_premature_interpretation(self):
  a={'session_id':'a','speech':[{'start':i,'text':'مفهوم مفهوم تازه'} for i in range(3)]}
  b={'session_id':'b','speech':[{'start':i,'text':'مفهوم مفهوم جدید'} for i in range(3)]}
  result=build([a,b])
  self.assertEqual(len(result['concepts']['مفهوم']['history']),2)
  self.assertEqual(result['concepts']['مفهوم']['meaning'],'OPEN')
  self.assertFalse(result['links'][0]['semantic_continuity_verified'])
  self.assertEqual(result['certified_trading_rules'],[])
 def test_prior_evidence_immutable(self):
  a={'session_id':'a','speech':[{'start':i,'text':'مفهوم مفهوم تازه'} for i in range(3)]}
  b={'session_id':'b','speech':[{'start':i,'text':'مفهوم مفهوم جدید'} for i in range(3)]}
  self.assertEqual(build([a])['concepts']['مفهوم']['history'][0],build([a,b])['concepts']['مفهوم']['history'][0])
 def test_duplicate_rejected(self):
  with self.assertRaises(ValueError):build([{'session_id':'x'},{'session_id':'x'}])
if __name__=='__main__':unittest.main()
