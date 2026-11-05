"""Read metadata/current quote only from exact existing DEMO terminal; no history/order."""
import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'eplanet-history-revision'))
import export_readonly as guard
import MetaTrader5 as mt5
before=guard.pids()
if len(before)!=1:raise RuntimeError('EXACT_EXISTING_TERMINAL_REQUIRED')
if not mt5.initialize(str(guard.EXE),timeout=10000):raise RuntimeError('ATTACH_FAILED')
try:
    symbol=guard.check(mt5)
    if guard.pids()!=before:raise RuntimeError('PROCESS_CHANGED')
    t0=time.time();quote=mt5.symbol_info_tick(guard.SYMBOL);t1=time.time()
    if not quote:raise RuntimeError('NO_QUOTE')
    guard.check(mt5)
    out={'mode':'DEMO','symbol':guard.SYMBOL,'chart_mode':symbol.chart_mode,
         'chart_mode_bid_constant':getattr(mt5,'SYMBOL_CHART_MODE_BID',None),
         'chart_mode_last_constant':getattr(mt5,'SYMBOL_CHART_MODE_LAST',None),
         'utc_wall_before':t0,'utc_wall_after':t1,'quote_time_msc':quote.time_msc,
         'quote_minus_wall_seconds':quote.time_msc/1000-(t0+t1)/2,
         'same_existing_process':guard.pids()==before,'history_calls':0,'orders':0,
         'note':'Clock observation is current only; no historical DST inferred.'}
    Path(__file__).with_name('terminal-clock-sanitized.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out))
finally:mt5.shutdown()
