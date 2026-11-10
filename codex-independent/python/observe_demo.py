"""One read-only SDK cycle against the existing ePlanet DEMO terminal."""
import argparse,datetime as dt,hashlib,json,math,time,os
from pathlib import Path
from candle_archive import CandleArchive
def capture(count,terminal_path,expected_data,latest=None,backfill_from=None):
    if type(count) is not int or not 1<=count<=50000:raise ValueError('COUNT_OUT_OF_RANGE')
    import MetaTrader5 as mt
    started=time.perf_counter()
    if not mt.initialize(str(terminal_path),timeout=15000):raise RuntimeError('EXISTING_DEMO_ATTACH_FAILED')
    try:
        terminal=mt.terminal_info();account=mt.account_info()
        if terminal is None or account is None:raise RuntimeError('IDENTITY_UNAVAILABLE')
        if account.trade_mode!=mt.ACCOUNT_TRADE_MODE_DEMO or account.server!='ePlanet-MT5':raise RuntimeError('EPLANET_DEMO_REQUIRED')
        if 'eplanet' not in account.company.lower() or Path(terminal.data_path)!=expected_data:raise RuntimeError('TERMINAL_IDENTITY_MISMATCH')
        if not terminal.connected:raise RuntimeError('DEMO_DISCONNECTED')
        identity=account.login
        symbol='XAUUSD.st'
        current=mt.copy_rates_from_pos(symbol,mt.TIMEFRAME_M15,0,1)
        if current is None or len(current)!=1:raise RuntimeError('CURRENT_BAR_UNAVAILABLE')
        fence=int(current[0]['time'])
        if latest is not None and (type(latest) is not int or latest>=fence):raise RuntimeError('INVALID_LATEST_WATERMARK')
        required=count if latest is None else max(count,math.ceil((fence-latest)/900)+4)
        if backfill_from is not None:
            if type(backfill_from) is not int or backfill_from>=fence:raise RuntimeError('INVALID_BACKFILL_WATERMARK')
            required=max(required,math.ceil((fence-backfill_from)/900)+4)
        if required>50000:raise RuntimeError('BOUNDED_BACKFILL_WINDOW_EXCEEDED')
        receive_start=time.perf_counter();data=mt.copy_rates_from_pos(symbol,mt.TIMEFRAME_M15,1,required)
        receive_seconds=time.perf_counter()-receive_start
        if data is None or not len(data):raise RuntimeError('CLOSED_HISTORY_UNAVAILABLE')
        current_after=mt.copy_rates_from_pos(symbol,mt.TIMEFRAME_M15,0,1)
        after=mt.account_info();end_terminal=mt.terminal_info()
        if (after is None or end_terminal is None or after.login!=identity or after.trade_mode!=mt.ACCOUNT_TRADE_MODE_DEMO
            or after.server!='ePlanet-MT5' or 'eplanet' not in after.company.lower()
            or Path(end_terminal.data_path)!=expected_data or not end_terminal.connected):raise RuntimeError('IDENTITY_CHANGED_DURING_READ')
        if current_after is None or len(current_after)!=1 or int(current_after[0]['time'])!=fence:raise RuntimeError('BAR_BOUNDARY_CHANGED_RETRY')
        bars=[{k:int(row[k]) if k in ('time','tick_volume','spread','real_volume') else float(row[k])
            for k in ('time','open','high','low','close','tick_volume','spread','real_volume')} for row in data]
        # CopyRates count is actual bars, not wall-clock grid slots. Session
        # closures can make it return earlier history than the requested gap.
        # Do not keep expanding the archive backwards on every unresolved gap.
        if backfill_from is not None:bars=[b for b in bars if b['time']>=backfill_from]
        if not bars:raise RuntimeError('BACKFILL_RANGE_UNAVAILABLE')
        if latest is not None and min(b['time'] for b in bars)>latest:raise RuntimeError('HISTORY_OVERLAP_UNAVAILABLE')
        return dict(schema='artin_codex_sdk_capture_v1',symbol=symbol,timeframe='M15',demo=True,
            server='ePlanet-MT5',native_time_preserved=True,time_conversion_applied=False,
            current_bar_open_native=fence,bars=bars,requested=required,received=len(bars),
            native_rows_returned=len(data),partial_history=len(data)<required,receive_seconds=receive_seconds,
            attach_and_capture_seconds=time.perf_counter()-started,orders_enabled=False)
    finally:mt.shutdown()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive',required=True);parser.add_argument('--report',required=True)
    parser.add_argument('--snapshot',required=True);parser.add_argument('--count',type=int,default=512)
    parser.add_argument('--terminal',required=True);parser.add_argument('--expected-data',required=True);args=parser.parse_args()
    if not 1<=args.count<=50000:raise ValueError('COUNT_OUT_OF_RANGE')
    started=time.perf_counter();archive=CandleArchive(args.archive)
    previous=archive.verify() if (Path(args.archive)/'checkpoint.json').exists() else None
    latest=previous['latest_time'] if previous else None
    # Revisit interior gaps as well as the latest watermark. Large unresolved
    # session gaps outside the bounded window are reported, never filled with
    # invented bars and never allowed to block all recent ingestion forever.
    gaps=previous['gaps'] if previous else []
    eligible=[g['after'] for g in gaps if latest is not None and latest-g['after']<(50000-args.count-8)*900]
    backfill_from=min(eligible) if eligible else None
    capture_doc=capture(args.count,Path(args.terminal),Path(args.expected_data),latest,backfill_from)
    snapshot=Path(args.snapshot);snapshot.parent.mkdir(parents=True,exist_ok=True)
    if snapshot.exists():raise RuntimeError('SNAPSHOT_EXISTS_NO_OVERWRITE')
    raw=(json.dumps(capture_doc,sort_keys=True,separators=(',',':'))+'\n').encode();snapshot.write_bytes(raw)
    result=archive.ingest(capture_doc['bars'],current_bar_open=capture_doc['current_bar_open_native'])
    report=dict(schema='artin_codex_observer_cycle_v1',checked_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        demo_guard_passed=True,existing_terminal_identity_passed=True,receive_seconds=capture_doc['receive_seconds'],
        attach_and_capture_seconds=capture_doc['attach_and_capture_seconds'],archive=result,
        snapshot_sha256=hashlib.sha256(raw).hexdigest(),snapshot_bytes=len(raw),
        interior_gap_revisit_from_native=backfill_from,older_gap_ranges_deferred=len(gaps)-len(eligible),
        total_seconds=time.perf_counter()-started,orders_submitted=0,terminal_restarted=False,
        account_login_called=False,network_disconnection_simulated=False,video_extraction_benchmarked=False)
    dest=Path(args.report);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise RuntimeError('REPORT_EXISTS_NO_OVERWRITE')
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':main()
