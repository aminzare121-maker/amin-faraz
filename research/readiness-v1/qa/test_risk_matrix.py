import unittest
from decimal import Decimal as D
from risk_matrix import matrix,open_lot,close_lot,CloseDeal,mark_pnl
class MatrixTests(unittest.TestCase):
 def test_three_sizes_and_exact_net(self):self.assertEqual([D(x['floating_before']) for x in matrix()],[D('8.62'),D('86.2'),D('862')])
 def test_partial_conservation(self):self.assertTrue(all(x['net_conserved'] for x in matrix()))
 def test_minimum_lot_not_split_below_grid(self):self.assertEqual(matrix()[0]['remaining_volume'],'0.00')
 def test_duplicate_no_second_realization(self):self.assertTrue(all(not x['duplicate_applied'] for x in matrix()))
 def test_stop_proposal_never_realized(self):self.assertTrue(all(x['stop_proposal_realized']=='0' for x in matrix()))
 def test_unknown_exit_fee_rejected(self):
  with self.assertRaises(ValueError):mark_pnl(open_lot('s','BUY','100','.01','100',confirmed=True),'101','101.3',unpaid_exit_cost=None,slippage_reserve=0)
 def test_unconfirmed_partial_never_realized(self):
  with self.assertRaises(ValueError):close_lot(open_lot('s','BUY','100','.1','100',confirmed=True),CloseDeal('d','.05','101','-.2',False))
 def test_break_even_after_cost(self):self.assertTrue(all(D(x['break_even_net'])==0 for x in matrix()))
 def test_gap_loss_exceeds_initial_five_dollar_move(self):self.assertEqual([D(x['gap_close_at_3994_net']) for x in matrix()],[D('-6.38'),D('-63.8'),D('-638')])
 def test_no_order_authority(self):self.assertTrue(all(not x['real_order_authority'] for x in matrix()))
if __name__=='__main__':unittest.main()
