"""Offline demonstration with immutable synthetic M15 records, never broker data."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from artin_mt5_durable_outbox_v5 import run, sha
from test_artin_mt5_incremental_observer_v4 import fixture, source

def generate():
    fixture_lines=fixture()
    with TemporaryDirectory() as tmp:
        folder=Path(tmp); csv=folder/'synthetic_source.csv'; state=folder/'state.json'; outbox=folder/'outbox';
        csv.write_bytes(source(fixture_lines,5)); a=run(csv,state,outbox)
        csv.write_bytes(source(fixture_lines,8)); b=run(csv,state,outbox)
        csv.write_bytes(source(fixture_lines,len(fixture_lines)-1)); c=run(csv,state,outbox)
        d=run(csv,state,outbox)
        receipts=sorted(outbox.glob('batch_*.json'))
        rows=[json.loads(p.read_bytes()) for p in receipts]
        report={
          'schema':'artin_v13_durable_outbox_v5_synthetic_e2e_receipt_v1',
          'synthetic_only':True,
          'source_fixture_sha256':sha(csv.read_bytes()),
          'source_fixture_bars':len(fixture_lines)-1,
          'run_new_bars':[a['new_closed_bars'],b['new_closed_bars'],c['new_closed_bars'],d['new_closed_bars']],
          'receipt_sequences':[x['sequence'] for x in rows],
          'final_checkpoint_rows':json.loads(state.read_bytes())['checkpoint']['rows_seen'],
          'receipt_byte_sha256':[sha(p.read_bytes()) for p in receipts],
          'teacher_semantics_certified':False,
          'orders_sent':0,'real_mt5_compiler_runtime_tested':False,
        }
        assert report['final_checkpoint_rows']==report['source_fixture_bars']
        assert sum(report['run_new_bars'])==report['source_fixture_bars']
        assert len(report['receipt_sequences'])==3
        return report

if __name__=='__main__':
    p=Path(__file__).with_name('ARTIN_V13_V5_SYNTHETIC_E2E_RECEIPT_20261110.json')
    p.write_text(json.dumps(generate(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(p)