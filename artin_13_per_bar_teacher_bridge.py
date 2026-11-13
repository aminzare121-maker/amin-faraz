#!/usr/bin/env python3
"""Per-bar three-valued Artin predicate bridge. Unknown is NEVER coerced to False or True.
Market observations are not teacher signals; no orders or P&L are generated.
"""
from __future__ import annotations
import csv,glob,json,sys
from collections import Counter
from artin_13_real_m15_gap_audit import REQUIRED, COMMON, FAMILY

def evaluate(path):
    rows=list(csv.DictReader(open(path,encoding="utf-8-sig")))
    bars=[]
    for row in rows:
        t=int(row.get("timestamp") or row.get("time"))
        if t>10**11:t//=1000
        o,h,l,c=[float(row[k]) for k in ("open","high","low","close")]
        if t%900 or not 0<l<=min(o,c)<=max(o,c)<=h or (bars and t<=bars[-1][0]):
            raise ValueError("INVALID_SOURCE_BAR")
        bars.append((t,o,h,l,c))
    counts={route:Counter() for route in REQUIRED}
    examples={}
    for i,(t,o,h,l,c) in enumerate(bars):
        contiguous=i>=2 and t-bars[i-1][0]==900 and bars[i-1][0]-bars[i-2][0]==900
        directions=([(b[4]>b[1])-(b[4]<b[1]) for b in bars[i-2:i+1]] if contiguous else [])
        facts={"decision_close":c,"decision_candle_closed":True,
               "three_same_direction_sequence":bool(directions and directions[0]!=0 and directions.count(directions[0])==3)}
        for route,required in REQUIRED.items():
            needed=tuple(dict.fromkeys(COMMON+FAMILY+required))
            known={k:facts[k] for k in needed if k in facts}
            missing=[k for k in needed if k not in facts]
            # A source-derived teacher predicate is required before entering.
            # Even a known false cannot become a confirmed NO_TRADE without the teacher's rule semantics.
            state="UNRESOLVED_TEACHER_CONTEXT" if missing else "ALL_PREDICATES_OBSERVED_NOT_SEMANTICALLY_VERIFIED"
            counts[route][state]+=1
            if route not in examples:examples[route]={"timestamp":t,"known_market_facts":known,"unknown_teacher_predicates":missing}
    return {"schema":"artin_13_per_bar_tri_state_bridge_v1","source_rows":len(bars),
            "routes":[{"route_id":r,"states":dict(counts[r]),"first_bar_example":examples[r]} for r in REQUIRED],
            "total_route_bar_evaluations":len(bars)*len(REQUIRED),
            "teacher_approved_entries":0,"trades_executed":0,"net_profit":None,
            "note":"Unknown teacher conditions are not inferred from candle geometry."}

if __name__=="__main__":
    result=evaluate(sys.argv[1])
    with open(sys.argv[2],"w") as f:json.dump(result,f,indent=2)
    print(json.dumps({"rows":result["source_rows"],"route_bar_evaluations":result["total_route_bar_evaluations"],"teacher_approved_entries":0}))
