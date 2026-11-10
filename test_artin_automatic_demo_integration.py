"""Mock SDK tests only. NOT a real ePlanet/MetaEditor result."""
import json,sys,tempfile,types,unittest,hashlib
from pathlib import Path
from unittest.mock import patch,Mock
from types import SimpleNamespace
from artin_mt5_demo_automatic import main,BotBlocked,verify_teacher_pdf_sources,SOURCE_PDF_HASHES

class DemoSdkContractTests(unittest.TestCase):
    def mock_sdk(self,trade_mode=0):
        m=types.ModuleType('MetaTrader5');m.ACCOUNT_TRADE_MODE_DEMO=0;m.ACCOUNT_TRADE_MODE_REAL=2
        m.ORDER_TYPE_BUY=0;m.ORDER_TYPE_SELL=1;m.ORDER_FILLING_FOK=0;m.ORDER_FILLING_IOC=1
        m.ORDER_TIME_GTC=0;m.TRADE_ACTION_DEAL=1;m.TRADE_ACTION_SLTP=6;m.TRADE_RETCODE_DONE=10009
        m.TIMEFRAME_M15=15;m.DEAL_ENTRY_OUT=1;m.DEAL_ENTRY_OUT_BY=3;m.DEAL_REASON_TP=5;m.DEAL_REASON_SL=4
        m.initialize=Mock(return_value=True);m.shutdown=Mock()
        m.account_info=Mock(return_value=SimpleNamespace(trade_mode=trade_mode,server='ePlanet-MT5',
                     company='ePlanet Ltd',login=112233,balance=1000))
        m.terminal_info=Mock(return_value=SimpleNamespace(data_path='/tmp/fake-terminal',connected=True))
        m.positions_get=Mock(return_value=[]);m.history_deals_get=Mock(return_value=[])
        def candle(t,o,h,l,c):return {'time':t,'open':o,'high':h,'low':l,'close':c}
        raw=[candle(0,100,101,99,100),candle(900,100,105,100,104),
             candle(1800,107,110,106,109),candle(2700,105,106,101,104),
             candle(3600,104,108,104,107)]
        def rates(symbol,tf,pos,count):return [candle(4500,107,108,106,107)] if pos==0 else raw[:count]
        m.copy_rates_from_pos=Mock(side_effect=rates)
        m.symbol_info=Mock(return_value=SimpleNamespace(volume_step=0.01,volume_min=0.01,volume_max=10,
             trade_tick_size=0.01,trade_stops_level=0,point=0.01,filling_mode=1))
        m.symbol_info_tick=Mock(return_value=SimpleNamespace(bid=107,ask=107.05,time=4512))
        m.order_calc_profit=Mock(return_value=-605)
        m.order_check=Mock(return_value=SimpleNamespace(retcode=0))
        m.order_send=Mock(return_value=SimpleNamespace(retcode=10009,order=123,deal=456,price=107.05))
        return m
    def args(self,root):
        winrate=root/'winrate.json';winrate.write_text(json.dumps({
          'schema':'fxm_winrate_evidence_v1','audited':True,'source':'PRIVATE_AUDIT',
          'wins':50,'losses':50}),encoding='utf8')
        return ['--terminal','/tmp/fake-terminal.exe','--expected-data','/tmp/fake-terminal',
          '--state',str(root/'state.json'),'--report',str(root/'report.jsonl'),
          '--history-bars','10','--reference-balance','1000',
          '--winrate-evidence-file',str(winrate),'--broker-day-offset-minutes','0',
          '--mode','THREE_TP','--enable-demo-orders','--once']
    def test_mock_demo_entry_exactly_once_persistent_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m=self.mock_sdk()
            with patch.dict(sys.modules,{'MetaTrader5':m}), patch('artin_mt5_demo_automatic.verify_teacher_pdf_sources',return_value=True):
                main(self.args(root));main(self.args(root))
            self.assertEqual(m.order_send.call_count,1)
            d=json.loads((root/'state.json').read_text())
            self.assertEqual(d['last_bar'],3600)
            self.assertEqual(d['plan']['ticket'],123)
            self.assertEqual(d['plan']['tp_levels'],['111.890','114.915','117.940'])
            self.assertTrue(d['plan']['broker_fill_verified'])
            report=(root/'report.jsonl').read_text()
            self.assertIn('EPLANET_DEMO_ORDER_ACCEPTED_BROKER_RESULT',report)
            self.assertIn('NO_NEW_CLOSED_M15',report)
    def test_never_order_on_real_account_even_with_enable(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m=self.mock_sdk(trade_mode=2)
            with patch.dict(sys.modules,{'MetaTrader5':m}), patch('artin_mt5_demo_automatic.verify_teacher_pdf_sources',return_value=True):
                with self.assertRaisesRegex(BotBlocked,'STRICT_EPLANET_DEMO_REQUIRED'):
                    main(self.args(root))
            m.order_send.assert_not_called()
    def test_teacher_pdf_sha_enforced_without_publishing_teacher_pdfs(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);p=folder/'original-private.pdf';p.write_bytes(b'test-hash-gate-only')
            wanted=hashlib.sha256(p.read_bytes()).hexdigest()
            with patch.dict(SOURCE_PDF_HASHES,{'original-private.pdf':wanted},clear=True):
                self.assertTrue(verify_teacher_pdf_sources(folder))
                p.write_bytes(b'changed')
                with self.assertRaisesRegex(BotBlocked,'TEACHER_ORIGINAL_PDF_MISSING_OR_MODIFIED'):
                    verify_teacher_pdf_sources(folder)
    def test_read_only_mode_has_signal_but_no_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m=self.mock_sdk()
            args=self.args(root)
            args.remove('--enable-demo-orders')
            with patch.dict(sys.modules,{'MetaTrader5':m}):main(args)
            m.order_send.assert_not_called();m.order_check.assert_not_called()
            self.assertIn('OBSERVED_PDF_CANDIDATE_ORDERS_DISABLED',(root/'report.jsonl').read_text())

if __name__=='__main__':unittest.main()