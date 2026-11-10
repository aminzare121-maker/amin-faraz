"""Recovery simulation on actual captured bars, distinct from a network outage."""
import hashlib,json,sys,tempfile
from pathlib import Path
from candle_archive import CandleArchive,verify_archive,IntegrityError
BASE=Path(__file__).resolve().parents[1]
def main():
    snapshot=BASE/'runtime/capture-01.json';raw=snapshot.read_bytes();doc=json.loads(raw)
    bars=doc['bars'];fence=doc['current_bar_open_native']
    if len(bars)<20:raise ValueError('INSUFFICIENT_REAL_CAPTURE')
    missing=bars[10:13];partial=bars[:10]+bars[13:]
    with tempfile.TemporaryDirectory(prefix='artin-independent-recovery-') as folder:
        archive=CandleArchive(folder)
        first=archive.ingest(partial,current_bar_open=fence)
        resumed=CandleArchive(folder).ingest(bars,current_bar_open=fence)
        if resumed['added']!=3 or resumed['backfilled']!=3 or resumed['duplicates']!=len(bars)-3:raise ValueError('BACKFILL_FAILED')
        if len(archive.read_bars())!=len(bars):raise ValueError('REPLAY_COUNT_MISMATCH')
        head=archive.verify();path=Path(folder)/'candles.jsonl';lines=path.read_bytes().splitlines(keepends=True)
        path.write_bytes(b''.join(lines[:-1]))
        try:verify_archive(folder,head)
        except IntegrityError:tail_detected=True
        else:raise ValueError('TAIL_DELETION_UNDETECTED')
    out=dict(schema='codex_captured_bars_recovery_v1',snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        captured_bar_count=len(bars),deliberately_omitted_count=len(missing),backfilled_count=resumed['backfilled'],
        duplicates_not_rewritten=resumed['duplicates'],known_broker_gaps_preserved=resumed['gaps'],
        before_gap_count=len(first['gaps']),after_gap_count=len(resumed['gaps']),
        source_native_time_preserved=True,tail_deletion_detected=tail_detected,
        physical_network_outage_tested=False,source='ACTUAL_DEMO_CAPTURE_WITH_CONTROLLED_LOCAL_OMISSIONS',
        terminal_or_account_changed=False,orders_submitted=0)
    (BASE/'reports/captured-recovery.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(actual_source_bars=len(bars),controlled_backfill=3,tail_deletion_detected=True,physical_network_outage_tested=False)))
if __name__=='__main__':main()
