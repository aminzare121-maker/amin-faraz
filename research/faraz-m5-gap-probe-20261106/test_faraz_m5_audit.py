"""Synthetic-only functional tests. Does not use any actual Eplanet quotes."""
import csv, json, subprocess, sys, tempfile, unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

class FarazM5AuditTests(unittest.TestCase):
    def test_two_named_gaps_synthetic(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            m15,m5=d/'m15.csv',d/'m5.csv'
            rows15,rows5=[],[]
            for j,center in enumerate((datetime(2025,11,28,11),datetime(2026,5,25,22))):
                for i in range(-70,71):
                    t=center+timedelta(minutes=15*i)
                    base=Decimal(4000+100*j)+Decimal(i)/Decimal(10)
                    five=[]
                    for k in range(3):
                        t5=t+timedelta(minutes=5*k)
                        o=base+Decimal(k)/10
                        c=o+Decimal('0.05')
                        five.append({"time":t5.isoformat(),"symbol":"XAUUSD.st","open":str(o),"high":str(c+Decimal('0.2')),
                                     "low":str(o-Decimal('0.2')),"close":str(c),"tick_volume":"25","spread":"10"})
                    if i!=0:
                        rows15.append({"time":t.isoformat(),"symbol":"XAUUSD.st","open":five[0]['open'],
                                       "high":str(max(Decimal(r['high']) for r in five)),
                                       "low":str(min(Decimal(r['low']) for r in five)),
                                       "close":five[2]['close'],"tick_volume":"75","spread":"10"})
                    if i!=0 or j==0: rows5.extend(five)
                    elif j==1:rows5.extend(five[:1])
            fields=['time','symbol','open','high','low','close','tick_volume','spread']
            for p,rows in ((m15,rows15),(m5,rows5)):
                with p.open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            result=subprocess.run([sys.executable,str(Path(__file__).parent/'faraz_m5_audit.py'),
                        '--m15',str(m15),'--m5',str(m5),'--mode','probe','--out',str(d/'out')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            data=json.loads((d/'out/faraz_m5_audit_report.json').read_text())
            self.assertTrue(data['calibration']['verified'])
            self.assertGreaterEqual(data['calibration']['checked'],100)
            self.assertEqual(data['classification_counts'].get('M5_3_OF_3_VERIFIED_SAME_EXPORT'),1)
            self.assertEqual(data['classification_counts'].get('M5_PARTIAL_1_OR_2'),1)
            rec=(d/'out/faraz_m5_recovered_PRIVATE.csv').read_text(encoding='utf-8-sig')
            self.assertIn('2025-11-28T11:00:00',rec)
            self.assertNotIn('2026-05-25T22:00:00',rec)

    def test_empty_data_never_claims_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); headers='time,symbol,open,high,low,close,tick_volume,spread\n'
            for n in ('m15.csv','m5.csv'): (d/n).write_text(headers,encoding='utf-8')
            proc=subprocess.run([sys.executable,str(Path(__file__).parent/'faraz_m5_audit.py'),
                '--m15',str(d/'m15.csv'),'--m5',str(d/'m5.csv'),'--out',str(d/'out')], capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            data=json.loads((d/'out/faraz_m5_audit_report.json').read_text())
            self.assertFalse(data['calibration']['verified'])
            self.assertEqual(data['classification_counts'].get('M5_HISTORY_UNAVAILABLE_OR_MARKET_CLOSED_UNKNOWN'),2)

if __name__=='__main__':unittest.main()