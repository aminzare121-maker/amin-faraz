import unittest
from decimal import Decimal as D
from raw_geometry import Candle,geometry,extract,touches

def bar(t,o,h,l,c):return Candle(t,t+60,*map(D,(o,h,l,c)))

class RawGeometryTests(unittest.TestCase):
    def up(self):return [bar(0,'10','12','9','11'),bar(60,'11','16','10','15'),bar(120,'15','18','14','17')]

    def test_exact_body_wicks_midpoint_no_inferred_labels(self):
        g=geometry(bar(0,'10','15','8','14'))
        self.assertEqual((g.body,g.upper_wick,g.lower_wick,g.range,g.body_midpoint,g.color),(D(4),D(1),D(2),D(7),D(12),'UP'))
        self.assertEqual(geometry(bar(0,'10','10','10','10')).color,'FLAT')
        self.assertFalse(hasattr(g,'strong'));self.assertFalse(hasattr(g,'doji'))

    def test_fvg_both_directions_bounds_and_known_at(self):
        r=extract(self.up(),at=180,interval_seconds=60)
        f=[x for x in r['candidates'] if x.kind=='FVG_CANDIDATE'][0]
        self.assertEqual((f.low,f.high,f.direction,f.known_at),(D(12),D(14),'UP',180))
        self.assertFalse(f.signal)
        down=[bar(0,'20','21','18','19'),bar(60,'19','20','13','14'),bar(120,'14','16','11','12')]
        f=[x for x in extract(down,at=180,interval_seconds=60)['candidates'] if x.kind=='FVG_CANDIDATE'][0]
        self.assertEqual((f.low,f.high,f.direction),(D(16),D(18),'DOWN'))

    def test_only_after_third_close_and_prefix_stability(self):
        bars=self.up()+[bar(180,'17','22','16','21'),bar(240,'21','1000','1','900')]
        for n in range(1,len(bars)+1):
            at=n*60
            self.assertEqual(extract(bars[:n],at=at,interval_seconds=60),extract(bars,at=at,interval_seconds=60))
        self.assertEqual(extract(bars,at=179,interval_seconds=60)['candidates'],())

    def test_gaps_never_create_three_bar_pattern(self):
        bars=self.up();bars[2]=bar(180,'15','18','14','17')
        r=extract(bars,at=240,interval_seconds=60)
        self.assertEqual(r['gaps'],((120,180),));self.assertEqual(r['candidates'],())

    def test_touching_wicks_no_gap_but_zone_contact_inclusive(self):
        bars=self.up();bars[2]=bar(120,'13','16','12','15')
        self.assertFalse(any(x.kind=='FVG_CANDIDATE' for x in extract(bars,at=180,interval_seconds=60)['candidates']))
        f=[x for x in extract(self.up(),at=180,interval_seconds=60)['candidates'] if x.kind=='FVG_CANDIDATE'][0]
        self.assertTrue(touches(f,D(12)));self.assertTrue(touches(f,D(14)))
        self.assertFalse(touches(f,D('14.01')))

    def test_ohlc_time_order_and_interval_validation(self):
        for factory in [lambda:bar(0,'10','9','8','10'),lambda:bar(0,'NaN','12','9','11'),
                        lambda:Candle(0,0,D(1),D(1),D(1),D(1)),
                        lambda:Candle(True,60,D(1),D(1),D(1),D(1)),
                        lambda:Candle(0,60,1.,D(2),D(1),D(1))]:
            with self.assertRaises(ValueError):factory()
        a=self.up()
        for bars,interval in [(a[::-1],60),([a[0],a[0]],60),(a,15),([a[0],bar(30,'11','13','10','12')],60)]:
            with self.assertRaises(ValueError):extract(bars,at=180,interval_seconds=interval)

if __name__=='__main__':unittest.main()
