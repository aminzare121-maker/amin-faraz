import tempfile,unittest
from pathlib import Path
import pandas as pd
from indicator_pair_shadow import audit
class IndicatorPairTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name)
        self.t=self.dir/'t.csv';self.i=self.dir/'i.csv'
        pd.DataFrame({'entry_utc':['2026-07-01T10:15Z','2026-07-01T10:30Z'],
                      'side':[1,-1],'pnl_usd':[10,-6]}).to_csv(self.t,index=False)
        self.base=pd.DataFrame({'bar_open_utc':['2026-07-01T10:00Z','2026-07-01T10:15Z'],
          'indicator_1':[1,-1],'indicator_2':[1,-1],
          'indicator_1_ready_utc':['2026-07-01T10:15Z','2026-07-01T10:30Z'],
          'indicator_2_ready_utc':['2026-07-01T10:15Z','2026-07-01T10:30Z']})
        self.base.to_csv(self.i,index=False)
    def tearDown(self):self.tmp.cleanup()
    def test_never_veto_trade_or_change_pnl(self):
        a=audit(self.t,self.i,self.dir/'out')
        self.assertEqual(a['n_context_ready'],2)
        self.assertEqual(a['n_preserved'],2)
        self.assertEqual(a['shadow_net_pnl'],4)
        self.assertTrue(a['unchanged'])
    def test_cannot_see_indicators_before_close(self):
        self.base.loc[0,'indicator_1_ready_utc']='2026-07-01T10:10Z'
        self.base.to_csv(self.i,index=False)
        with self.assertRaisesRegex(ValueError,'future-data'):audit(self.t,self.i,self.dir/'out')
    def test_ignore_indicator_arriving_after_entry(self):
        self.base.loc[0,'indicator_1_ready_utc']='2026-07-01T10:16Z'
        self.base.to_csv(self.i,index=False)
        self.assertEqual(audit(self.t,self.i,self.dir/'out')['n_context_ready'],1)
    def test_bad_indicator_value_fails(self):
        self.base.loc[0,'indicator_2']=2
        self.base.to_csv(self.i,index=False)
        with self.assertRaisesRegex(ValueError,'-1/0/'):audit(self.t,self.i,self.dir/'out')
if __name__=='__main__':unittest.main()
