"""Synthetic-only tests for Artin source-bound M15 shadow ledger."""
import csv
import gzip
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from paper_m15_shadow import replay, evaluate_trade, validate_output_path, write_json_atomic


class M15PaperShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.csv=self.root/'M15.csv'
        self.trace=self.root/'PRIVATE_raw_decisions.jsonl.gz'
        self.summary=self.root/'SUMMARY.json'
        self.specs=self.root/'specs.json'

    def make(self,bars,signal=900,status='ELIGIBLE',stop='9',target='13'):
        with self.csv.open('w',newline='',encoding='utf8') as f:
            w=csv.writer(f);w.writerow(['time_raw_epoch','open','high','low','close'])
            w.writerows(bars)
        with gzip.open(self.trace,'wt',encoding='utf8') as f:
            for bar in bars:
                t=int(bar[0])
                f.write(json.dumps({'bar_opened_at':t,'at':t+900,'decisions':
                    ([{'status':status,'side':'BUY','rule_id':'BREAK_STRONG'}] if t+900==signal else [])})+'\n')
        self.summary.write_text(json.dumps({'csv_sha256':hashlib.sha256(self.csv.read_bytes()).hexdigest(),
                                'interval_seconds':900,'observed_bars':len(bars)}))
        self.specs.write_text(json.dumps({'specs':[{'known_at':signal,'signal_at':signal,'side':'BUY',
            'rule_id':'BREAK_STRONG','source':'session21:200','stop_source':'session25:300',
            'target_source':'session26:100','stop':stop,'target':target}]}),encoding='utf8')

    def run_shadow(self):
        return replay(self.csv,self.trace,self.summary,self.specs,'100','0.01','1')

    def test_target_next_bar_after_signal_only(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        r=self.run_shadow()
        self.assertEqual(r['completed_paper_trades'],1)
        self.assertEqual(r['paper_net_usd_closed_only'],'2.99')
        self.assertEqual(r['trades'][0]['exit_reason'],'TARGET')
        self.assertEqual(r['orders_sent'],0)

    def test_both_targets_conservatively_stop_and_annotates_ambiguity(self):
        self.make([(0,10,11,9,10),(900,10,14,8,11)])
        r=self.run_shadow()
        self.assertEqual(r['trades'][0]['exit_reason'],'STOP')
        self.assertTrue(r['trades'][0]['ambiguous_same_bar'])
        self.assertEqual(r['paper_net_usd_closed_only'],'-1.01')

    def test_requires_immediate_next_bar(self):
        self.make([(0,10,11,9,10),(1800,10,14,9.5,13)])
        r=self.run_shadow()
        self.assertEqual(r['completed_paper_trades'],0)
        self.assertEqual(r['blockers']['MISSING_IMMEDIATE_NEXT_M15_BAR'],1)

    def test_source_missing_blocks_spec(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        s=json.loads(self.specs.read_text());s['specs'][0].pop('stop_source')
        self.specs.write_text(json.dumps(s))
        with self.assertRaises(ValueError):self.run_shadow()

    def test_unready_not_promoted_to_trade(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)],status='REVIEW')
        r=self.run_shadow()
        self.assertEqual(r['completed_paper_trades'],0)
        self.assertEqual(r['eligible_decisions'],0)
        self.assertEqual(len(r['orphan_specs']),1)

    def test_sell_stop_or_target(self):
        bars=[{'t':900,'o':Decimal(10),'h':Decimal('10.1'),'l':Decimal(7),'c':Decimal(8)}]
        key=(900,'SELL','REVERSAL_CLASSIC')
        s={'stop':'11','target':'8','source':'x','stop_source':'y','target_source':'z'}
        x=evaluate_trade(bars,0,key,s,Decimal(100),Decimal('.01'),Decimal(1))
        self.assertEqual(x['net_usd'],'1.99')
        self.assertEqual(x['exit_reason'],'TARGET')

    def test_gap_inside_open_trade_unresolved(self):
        self.make([(0,10,11,9,10),(900,10,11,9.5,10),(2700,10,14,9,12)])
        r=self.run_shadow()
        self.assertEqual(r['trades'][0]['state'],'UNRESOLVED')
        self.assertEqual(r['blockers']['GAP_DURING_OPEN_TRADE'],1)

    def test_summary_wrong_csv_is_rejected(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        s=json.loads(self.summary.read_text());s['csv_sha256']='0'*64
        self.summary.write_text(json.dumps(s))
        with self.assertRaises(ValueError):self.run_shadow()

    def test_future_defined_stop_is_rejected(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        s=json.loads(self.specs.read_text());s['specs'][0]['known_at']=1800
        self.specs.write_text(json.dumps(s))
        with self.assertRaises(ValueError):self.run_shadow()

    def test_invalid_ohlc_rejected(self):
        self.make([(0,10,9,9,10),(900,10,14,9.5,13)])
        with self.assertRaises(ValueError):self.run_shadow()

    def test_no_spec_is_visible_blocker(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        self.specs.write_text('{"specs":[]}')
        r=self.run_shadow()
        self.assertEqual(r['blockers']['MISSING_TEACHER_SOURCED_STOP_TARGET'],1)


    def test_placeholder_source_is_rejected_before_any_trade(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        s = json.loads(self.specs.read_text())
        s['specs'][0]['source'] = 'VERIFY_LESSON_TIMESTAMP_ENTRY'
        self.specs.write_text(json.dumps(s))
        with self.assertRaisesRegex(ValueError, 'placeholder source reference'):
            self.run_shadow()

    def test_placeholder_stop_source_is_rejected(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        s = json.loads(self.specs.read_text())
        s['specs'][0]['stop_source'] = 'TODO: actual lesson screenshot'
        self.specs.write_text(json.dumps(s))
        with self.assertRaisesRegex(ValueError, 'placeholder source reference'):
            self.run_shadow()

    def test_nonstring_source_reference_is_rejected(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        s = json.loads(self.specs.read_text())
        s['specs'][0]['target_source'] = 123
        self.specs.write_text(json.dumps(s))
        with self.assertRaisesRegex(ValueError, 'invalid source reference'):
            self.run_shadow()

    def test_valid_looking_references_are_still_not_teacher_verified(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        s = json.loads(self.specs.read_text())
        s['specs'][0]['source'] = 'session999:1'
        self.specs.write_text(json.dumps(s))
        r = self.run_shadow()
        self.assertEqual(r['completed_paper_trades'], 1)
        self.assertFalse(r['teacher_method_verified'])
        self.assertFalse(r['declared_source_refs_independently_verified'])
        self.assertEqual(r['teacher_verified_trade_count'], 0)
        self.assertEqual(r['trades'][0]['source_evidence_status'], 'DECLARED_UNVERIFIED')
        self.assertFalse(r['trades'][0]['teacher_rule_verified'])

    def test_hardlink_output_to_input_is_rejected_without_damage(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        out = self.root/'shadow.json'
        before = self.summary.read_bytes()
        os.link(self.summary, out)
        with self.assertRaisesRegex(ValueError, 'output may not overwrite'):
            validate_output_path(out, (self.csv, self.summary, self.trace, self.specs))
        self.assertEqual(self.summary.read_bytes(), before)

    def test_safe_atomic_writer_roundtrips_json(self):
        out = self.root/'shadow.json'
        write_json_atomic(out, {'state':'DECLARED_UNVERIFIED','text':'مدرس'})
        raw = out.read_bytes()
        self.assertTrue(raw.endswith(b'\n'))
        self.assertEqual(json.loads(raw.decode('utf8'))['text'], 'مدرس')


    def test_strict_teacher_audit_blocks_profitable_synthetic_fill(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        r = replay(self.csv,self.trace,self.summary,self.specs,'100','0.01','1',
                   strict_teacher_audit=True)
        self.assertEqual(r['raw_eligible_decisions'],1)
        self.assertEqual(r['eligible_decisions'],0)
        self.assertEqual(r['completed_paper_trades'],0)
        self.assertIsNone(r['paper_net_usd_closed_only'])
        self.assertEqual(r['trades'][0]['state'],'REVIEW')
        self.assertEqual(r['trades'][0]['reason'],'RAW_TRACE_PROVENANCE_FIELDS_MISSING')
        self.assertEqual(r['teacher_gate_summary']['reviewed_candidates'],1)
        self.assertEqual(r['orders_sent'],0)
        self.assertFalse(r['teacher_method_verified'])

    def test_strict_teacher_audit_does_not_mislabel_valid_specs_as_orphan(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        r = replay(self.csv,self.trace,self.summary,self.specs,'100','0.01','1',
                   strict_teacher_audit=True)
        self.assertEqual(r['orphan_specs'],[])
        self.assertEqual(r['outcomes_by_state'],{'REVIEW':1})
        self.assertEqual(r['blockers']['RAW_TRACE_PROVENANCE_FIELDS_MISSING'],1)



    def test_dialogue_index_unanswered_teacher_questions_blocks_shadow(self):
        from classroom_rule_review import audit_dialogue_records, SCHEMA
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        rindex=audit_dialogue_records(dict(schema=SCHEMA,records=[]))
        index_path=self.root/'PRIVATE_classroom_index.json'
        index_path.write_text(json.dumps(rindex),encoding='utf8')
        r=replay(self.csv,self.trace,self.summary,self.specs,'100','0.01','1',
                 strict_teacher_audit=True,classroom_index_path=index_path)
        self.assertEqual(r['raw_eligible_decisions'],1)
        self.assertEqual(r['completed_paper_trades'],0)
        self.assertEqual(r['trades'][0]['reason'],'DIALOGUE_NO_DIALOGUE_REVIEW_RECORDS')
        self.assertIsNone(r['paper_net_usd_closed_only'])
        self.assertEqual(len(r['classroom_index_sha256']),64)

    def test_dialogue_index_cannot_be_used_in_diagnostic_profit_mode(self):
        self.make([(0,10,11,9,10),(900,10,14,9.5,13)])
        index_path=self.root/'PRIVATE_classroom_index.json'
        index_path.write_text('{"schema":"artin_classroom_rule_index_v1","rules":{}}')
        with self.assertRaisesRegex(ValueError,'requires strict teacher audit'):
            replay(self.csv,self.trace,self.summary,self.specs,'100','0.01','1',
                   strict_teacher_audit=False,classroom_index_path=index_path)



if __name__=='__main__':
    unittest.main()
