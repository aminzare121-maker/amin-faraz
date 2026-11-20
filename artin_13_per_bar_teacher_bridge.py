#!/usr/bin/env python3
"""Per-bar three-valued Artin predicate bridge. Unknown is NEVER coerced to False or True.
Market observations are not teacher signals; no orders or P&L are generated.
"""
from __future__ import annotations
import csv,glob,json,sys,math,importlib.util
from decimal import Decimal
from pathlib import Path
from collections import Counter
from artin_13_real_m15_gap_audit import REQUIRED, requirements
from artin_dossier_decision_gate import inspect_dossier

def evaluate(path, dossier=None, *, as_of=None):
    # In a causal replay, the decision clock must not precede any bar close.
    # Historical imports without as_of remain observation-only, never executable.
    if as_of is not None and (type(as_of) is not int or as_of < 0):
        raise ValueError('INVALID_DECISION_CLOCK')
    # Validate private evidence at the actual M15 decision boundary, never via a caller's approval flag.
    evidence = inspect_dossier(dossier)
    if evidence['executable'] or evidence['trade_authorized'] or evidence['approved_rule_outcomes']:
        raise AssertionError('UNEXPECTED_EXECUTABLE_TEACHER_EVIDENCE')
    rows=list(csv.DictReader(open(path,encoding="utf-8-sig")))
    bars=[]
    for row in rows:
        t=int(row.get("timestamp") or row.get("time"))
        if t>10**11:t//=1000
        o,h,l,c=[float(row[k]) for k in ("open","high","low","close")]
        if (t%900 or not all(math.isfinite(v) for v in (o,h,l,c))
                or not 0<l<=min(o,c)<=max(o,c)<=h
                or (bars and t<=bars[-1][0])):
            raise ValueError("INVALID_SOURCE_BAR")
        if as_of is not None and t + 900 > as_of:
            raise ValueError('UNCLOSED_OR_FUTURE_SOURCE_BAR')
        bars.append((t,o,h,l,c))
    if not bars:
        raise ValueError("EMPTY_SOURCE_BARS")
    # Evaluate the actual independent entry engine alongside the evidence gate.
    # Empty teacher facts are deliberate: market OHLC is not teacher AV approval.
    engine_path=Path(__file__).resolve().parent/'research/artin-independent-engine/entry_engine.py'
    spec=importlib.util.spec_from_file_location('artin_integrated_entry_engine',engine_path)
    entry=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=entry
    spec.loader.exec_module(entry)
    if set(REQUIRED)!=set(entry.RULE_IDS):
        raise ValueError('ROUTE_SET_MISMATCH')
    # The legacy engine's hard-coded session references are not authoritative.
    # Keep dossier session identities separate and flag conflicts for original
    # audiovisual review rather than silently attributing a rule to a video.
    source_conflicts={}
    for route, identity in evidence.get('route_source_identity', {}).items():
        legacy_sessions=sorted({session for session, *_ in entry.SOURCES.get(route, ())})
        dossier_sessions=identity['source_sessions']
        # Matching session numbers alone cannot establish identical source clips.
        # Compare time intervals only when the dossier carries exact ranges;
        # both sides remain unverified until original audiovisual replay.
        dossier_route = next((r for r in dossier['routes'] if r['route_id'] == route), None)
        dossier_ranges = sorted((int(x['session']), float(x['start']), float(x['end']))
                                for x in dossier_route['citation_intervals']) if dossier_route else []
        engine_ranges = sorted((int(s), float(a), float(b))
                               for s, a, b in entry.SOURCES.get(route, ()))
        range_mismatch = dossier_ranges != engine_ranges
        if legacy_sessions != dossier_sessions or range_mismatch:
            source_conflicts[route]={
                'engine_sessions_unverified':legacy_sessions,
                'dossier_sessions_unverified':dossier_sessions,
                'interval_identity_mismatch':range_mismatch,
                'status':'SOURCE_IDENTITY_CONFLICT_REQUIRES_ORIGINAL_AV',
            }
    engine=entry.Engine('ARTIN_PER_BAR_SOURCE_GATED',tuple(entry.RULE_IDS))
    engine_statuses={route:Counter() for route in REQUIRED}
    engine_reasons={route:Counter() for route in REQUIRED}
    counts={route:Counter() for route in REQUIRED}
    side_counts={route:{side:Counter() for side in ('BUY','SELL')} for route in REQUIRED}
    examples={}
    for i,(t,o,h,l,c) in enumerate(bars):
        # Raw candle direction is not the teacher-defined three-candle setup.
        # Preserve it as an unresolved teacher predicate until original AV replay.
        facts={"decision_close":c,"decision_candle_closed":True}
        # Only causal market facts cross the engine boundary. Teacher predicates
        # remain absent; the entry engine cannot infer teacher AV approval.
        market_facts={
            "decision_close":entry.Fact(Decimal(str(c)),t+900,"M15_CSV_CLOSE_UNVERIFIED_PROVENANCE"),
            "decision_candle_closed":entry.Fact(True,t+900,"M15_CSV_CLOSED_BAR"),
        }
        for route,required in REQUIRED.items():
            for side in ('BUY','SELL'):
                decision=engine.evaluate(route,entry.Observation(side,t+900,market_facts))
                if decision.order_created or decision.status=='ELIGIBLE':
                    raise AssertionError('UNVERIFIED_TEACHER_ENTRY_NOT_BLOCKED')
                engine_statuses[route][decision.status]+=1
                for reason in decision.reasons:
                    engine_reasons[route][reason]+=1
                # Preserve the actual engine verdict for this side and bar.
                # Teacher AV remains uncertified: this is diagnostic only.
                side_counts[route][side]['ENGINE_'+decision.status]+=1
                for reason in decision.reasons:
                    side_counts[route][side]['REASON:'+reason]+=1
            needed_by_side={side: requirements(route, side) for side in ('BUY', 'SELL')}
            needed=tuple(dict.fromkeys(needed_by_side['BUY']+needed_by_side['SELL']))
            known={k:facts[k] for k in needed if k in facts}
            missing=[k for k in needed if k not in facts]
            # A source-derived teacher predicate is required before entering.
            # Even a known false cannot become a confirmed NO_TRADE without the teacher's rule semantics.
            state="UNRESOLVED_TEACHER_CONTEXT" if missing else "ALL_PREDICATES_OBSERVED_NOT_SEMANTICALLY_VERIFIED"
            counts[route][state]+=1
            for side in ('BUY','SELL'):
                # Independently of the engine verdict, unverified teacher AV
                # cannot become a BUY/SELL signal or certified NO_TRADE.
                side_counts[route][side]['BLOCKED_TEACHER_AV_UNVERIFIED']+=1
            if route not in examples:examples[route]={"timestamp":t,"known_market_facts":known,"unknown_teacher_predicates":missing,"unknown_by_side":{side:[k for k in keys if k not in facts] for side,keys in needed_by_side.items()}}
    return {"schema":"artin_13_per_bar_tri_state_bridge_v1","source_rows":len(bars),
            "routes":[{"route_id":r,"source_identity":evidence.get("route_source_identity",{}).get(r),"source_identity_status":("SOURCE_IDENTITY_CONFLICT_REQUIRES_ORIGINAL_AV" if r in source_conflicts else "SOURCE_IDENTITY_MATCH_UNVERIFIED" if r in evidence.get("route_source_identity",{}) else "SOURCE_IDENTITY_UNAVAILABLE"),"states":dict(counts[r]),"side_decisions":{side:{"states":dict(side_counts[r][side]),"trade_permitted":False} for side in ("BUY","SELL")},"first_bar_example":examples[r]} for r in REQUIRED],
            "total_route_bar_evaluations":len(bars)*len(REQUIRED),
            "independent_engine":{"fingerprint":engine.fingerprint,"evaluations":len(bars)*len(REQUIRED)*2,"route_statuses":{r:dict(engine_statuses[r]) for r in REQUIRED},
                                  "route_reasons":{r:dict(engine_reasons[r]) for r in REQUIRED},"orders_created":0},
            "teacher_approved_entries":0,"trades_executed":0,"net_profit":None,
            "side_decision_evaluations":len(bars)*len(REQUIRED)*2,
            "causal_close_clock_checked":as_of is not None,
            "source_identity_conflicts":source_conflicts,
            "evidence_gate":{"decision":evidence["decision"],"reason":evidence["reason"],
                             "trade_authorized":False},
            "note":"Unknown teacher conditions are not inferred from candle geometry."}

if __name__=="__main__":
    dossier=json.load(open(sys.argv[3],encoding="utf-8")) if len(sys.argv)>3 else None
    result=evaluate(sys.argv[1], dossier)
    with open(sys.argv[2],"w") as f:json.dump(result,f,indent=2)
    print(json.dumps({"rows":result["source_rows"],"route_bar_evaluations":result["total_route_bar_evaluations"],"teacher_approved_entries":0}))
