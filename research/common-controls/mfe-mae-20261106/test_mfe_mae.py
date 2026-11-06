import unittest
from decimal import Decimal as D
from mfe_mae_analysis import first_touch,excursion,net_at,window

def b(o,h,l,c):return dict(open=D(o),high=D(h),low=D(l),close=D(c))
BASE=dict(spread='0',slippage='0',commission_roundtrip_per_lot='0')
TRADE=dict(side='buy',entry='100',initial_stop='95',target='110',lots='.01')

class ExcursionTests(unittest.TestCase):
    def test_same_bar_stop_target_is_ambiguous(self):
        self.assertEqual(first_touch([b('100','112','94','105')],TRADE,BASE),'AMBIGUOUS')

    def test_observed_open_stop_is_known_before_extremes(self):
        self.assertEqual(first_touch([b('94','112','93','105')],TRADE,BASE),'STOP_OPEN')

    def test_exit_bar_extrema_are_only_upper_envelope(self):
        low=excursion([],TRADE,BASE,known_net='10')
        high=excursion([b('100','130','94','105')],TRADE,BASE,known_net='10')
        self.assertEqual(low,(D(10),D(0)))
        self.assertEqual(high,(D(30),D(6)))

    def test_costs_are_not_double_counted(self):
        cost=dict(spread='.3',slippage='.1',commission_roundtrip_per_lot='10')
        self.assertEqual(net_at(D(100),dict(TRADE,entry='100.4'),cost),D('-.6'))
        self.assertEqual(net_at(D(100),dict(TRADE,side='sell',entry='99.9'),cost),D('-.6'))

    def test_short_uses_ask_for_thresholds(self):
        trade=dict(TRADE,side='sell',entry='100',initial_stop='105',target='90')
        cost=dict(BASE,spread='1')
        self.assertEqual(first_touch([b('100','104','95','100')],trade,cost),'STOP')

    def test_missing_and_midnight_windows_are_blocked(self):
        bars={i*900:b('100','101','99','100') for i in range(12)}
        self.assertEqual(window(bars,0,12)[1],'ELIGIBLE')
        del bars[900]
        self.assertEqual(window(bars,0,12)[1],'INCOMPLETE_OR_GAP')
        bars={i*900:b('100','101','99','100') for i in range(84,96)}
        self.assertEqual(window(bars,84*900,12)[1],'RAW_DAY_BOUNDARY')

if __name__=='__main__':unittest.main()
