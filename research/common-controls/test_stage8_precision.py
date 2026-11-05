import tempfile,unittest
from pathlib import Path
from decimal import Decimal as D
from unittest.mock import patch
from registry import Registry,digest
from test_selector import bars,controlled_run,CONTEXTS,PROTOCOL
from matched_controls import SPEC

class PrecisionTests(unittest.TestCase):
    def test_same_direction_exact_capital_matches_all_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            bank=Registry(Path(directory)/'bank');data=bars();bank.artifact('fixture',digest(data),{},True)
            # Isolate arithmetic: every control follows the candidate direction.
            with patch('matched_controls.side',return_value='buy'):
                r=controlled_run(bank,data,CONTEXTS,dict(PROTOCOL,matched_controls=SPEC))['result']
            checked=0
            for candidate in r['candidates']:
                for scenario in candidate['validation'].values():
                    capital=D('10000')
                    for row in scenario['rows']:
                        for control in row['matched_controls']:
                            self.assertEqual(D(control['candidate_capital_before']),capital)
                            self.assertEqual(D(control['capital_before']),capital)
                            self.assertNotIn('CAPITAL_PATH_MISMATCH',control['reasons']);checked+=1
                        net=row['trace']['net_with_known_costs']
                        if net is None:break
                        capital+=D(str(net))
            self.assertGreater(checked,100)

    def test_real_difference_still_rejected(self):
        from matched_controls import paired
        from execution_scenarios import replay
        order=dict(side='buy',signal_available=0,lots='.01',contract=100,stop='99',target='100.6')
        kwargs={k:v for k,v in CONTEXTS['base'].items() if k not in ('cost_basis','exit_policy')}
        trace=replay(bars()[:2],order,**kwargs,intrabar_policy='stop_first')
        equities={seed:D('9999.999999999999') for seed in SPEC['seeds']}
        with patch('matched_controls.side',return_value='buy'):
            controls=paired(bars()[:2],order,CONTEXTS['base'],None,'stop_first',trace,D('10000'),equities)
        self.assertTrue(all('CAPITAL_PATH_MISMATCH' in c['reasons'] for c in controls))

if __name__=='__main__':unittest.main()
