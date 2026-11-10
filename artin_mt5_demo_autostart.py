"""Discover the already open ePlanet DEMO terminal, run auto scanner in observe mode.

No login, no user credentials, no REAL account, no order mode.
Owner's verified configuration is required separately to enable DEMO orders.
"""
from pathlib import Path
import sys,subprocess

def main():
    try:import MetaTrader5 as mt
    except ImportError as e:raise SystemExit('BLOCKED: MetaTrader5 package not installed on Windows') from e
    if not mt.initialize(timeout=15000):raise SystemExit('BLOCKED: Existing MT5 terminal unavailable')
    try:
        account=mt.account_info();terminal=mt.terminal_info()
        if account is None or terminal is None or not terminal.connected:
            raise SystemExit('BLOCKED: No connected terminal/account')
        if (account.trade_mode!=mt.ACCOUNT_TRADE_MODE_DEMO or
            account.server!='ePlanet-MT5' or 'eplanet' not in account.company.lower()):
            raise SystemExit('BLOCKED: Only ePlanet DEMO is allowed')
        path=Path(terminal.path)
        options=(path/'terminal64.exe',path/'terminal.exe')
        candidates=[x for x in options if x.is_file()]
        if len(candidates)!=1:raise SystemExit('BLOCKED: Terminal executable path ambiguous')
        terminal_path=str(candidates[0]);data_path=str(Path(terminal.data_path))
    finally:mt.shutdown()
    base=Path(__file__).resolve().parent
    args=[sys.executable,str(base/'artin_mt5_demo_automatic.py'),
        '--terminal',terminal_path,'--expected-data',data_path,
        '--state',str(base/'private/ARTIN_AUTOMATIC_DEMO_STATE.json'),
        '--report',str(base/'private/ARTIN_AUTOMATIC_DEMO_OBSERVER.jsonl')]
    return subprocess.call(args)

if __name__=='__main__':sys.exit(main())