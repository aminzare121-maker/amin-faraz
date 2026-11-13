"""Read-only local MT5 DEMO probe. No trading functions or credentials.

Run on the Windows machine with MetaTrader 5 open:
    python artin_mt5_demo_probe.py --out artin_demo_probe.json
"""
import argparse
import json
from pathlib import Path


class ProbeBlocked(RuntimeError):
    pass


def probe(mt5):
    if not mt5.initialize():
        raise ProbeBlocked('MT5_INITIALIZE_FAILED')
    try:
        account = mt5.account_info()
        terminal = mt5.terminal_info()
        if account is None or terminal is None:
            raise ProbeBlocked('MT5_ACCOUNT_OR_TERMINAL_UNAVAILABLE')
        # MetaTrader5 ACCOUNT_TRADE_MODE_DEMO = 0; fail closed for other modes.
        if getattr(account, 'trade_mode', None) != getattr(mt5, 'ACCOUNT_TRADE_MODE_DEMO', 0):
            raise ProbeBlocked('MT5_ACCOUNT_IS_NOT_DEMO')
        if getattr(terminal, 'connected', False) is not True:
            raise ProbeBlocked('MT5_TERMINAL_DISCONNECTED')
        symbol = mt5.symbol_info('XAUUSD')
        if symbol is None:
            raise ProbeBlocked('MT5_XAUUSD_NOT_FOUND')
        # Never export login, server, password, token, balance, or positions.
        return {'schema':'artin_mt5_demo_readonly_probe_v1',
                'terminal_connected':True,'account_mode':'DEMO',
                'symbol':'XAUUSD','symbol_available':True,
                'terminal_trade_allowed':bool(getattr(terminal,'trade_allowed',False)),
                'orders_sent':0,'order_functions_called':False,
                'broker_fills_verified':False,'demo_trade_test_passed':False}
    finally:
        mt5.shutdown()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit('METATRADER5_PYTHON_PACKAGE_NOT_INSTALLED') from exc
    try:
        result=probe(mt5)
    except ProbeBlocked as exc:
        raise SystemExit(str(exc)) from exc
    out=Path(args.out)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('DEMO_READONLY_PROBE_OK: '+str(out))


if __name__=='__main__':
    main()
