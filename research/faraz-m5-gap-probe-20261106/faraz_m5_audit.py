#!/usr/bin/env python3
"""FARAZ historical M5-to-M15 offline audit, NO broker connection and NO orders.

Python 3.10+, standard library only. All records remain local.
Inputs are CSV exports of the *same* MT5 symbol, terminal and quote side.
An absent bar from an incomplete history export does NOT prove closed markets.
"""
from __future__ import annotations
import argparse, csv, json, hashlib
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from collections import Counter

TARGETS = [(18,"2025-11-28T11:00:00"),(142,"2026-05-25T22:00:00")]
FIELDS = ("open", "high", "low", "close")


def parse_dt(v: str) -> datetime:
    v = str(v).strip()
    if v.isdecimal():
        return datetime(1970,1,1) + timedelta(seconds=int(v)) # raw epoch label; NOT asserted UTC
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try: return datetime.strptime(v, fmt)
        except ValueError: continue
    try:
        t = datetime.fromisoformat(v.replace("Z","+00:00"))
        if t.tzinfo is not None: raise ValueError("Timezone-bearing timestamps: first verify source clock contract; not accepted silently")
        return t
    except ValueError as e: raise ValueError(f"unrecognised or timezone-bearing timestamp: {v}") from e


def load_bars(path: Path, expected_symbol: str) -> dict[datetime,dict]:
    out = {}
    with path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if reader.fieldnames is None: raise ValueError(f"empty CSV: {path}")
        columns={str(k).strip().lower():k for k in reader.fieldnames}
        tm=next((columns[x] for x in ("time","datetime","timestamp") if x in columns),None)
        if not tm or not all(x in columns for x in FIELDS): raise ValueError(f"missing time/OHLC columns in {path.name}")
        for line,row in enumerate(reader,2):
            if not any(row.values()):continue
            symkey=columns.get("symbol")
            if symkey and row.get(symkey,"" ).strip()!=expected_symbol:
                raise ValueError(f"symbol mismatch in {path.name} line {line}: {row.get(symkey)}")
            t=parse_dt(row[tm])
            try: r={p:Decimal(row[columns[p]]) for p in FIELDS}
            except (InvalidOperation,TypeError,KeyError) as e: raise ValueError(f"bad OHLC in {path.name} line {line}") from e
            if not all(v.is_finite() and v>0 for v in r.values()) or r["high"]<max(r["open"],r["close"]) or r["low"]>min(r["open"],r["close"]):
                raise ValueError(f"invalid OHLC in {path.name} line {line}")
            if t in out:
                if any(r[p]!=out[t][p] for p in FIELDS): raise ValueError(f"conflicting duplicate timestamp: {t} {path.name}")
                continue
            out[t]=r
    return out


def aggregate(t:datetime, m5:dict) -> dict|None:
    bars=[m5.get(t+timedelta(minutes=m)) for m in (0,5,10)]
    if not all(bars):return None
    return {"open":bars[0]["open"],"high":max(b["high"] for b in bars),"low":min(b["low"] for b in bars),"close":bars[2]["close"]}


def matched(a:dict,b:dict,tolerance:Decimal) -> bool:
    return all(abs(a[k]-b[k])<=tolerance for k in FIELDS)


def calibration(m15:dict, m5:dict, tolerance:Decimal, min_checks:int=100):
    candidates=[t for t in sorted(m15) if aggregate(t,m5) is not None]
    if len(candidates)>300:
        # Evenly spaced across the available time range; no data-mining by outcome.
        indices=sorted({round(i*(len(candidates)-1)/299) for i in range(300)})
        candidates=[candidates[i] for i in indices]
    good=sum(matched(m15[t],aggregate(t,m5),tolerance) for t in candidates)
    checked=len(candidates)
    aligned=checked>=min_checks and good>=int(0.98*checked+0.999999)
    return {"checked":checked,"matched":good,"mismatch":checked-good,"min_required":min_checks,"verified":aligned,
            "note":"Matches same-export M15 and M5 internally; does NOT verify match to old raw SDK timestamp labels or historical trading hours."}


def gaps_from_csv(p:Path):
    out=[]
    with p.open(encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f)
        for row in rd:
            gid=int(row["gap_id"])
            start=parse_dt(row["first_missing_candle_open_raw_label"])
            n=int(row["missing_m15_count"])
            out.extend((gid,start+timedelta(minutes=15*i)) for i in range(n))
    return out


def gaps_from_m15(m15:dict):
    times=sorted(m15)
    out=[]
    current_gap=0
    for a,b in zip(times,times[1:]):
        n=int((b-a).total_seconds()//900)-1
        if n<=0:continue
        current_gap+=1
        out.extend((current_gap,a+timedelta(minutes=15*i)) for i in range(1,n+1))
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--m15",type=Path,required=True)
    ap.add_argument("--m5",type=Path,required=True)
    ap.add_argument("--symbol",default="XAUUSD.st")
    ap.add_argument("--mode",choices=("probe","full"),default="probe")
    ap.add_argument("--gap-csv",type=Path,help="Optional original 260 gap CSV; use only after clock/source alignment")
    ap.add_argument("--out",type=Path,default=Path("faraz_m5_audit_out"))
    ap.add_argument("--min-checks",type=int,default=100)
    ap.add_argument("--tolerance",type=Decimal,default=Decimal("0.001"))
    args=ap.parse_args()
    if args.min_checks<1:ap.error("min-checks must be positive")
    m15=load_bars(args.m15,args.symbol)
    m5=load_bars(args.m5,args.symbol)
    c=calibration(m15,m5,args.tolerance,args.min_checks)
    if args.mode=="probe": gaps=[(i,parse_dt(t)) for i,t in TARGETS]
    elif args.gap_csv:gaps=gaps_from_csv(args.gap_csv)
    else:gaps=gaps_from_m15(m15)
    # Note raw source label mapping is NOT verified by this tool.
    mtimes=sorted(m5)
    counts=Counter()
    items=[]; recovered=[]
    for gid,t in gaps:
        available=[t+timedelta(minutes=i) for i in (0,5,10) if t+timedelta(minutes=i) in m5]
        cand=aggregate(t,m5)
        if t in m15:
            status="M15_PRESENT_IN_NEW_EXPORT"
        elif len(available)==3 and c["verified"]:
            status="M5_3_OF_3_VERIFIED_SAME_EXPORT"
        elif len(available)==3:
            status="M5_3_OF_3_BLOCKED_ALIGNMENT"
        elif 0<len(available)<3:
            status="M5_PARTIAL_1_OR_2"
        else:
            # Local evidence of nearby M5 does not establish broker's full coverage.
            before=any(t-timedelta(minutes=i) in m5 for i in (5,10,15,20,25,30))
            after=any(t+timedelta(minutes=i) in m5 for i in (15,20,25,30,35,40))
            status="M5_0_WITH_LOCAL_NEIGHBORS" if before and after else "M5_HISTORY_UNAVAILABLE_OR_MARKET_CLOSED_UNKNOWN"
        counts[status]+=1
        items.append({"gap_id":gid,"time_source_label":t.isoformat(),"status":status,"m5_present":len(available),"m5_times":[x.isoformat() for x in available]})
        if status=="M5_3_OF_3_VERIFIED_SAME_EXPORT":
            recovered.append({"gap_id":gid,"time":t.isoformat(),"open":str(cand["open"]),"high":str(cand["high"]),"low":str(cand["low"]),"close":str(cand["close"]),"origin":"RECOVERED_FROM_M5_RESEARCH_ONLY"})
    args.out.mkdir(parents=True,exist_ok=True)
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    metadata={"status":"OFFLINE_DIAGNOSTIC_ONLY", "symbol":args.symbol, "mode":args.mode,
              "m15_count":len(m15),"m5_count":len(m5),"target_slots":len(gaps),"classification_counts":dict(counts),
              "calibration":c,
              "sources":{"m15_sha256":sha(args.m15),"m5_sha256":sha(args.m5)},
              "cautions":["Read-only export of same symbol/account must be confirmed by owner.",
                          "Verified refers only to internal M5/M15 OHLC consistency in this export; not old raw SDK labels.",
                          "No missing M5 record demonstrates broker intent or confirmed market closure.",
                          "No recovered price is evidence of executable Bid/Ask or financial backtest validity."],
              "slots":items}
    (args.out/"faraz_m5_audit_report.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    if recovered:
        with (args.out/"faraz_m5_recovered_PRIVATE.csv").open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(recovered[0]));w.writeheader();w.writerows(recovered)
    print(json.dumps({k:v for k,v in metadata.items() if k!="slots"},ensure_ascii=False,indent=2))
    print("Two targets:")
    for x in items:
        if x["time_source_label"] in [t for _,t in TARGETS]:print(x)
    print(f"Saved report in {args.out.resolve()} (PRIVATE, never publish raw prices)")

if __name__=="__main__": main()