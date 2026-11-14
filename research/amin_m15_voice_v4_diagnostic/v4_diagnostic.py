#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Eplanet M15 V4: frozen V3 long 4-bar 2R model, loss cohorts and one-shot holdout.
RESEARCH ONLY. No broker login, no orders, no trade signal.
This script may NOT use holdout outcomes to retune the filters.
"""
from pathlib import Path
import sys, json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

BASE = Path(__file__).resolve().parents[1] / "amin_m15_voice_v3_full"
sys.path.insert(0, str(BASE))
import amin_candle_voice_v3 as v3

CSV = BASE/"data/Eplanet_M15_20251105_20261105_merged.csv"
OUT = Path(__file__).resolve().parent/"results"
HASH = "06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604"
PRESET = {"spec":"h4_sl1_r2", "model":"V3 TP probability classifier", "side":"long", "quantile":0.9,
          "start_utc_hour":7, "end_utc_hour_exclusive":20, "min_trend_24_atr":0,
          "max_spread_atr_calibration_quantile":0.7, "recent_gap_20":False,
          "filters_modified_after_holdout":False}
def cohorts(trades, label):
    buckets = {}
    for t in trades:
        buckets.setdefault(str(label(t)),[]).append(t)
    return {k:{"trades":len(vals), "losses":sum(t["pnl_usd_assumed_fixed_001_lot"]<0 for t in vals),
               "stops":sum(t["event"].startswith("STOP") for t in vals),
               "net_usd_001_lot":round(sum(t["pnl_usd_assumed_fixed_001_lot"] for t in vals),3)}
            for k, vals in sorted(buckets.items())}
def summarize(trades, df, ids):
    days=len({int(df.time.iat[int(i)]//86400) for i in ids})
    m=v3.metrics(trades,days)
    ci=v3.daily_bootstrap_lower(trades)
    halves=v3.time_robustness(trades,int(ids[len(ids)//2]))
    stress=round(m["sum_usd_fixed_001_lot"] - len(trades)*v3.STRESS_EXTRA_COST_PRICE_PER_OZ*v3.CONTRACT_OZ*v3.LOT,3)
    return {"metrics":m,"bootstrap_lower_usd_per_trade":ci,"halves":halves,
            "stressed_total_usd":stress,"passes_v3_gate":v3.gate(m,ci,halves,stress)}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    df=v3.read_history(CSV)
    assert len(df)==23643 and v3.sha256(CSV)==HASH, "FULL_SOURCE_PROVENANCE_FAIL"
    f,atr=v3.features(df)
    x=f.to_numpy(dtype=float)
    sp=v3.Barrier(4,1.,2.)
    out=v3.label_barriers(df,atr,sp)
    valid=out["valid"]&np.isfinite(x).all(axis=1)
    parts={name:ids[valid[ids]] for name,ids in v3.make_splits(len(df),4).items()}
    train,cal,val,hold=[parts[k] for k in ("train","calibration","validation","holdout")]
    model=HistGradientBoostingClassifier(max_iter=65,max_leaf_nodes=9,max_depth=4,
          learning_rate=.05,min_samples_leaf=100,l2_regularization=12,
          random_state=v3.SEED,early_stopping=False)
    model.fit(x[train],out["buy"]["tp"][train])
    pcal=model.predict_proba(x[cal])[:,1]
    pval=model.predict_proba(x[val])[:,1]
    phold=model.predict_proba(x[hold])[:,1]
    a,b,c=v3.calibrate_p(pcal,out["buy"]["tp"][cal],pval,phold)
    threshold=float(np.quantile(a,.9))
    spread_cap=float(np.quantile(f["spread_atr_assumed"].iloc[cal],.70))
    assert all(np.isfinite(z) for z in (threshold,spread_cap))
    def market_ok(i):
        row=f.iloc[int(i)]
        hour=(int(df.time.iat[int(i)])%86400)//3600
        return bool(7<=hour<20 and row["trend_24"]>0 and
                    row["spread_atr_assumed"]<=spread_cap and row["gap_in_last_20"]==0)
    def add_info(trades):
        rows=[]
        for t in trades:
            i=int(t["decision_index"]);r=dict(t); ff=f.iloc[i]
            r.update({"hour_utc":int((int(df.time.iat[i])%86400)//3600),
                    "atr_price":round(float(ff["atr"]),6),
                    "spread_to_atr":round(float(ff["spread_atr_assumed"]),6),
                    "trend_24_atr":round(float(ff["trend_24"]),6),
                    "recent_gap":int(ff["gap_in_last_20"])})
            rows.append(r)
        return rows
    report={"source":{"sha256":HASH,"bars":len(df),
                "start_utc":v3.utc(df.time.iat[0]),"end_utc":v3.utc(df.time.iat[-1])},
            "preset":PRESET,"threshold_calibration":threshold,"spread_cap_calibration":spread_cap,
            "split_rows":{k:len(v) for k,v in parts.items()},
            "cohorts_calibration_only":{},"results":{},
            "new_filter_after_holdout_retuned":False,
            "signal_approved":False,"orders_sent":0}
    for name,ids,scores in (("calibration",cal,a),("validation",val,b),("holdout",hold,c)):
        proba=dict(zip((int(i) for i in ids),(float(p) for p in scores)))
        raw=v3.select_backtest(df,ids,out,{"buy":proba,"sell":{}},{"buy":threshold,"sell":1e6},"long")
        clean={i:p for i,p in proba.items() if market_ok(i)}
        filt=v3.select_backtest(df,ids,out,{"buy":clean,"sell":{}},{"buy":threshold,"sell":1e6},"long")
        report["results"][name]={"reference":summarize(raw,df,ids),"filter":summarize(filt,df,ids)}
        ra=add_info(raw); fa=add_info(filt)
        pd.DataFrame(ra).to_csv(OUT/f"{name}_reference_trades.csv",index=False)
        pd.DataFrame(fa).to_csv(OUT/f"{name}_filtered_trades.csv",index=False)
        if name=="calibration":
            report["cohorts_calibration_only"]={
                "exit_type":cohorts(ra,lambda t:t["event"]),
                "utc_4h":cohorts(ra,lambda t: f"{(t['hour_utc']//4)*4:02d}-{(t['hour_utc']//4)*4+3:02d}"),
                "trend":cohorts(ra,lambda t: "up" if t["trend_24_atr"]>0 else "down_or_flat"),
                "relative_cost":cohorts(ra,lambda t:"low" if t["spread_to_atr"]<=spread_cap else "high"),
                "recent_gap":cohorts(ra,lambda t:"yes" if t["recent_gap"] else "no")}
    # Verify exact replication of past V3 validation candidate and frozen test outputs
    assert report["results"]["validation"]["reference"]["metrics"]["signals"]==246
    assert abs(report["results"]["validation"]["reference"]["metrics"]["sum_usd_fixed_001_lot"]-129.444)<.02
    assert report["results"]["holdout"]["reference"]["metrics"]["signals"]==242
    assert report["results"]["holdout"]["filter"]["metrics"]["signals"]==49
    assert abs(report["results"]["holdout"]["filter"]["metrics"]["sum_usd_fixed_001_lot"]+203.545)<.02
    assert report["results"]["holdout"]["filter"]["passes_v3_gate"] is False
    report["joint_val_holdout_pass"]=all(report["results"][part]["filter"]["passes_v3_gate"]
                                      for part in ("validation","holdout"))
    report["conclusion"]="FILTER_REJECTED_BY_UNSEEN_HOLDOUT"
    (OUT/"v4_diagnostic_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("V4_SOURCE_AND_MODEL_REPLAY_PASS")
    print(json.dumps({"rows":len(df),"threshold":round(threshold,6),"cost_ratio_cap":round(spread_cap,6),
        "reference_validation":report["results"]["validation"]["reference"]["metrics"],
        "filtered_validation":report["results"]["validation"]["filter"]["metrics"],
        "reference_holdout":report["results"]["holdout"]["reference"]["metrics"],
        "filtered_holdout":report["results"]["holdout"]["filter"]["metrics"],
        "conclusion":report["conclusion"],"live_signal_approved":False},ensure_ascii=False))

if __name__=="__main__": main()
