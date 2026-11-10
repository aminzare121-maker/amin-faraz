"""Ingest the hash-pinned, actual MQL capture without any MT5 API calls."""
import argparse,hashlib,json,time
from pathlib import Path
from candle_archive import CandleArchive
BASE=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--receipt',required=True);p.add_argument('--archive',required=True);args=p.parse_args()
    receipt=json.loads(Path(args.receipt).read_text(encoding='utf-8-sig'))
    if receipt.get('actual_mql_runtime_verified') is not True:raise ValueError('UNVERIFIED_MQL_RECEIPT')
    source=Path(receipt['capture_path']);raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=receipt['capture_sha256']:raise ValueError('CAPTURE_HASH_MISMATCH')
    compile_receipt=json.loads((BASE/'reports/actual-compile.json').read_text(encoding='utf-8-sig'))
    if receipt['installed_ex5_sha256']!=compile_receipt['ex5_sha256'] or receipt['installed_source_sha256']!=compile_receipt['source_sha256']:raise ValueError('EXECUTED_BUILD_MISMATCH')
    doc=json.loads(raw)
    required={'schema':'artin_codex_capture_v1','capture_magic':'ARTIN_CODEX_INDEPENDENT_READ_ONLY',
        'demo':True,'orders_enabled':False,'server':'ePlanet-MT5','timeframe':'M15','period_seconds':900,'time_conversion_applied':False}
    if any(doc.get(k)!=v for k,v in required.items()) or doc.get('symbol') not in ('XAUUSD','XAUUSD.st'):raise ValueError('CAPTURE_SCOPE_MISMATCH')
    if len(doc['bars'])!=doc['received_closed_bars']:raise ValueError('CAPTURE_COUNT_MISMATCH')
    started=time.perf_counter();archive=CandleArchive(args.archive)
    result=archive.ingest(doc['bars'],current_bar_open=doc['current_bar_open_native'],symbol=doc['symbol'])
    # Preserve a private exact copy; do not send raw candles with public reports.
    target=BASE/'runtime/mql-capture-verified.json'
    if target.exists() and target.read_bytes()!=raw:raise ValueError('PRIVATE_CAPTURE_ALREADY_EXISTS')
    target.write_bytes(raw)
    proof=dict(schema='codex_independent_mql_to_archive_v1',capture_sha256=receipt['capture_sha256'],
        executed_ex5_sha256=receipt['installed_ex5_sha256'],capture_bar_count=len(doc['bars']),archive_result=result,
        import_and_verify_seconds=time.perf_counter()-started,orders_submitted=0,semantic_verified=False)
    (BASE/'reports/mql-archive-import.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    (BASE/'reports/mql-sdk-head-pin.json').write_text(json.dumps(result['head'],indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(capture_bars=len(doc['bars']),added=result['added'],duplicates=result['duplicates'],
        archived_count=result['head']['count'],orders_submitted=0)))
if __name__=='__main__':main()
