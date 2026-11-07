import unittest
from decimal import Decimal as D
from dataclasses import FrozenInstanceError
from capital import Instrument, Costs, size_position, account_fill, move_stop, BoxPlan

class CapitalTests(unittest.TestCase):
    def setUp(self):
        self.i=Instrument(D('100'),D('.01'),D('.01'))
        self.c=Costs(D('10'),D('.1'))

    def test_both_sides_round_down_with_costs(self):
        for side,stop in [('BUY',D('99')),('SELL',D('101'))]:
            r=size_position(side,D('100'),stop,D('25'),self.i,self.c)
            self.assertEqual(r['lots'],D('.20'))
            self.assertEqual(r['modeled_loss'],D('24'))
            self.assertLessEqual(r['modeled_loss'],r['risk_budget'])

    def test_minimum_lot_reject_never_shifts_stop(self):
        r=size_position('BUY',D('100'),D('99'),D('1'),self.i,self.c)
        self.assertEqual(r['reason'],'MIN_LOT_EXCEEDS_RISK_BUDGET')

    def test_invalid_stop_and_declared_inputs(self):
        for side,stop in [('BUY',D('101')),('SELL',D('99'))]:
            self.assertEqual(size_position(side,D('100'),stop,D('25'),self.i,self.c)['status'],'REJECT')
        for f in [lambda: Costs(D('-1'),D('0')),lambda: Instrument(D('100'),D('.015'),D('.01')),
                  lambda: size_position('BUY',100.,D('99'),D('25'),self.i,self.c),
                  lambda: Costs(D('NaN'),D('0'))]:
            with self.assertRaises(ValueError): f()

    def test_actual_fills_account_full_fee_once_both_sides(self):
        for side,exit in [('BUY',D('102')),('SELL',D('98'))]:
            r=account_fill(side,D('100'),exit,D('.2'),self.i,D('2'))
            self.assertEqual(r['gross_pnl'],D('40'))
            self.assertEqual(r['net_pnl'],D('38'))

    def test_missing_fill_or_fee_is_unknown(self):
        for entry,exit,fee in [(None,D('102'),D('2')),(D('100'),None,D('2')),(D('100'),D('102'),None)]:
            self.assertIsNone(account_fill('BUY',entry,exit,D('.2'),self.i,fee)['net_pnl'])

    def test_reduce_riskfree_save_both_sides_no_realization(self):
        for side,initial,reduce,free,save in [('BUY','99','99.5','100.2','101'),('SELL','101','100.5','99.8','99')]:
            current=D(initial)
            for label,new in [('reduce',reduce),('riskfree',free),('saveprofit',save)]:
                r=move_stop(label,side,D('100'),D(initial),current,D(new),D('.2'),self.i,self.c)
                self.assertEqual(r['status'],'ACCEPT')
                self.assertEqual(r['lots'],D('.2'))
                self.assertIsNone(r['realized_pnl'])
                if label=='riskfree': self.assertEqual(r['modeled_exit_net'],D('0'))
                current=D(new)

    def test_stop_reversal_and_label_misuse_rejected(self):
        for label,current,new in [('reduce','99.5','99.4'),('reduce','99','100.2'),('riskfree','99','100'),('saveprofit','99','100.1')]:
            self.assertEqual(move_stop(label,'BUY',D('100'),D('99'),D(current),D(new),D('.2'),self.i,self.c)['status'],'REJECT')

    def test_explicit_zero_fee_and_cost_aware_reduce_both_sides(self):
        zero=Costs(D('0'),D('0'))
        self.assertEqual(size_position('BUY',D('100'),D('99'),D('25'),self.i,zero)['lots'],D('.25'))
        for side,initial,beyond in [('BUY','99','100.1'),('SELL','101','99.9')]:
            for stop in [D('100'),D(beyond)]:
                r=move_stop('reduce',side,D('100'),D(initial),D(initial),stop,D('.2'),self.i,self.c)
                self.assertEqual(r['status'],'ACCEPT')
                self.assertLess(r['modeled_exit_net'],D('0'))
            free=move_stop('riskfree',side,D('100'),D(initial),D(initial),D('100'),D('.2'),self.i,zero)
            self.assertEqual(free['status'],'ACCEPT')
            self.assertEqual(account_fill(side,D('100'),D('100'),D('.2'),self.i,D('0'))['net_pnl'],D('0'))

    def test_box_immutable_and_fingerprint_no_implicit_policy_change(self):
        b=BoxPlan('box-a',D('25'),'explicit per-trade structural target',('reduce','riskfree'),True)
        with self.assertRaises(FrozenInstanceError): b.risk_budget=D('30')
        self.assertEqual(b.validate_unchanged(BoxPlan('box-a',D('25.00'),b.target_definition,('reduce','riskfree'),True))['status'],'ACCEPT')
        self.assertEqual(b.validate_unchanged(BoxPlan('box-a',D('30'),b.target_definition,('reduce','riskfree'),True))['status'],'REJECT')
        with self.assertRaises(ValueError): BoxPlan('x',D('25'),'rule',[],True)
        with self.assertRaises(ValueError): BoxPlan('x',D('25'),'rule',(),False)
        with self.assertRaises(ValueError): BoxPlan('x',D('25'),D('103'),(),True)
        with self.assertRaises(ValueError): BoxPlan('x',D('25'),'  ',(),True)
        # Distinct numerical trade targets belong to the caller, not to box policy.
        trades=[{'target':D('103'),'box_fingerprint':b.fingerprint},
                {'target':D('207'),'box_fingerprint':b.fingerprint}]
        self.assertNotEqual(trades[0]['target'],trades[1]['target'])
        self.assertEqual(trades[0]['box_fingerprint'],trades[1]['box_fingerprint'])
        changed=BoxPlan('box-a',D('25'),'different target policy',b.management_choices,True)
        self.assertEqual(b.validate_unchanged(changed)['status'],'REJECT')

if __name__=='__main__': unittest.main()
