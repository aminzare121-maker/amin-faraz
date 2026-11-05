import ast,copy,pathlib,unittest
from export_readonly import bar_qa,tick_qa
BAR={'time':900,'open':100.,'high':102.,'low':99.,'close':101.}
TICK={'time_msc':900000,'bid':100.,'ask':101.,'flags':6}
class Checks(unittest.TestCase):
    def test_closed(self):self.assertTrue(bar_qa([BAR],900,1800)['structural_pass'])
    def test_unclosed(self):self.assertFalse(bar_qa([BAR],900,1799)['structural_pass'])
    def test_duplicate(self):self.assertFalse(bar_qa([BAR,BAR],900,1800)['structural_pass'])
    def test_nan(self):self.assertFalse(bar_qa([{**BAR,'high':float('nan')}],900,1800)['structural_pass'])
    def test_gap_unknown(self):self.assertEqual(bar_qa([BAR,{**BAR,'time':2700}],900,3600)['gaps'][0]['classification'],'UNKNOWN_SESSION')
    def test_empty_not_success(self):self.assertFalse(bar_qa([],900,1800)['structural_pass'])
    def test_tick_crossed(self):self.assertFalse(tick_qa([{**TICK,'ask':99}],900,1200)['structural_pass'])
    def test_tick_equal_time_retained(self):self.assertTrue(tick_qa([TICK,{**TICK,'bid':100.1}],900,1200)['structural_pass'])
    def test_tick_boundary(self):self.assertFalse(tick_qa([TICK],600,900)['structural_pass'])
    def test_sdk_allowlist(self):
        tree=ast.parse(pathlib.Path('export_readonly.py').read_text())
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='mt5'}
        self.assertLessEqual(calls,{'initialize','terminal_info','account_info','symbol_info','copy_rates_range','copy_ticks_range','last_error','shutdown'})
if __name__=='__main__':unittest.main(verbosity=2)
