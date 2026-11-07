"""Local, read-only MT5 Eplanet REAL history collector. Never uploads raw prices."""
import argparse, csv, hashlib, json
from datetime import datetime, timedelta, timezone
from pathlib import Path

def fetch(days=365, tick_minutes=30, out="PRIVATE_EPLANET_HISTORY"):
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError("Open the authorized MT5 terminal; initialize failed")
    try:
        account, terminal = mt5.account_info(), mt5.terminal_info()
        if account is None or terminal is None or not terminal.connected:
            raise RuntimeError("No connected MT5 account")
        if account.trade_mode != mt5.ACCOUNT_TRADE_MODE_REAL:
            raise RuntimeError("REAL account required; abort")
        if "eplanet" not in str(account.server).lower():
            raise RuntimeError("Connected broker server was not identified as Eplanet")
        symbol = "XAUUSD.st"
        info = mt5.symbol_info(symbol)
        if info is None or not info.visible:
            raise RuntimeError("XAUUSD.st must already be visible; no terminal settings modified")
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start, now)
        if rates is None or not len(rates):
            raise RuntimeError("M15 history unavailable. Check Max bars in chart and connection.")
        folder = Path(out).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        def save(filename, header, rows):
            path = folder / filename
            with path.open("w", newline="", encoding="utf-8") as fp:
                w = csv.writer(fp); w.writerow(header); w.writerows(rows)
            return hashlib.sha256(path.read_bytes()).hexdigest()
        def utc(t):
            return datetime.fromtimestamp(int(t), timezone.utc).isoformat()
        digest = save("xauusdst_m15.csv",
            ["open_utc","open","high","low","close","tick_volume","spread_points","real_volume"],
            ((utc(x["time"]),float(x["open"]),float(x["high"]),float(x["low"]),
              float(x["close"]),int(x["tick_volume"]),int(x["spread"]),int(x["real_volume"])) for x in rates))
        gaps, invalid, duplicate = 0, 0, 0
        last = None
        for row in rates:
            t = int(row["time"])
            if not (row["low"] <= min(row["open"],row["close"]) <= max(row["open"],row["close"]) <= row["high"]):
                invalid += 1
            if last is not None:
                gaps += t-last > 900
                duplicate += t <= last
            last = t
        ticks = mt5.copy_ticks_range(symbol, now-timedelta(minutes=tick_minutes), now, mt5.COPY_TICKS_ALL)
        tick_status, tick_count, tick_digest = "UNAVAILABLE", 0, None
        if ticks is not None and 0 < len(ticks) <= 100000:
            tick_count = len(ticks)
            tick_digest = save("xauusdst_tick_sample.csv",
                ["time_utc","time_msc","bid","ask","last","volume","flags"],
                ((utc(x["time"]),int(x["time_msc"]),float(x["bid"]),float(x["ask"]),
                   float(x["last"]),int(x["volume"]),int(x["flags"])) for x in ticks))
            tick_status = "EXPORTED"
        elif ticks is not None and len(ticks) > 100000:
            tick_status = "TOO_MANY_SKIPPED"
        properties = ("digits","point","trade_contract_size","trade_tick_size",
                      "trade_tick_value","trade_stops_level","trade_freeze_level",
                      "swap_mode","swap_long","swap_short","swap_rollover3days")
        report = {
            "mode":"REAL_READ_ONLY", "symbol":symbol, "timestamp_utc":now.isoformat(),
            "requested_from_utc":start.isoformat(), "first_m15_utc":utc(rates[0]["time"]),
            "last_m15_utc":utc(rates[-1]["time"]), "m15_rows":len(rates),
            "m15_sha256":digest, "invalid_ohlc":invalid, "out_of_order_or_duplicate":duplicate,
            "gaps_including_weekends":gaps, "tick_status":tick_status,
            "tick_sample_rows":tick_count, "tick_sha256":tick_digest,
            "symbol_spec":{k:getattr(info,k,None) for k in properties},
            "notes":["No order functions called","No raw data uploaded",
                     "Broker server DST needs independent verification",
                     "All gaps need session-aware classification",
                     "Do not infer real execution slippage from these prices"]}
        (folder/"qa_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        return {k:report[k] for k in ("mode","m15_rows","tick_status","tick_sample_rows","invalid_ohlc","out_of_order_or_duplicate")}
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--days",type=int,default=365)
    p.add_argument("--tick-minutes",type=int,default=30)
    p.add_argument("--output",default="PRIVATE_EPLANET_HISTORY")
    a=p.parse_args()
    if not (1 <= a.days <= 366 and 1 <= a.tick_minutes <= 60):
        p.error("days 1..366 and tick-minutes 1..60")
    print(json.dumps(fetch(a.days,a.tick_minutes,a.output),ensure_ascii=False))
