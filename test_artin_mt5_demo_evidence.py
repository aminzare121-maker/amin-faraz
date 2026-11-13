import unittest
from artin_mt5_demo_evidence import evaluate_demo_receipt, DemoEvidenceError


def receipt():
    return {'schema':'artin_mt5_demo_receipt_v1','account_mode':'DEMO',
            'terminal_connected':True,'terminal_id':'SYNTHETIC_TERMINAL',
            'run_id':'SYNTHETIC_RUN','symbol':'XAUUSD',
            'events':[{'ticket':101,'kind':'ENTRY_FILLED','side':'BUY',
                       'lots':'0.01','fill_price':'4000'},
                      {'ticket':101,'kind':'STOP_MODIFIED','new_stop':'4001'},
                      {'ticket':101,'kind':'EXIT_FILLED','fill_price':'4001'}]}


class DemoEvidenceTests(unittest.TestCase):
    def test_synthetic_receipt_validates_but_never_certifies_demo_success(self):
        result=evaluate_demo_receipt(receipt())
        self.assertEqual(result['filled_entries'],1)
        self.assertEqual(result['filled_exits'],1)
        self.assertFalse(result['demo_success_certified'])
        self.assertFalse(result['broker_receipt_independently_authenticated'])

    def test_real_account_is_forbidden(self):
        r=receipt();r['account_mode']='REAL'
        with self.assertRaisesRegex(DemoEvidenceError,'REAL_ACCOUNT_FORBIDDEN'):
            evaluate_demo_receipt(r)

    def test_exit_without_entry_rejected(self):
        r=receipt();r['events']=r['events'][2:]
        with self.assertRaisesRegex(DemoEvidenceError,'DEMO_EXIT_WITHOUT_OPEN_POSITION'):
            evaluate_demo_receipt(r)


if __name__=='__main__':
    unittest.main()
