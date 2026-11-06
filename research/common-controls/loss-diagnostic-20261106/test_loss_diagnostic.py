import unittest
from decimal import Decimal as D
from loss_diagnostic import group_stats,distribution,dd,decision,label,UM

def trade(net,reason='STOP'):
    return dict(net_scenario_usd=net,reason=reason)

class DiagnosticTests(unittest.TestCase):
    def test_unresolved_never_becomes_zero_full_net(self):
        r=group_stats([trade('10','TARGET'),trade('-15'),trade(None,'AMBIGUOUS_SL_TP')])
        self.assertIsNone(r['full_net'])
        self.assertEqual(r['known_partial_net'],'-5')
        self.assertEqual(r['resolved'],2)
        self.assertEqual(r['unresolved'],1)
        self.assertEqual(r['profit_factor'],str(D(10)/15))

    def test_no_trade_is_separate_from_unresolved(self):
        r=group_stats([])
        self.assertEqual(r['positions'],0)
        self.assertEqual(r['full_net'],'0')
        self.assertEqual(r['win_rate_resolved'],UM)

    def test_drawdown_is_closed_sequence_not_max_loss(self):
        self.assertEqual(dd(map(D,['10','-4','3','-12','5'])),D(13))

    def test_decimal_quantiles(self):
        r=distribution(list(map(D,['-10','0','2','10'])))
        self.assertEqual(D(r['median']),D(1))
        self.assertEqual(D(r['q25']),D('-2.5'))

    def test_negative_two_costs_stop_current_policy(self):
        m=dict(known_partial_net='-1',fully_resolved_segment_net='-2',profit_factor='.9',unresolved=1)
        self.assertEqual(decision([m,m]),'STOP')

    def test_unknowns_block_candidate(self):
        m=dict(known_partial_net='1',fully_resolved_segment_net='2',profit_factor='1.1',unresolved=1)
        self.assertEqual(decision([m,m]),'RESEARCH_ONLY')
        m=dict(m,unresolved=0)
        self.assertEqual(decision([m,m]),'CANDIDATE_FOR_FRESH_TEST')

    def test_raw_timestamp_has_no_timezone_claim(self):
        self.assertIsNone(label(0).tzinfo)
        self.assertEqual(label(0).isoformat(),'1970-01-01T00:00:00')

if __name__=='__main__':unittest.main()
