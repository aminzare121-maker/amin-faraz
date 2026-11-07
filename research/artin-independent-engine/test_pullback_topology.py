import json,unittest
from decimal import Decimal as D
from pathlib import Path
from pullback_topology import PathPoint,PathReference,PullbackTopology

class PullbackTopologyTests(unittest.TestCase):
    def replay(self,case):
        r=case['reference'];ref=PathReference(case['id'],r['anchor_at'],D(r['anchor_price']),r['known_at'],case['source'],
            r.get('second_at'),None if r.get('second_price') is None else D(r['second_price']))
        m=PullbackTopology(case['side'],ref,'TEACHER_SCHEMATIC_VERTEX')
        return m,[m.step(PathPoint(p['at'],D(p['price']),case['source'])) for p in case['points']]
    def cases(self):
        return json.loads((Path(__file__).parent/'docs/S16_SOURCE_PATH_CASES.json').read_text(encoding='utf8'))['cases']
    def test_observed_teacher_schematic_paths_reach_core_without_ready_flags(self):
        for c in self.cases():
            with self.subTest(case=c['id']):
                m,rows=self.replay(c)
                self.assertEqual(rows[-1]['stage'],'CORE_CONFIRMED')
                self.assertFalse(rows[-1]['actionable'])
                self.assertLess(rows[-1]['extreme_at'],rows[-1]['first_known_at'])
                self.assertTrue(rows[-1]['later_exception_assessment_required'])
    def test_source_prefix_before_confirming_vertex_never_enters(self):
        for c in self.cases():
            c={**c,'points':c['points'][:-1]};m,rows=self.replay(c)
            self.assertNotEqual(rows[-1]['stage'],'CORE_CONFIRMED')
    def test_equal_reference_extreme_is_not_beyond_and_no_fixed_bar_quota(self):
        ref=PathReference('S',0,D(100),0,'SYNTHETIC')
        m=PullbackTopology('BUY',ref,'CLOSED_PRICE_PATH',900)
        for at,p in enumerate([99,104,110,105,107,110,106,109]):r=m.step(PathPoint(at*900,D(p),'SYNTHETIC'))
        self.assertEqual(r['stage'],'RETURN_OBSERVED')
        r=m.step(PathPoint(8*900,D(111),'SYNTHETIC'))
        self.assertEqual(r['stage'],'CORE_CONFIRMED')
        self.assertEqual(m.step(PathPoint(9*900,D(112),'SYNTHETIC'))['events'],[])
    def test_growing_peak_not_known_as_pivot_before_observed_return(self):
        m=PullbackTopology('BUY',PathReference('S',0,D(100),0,'SYNTHETIC'),'CLOSED_PRICE_PATH',900)
        for at,p in enumerate([99,104,110,112]):r=m.step(PathPoint(at*900,D(p),'SYNTHETIC'))
        self.assertIsNone(r['first_known_at'])
        r=m.step(PathPoint(3600,D(109),'SYNTHETIC'))
        self.assertEqual(r['first_known_at'],3600)
        self.assertEqual(r['extreme_at'],2700)
    def test_late_start_and_data_gap_do_not_manufacture_a_break(self):
        ref=PathReference('S',0,D(100),0,'SYNTHETIC')
        m=PullbackTopology('BUY',ref,'CLOSED_PRICE_PATH',900)
        self.assertEqual(m.step(PathPoint(0,D(105),'SYNTHETIC'))['stage'],'AWAIT_REFERENCE_SIDE')
        m=PullbackTopology('BUY',ref,'CLOSED_PRICE_PATH',900)
        m.step(PathPoint(0,D(99),'SYNTHETIC'))
        self.assertEqual(m.step(PathPoint(1800,D(105),'SYNTHETIC'))['stage'],'REVIEW_MISSING_PATH')
    def test_reference_anchors_not_future_and_coordinates_not_reordered(self):
        with self.assertRaises(ValueError):PathReference('S',0,D(100),0,'S',1,D(101))
        ref=PathReference('S',1,D(100),1,'S')
        m=PullbackTopology('BUY',ref,'TEACHER_SCHEMATIC_VERTEX')
        self.assertEqual(m.step(PathPoint(0,D(99),'S'))['reason'],'REFERENCE_NOT_KNOWN')
        with self.assertRaises(ValueError):m.step(PathPoint(0,D(99),'S'))

if __name__=='__main__':unittest.main()
