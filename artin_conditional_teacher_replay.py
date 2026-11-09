#!/usr/bin/env python3
"""Artin evidence-grounded *candidate* interpretation and counterfactual replay.

This is NOT independent acoustic verification, a certified teacher rule engine, MT5,
or a claim that a hypothetical case happened historically. The provenance is the
archived, unverified original-machine-ASR text with image references. All outputs
remain fail closed and contain no executable order. Original files stay private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

SHA_RE = re.compile(r"[a-f0-9]{64}\Z")

# These are manually reviewed readings of archived MACHINE ASR spans, not invented
# general-purpose market indicators. The `anchor_phrases` must be present verbatim
# within the source-linked five-span context; otherwise refuse to form a scenario.
# Input cases already contain source session/segment/audio/image SHA anchors.
SCENARIOS = {
    "A04-QUOTE-MECHANICS": {
        "anchor_phrases": ["معامله سلی که میگیری با بید شروع میشه", "معامله بایی که میگیری با اسک شروع میشه"],
        "meaning_candidate": "Sell uses Bid and Buy uses Ask as quoted price mechanics; not a trade trigger.",
        "rule_category": "CONCEPT_NOT_SIGNAL", "required_missing": ["speaker_audio_verification"],
    },
    "A12-CANDLE-BODY": {
        "anchor_phrases": ["بدنه های بزرگتر از سایه دارن"],
        "meaning_candidate": "Candle body vs shadow is explained, not an entry predicate.",
        "rule_category": "CONCEPT_NOT_SIGNAL", "required_missing": ["quantified_candle_pattern", "entry_context"],
    },
    "A13-WEAK-TREND-REVERSE": {
        "anchor_phrases": ["فقط اجازه گرفتن پوزیشن ریورس", "بعد از یک اصلاحی"],
        "meaning_candidate": "In weak trend the described permitted position is reversal, with a correction and an entry strategy to be taught later.",
        "rule_category": "CONDITIONAL_CONSTRAINT", "required_missing": ["weak_trend_operational_definition", "correction_definition", "future_entry_strategy"],
    },
    "A14-TREND-TYPES": {
        "anchor_phrases": ["رنج میزنه"],
        "meaning_candidate": "Up/down/range classification is explained, without precise automatic classifier.",
        "rule_category": "CONCEPT_NOT_SIGNAL", "required_missing": ["trend_classifier_thresholds", "timeframe"],
    },
    "A15-BREAKOUT-VS-PULLBACK": {
        "anchor_phrases": ["منتظر پول بک بمونی", "بعد از شکست بلا فاصله ورود کنی"],
        "meaning_candidate": "Some breakouts require waiting for pullback and some allow immediate entry, but the dividing test is not in this context.",
        "rule_category": "CONDITIONAL_BRANCH_INCOMPLETE", "required_missing": ["breakout_type_classifier", "chart_relevant_frame", "entry_confirmation"],
    },
    "A18-ENTRY-SCHEMATIC": {
        "anchor_phrases": ["من اگر میخواستم ورود بکنم"],
        "meaning_candidate": "A hypothetical chart entry is discussed; its full predicates and order execution are not established.",
        "rule_category": "CONDITIONAL_BRANCH_INCOMPLETE", "required_missing": ["entry_price", "entry_conditions", "stop_loss", "speaker_verification"],
    },
    "A19-PIERCING-EXAMPLE": {
        "anchor_phrases": ["این کارو نمی کنم ورود نمی کنم", "اگر اومد پیرسینگش کرد", "من اینجا ورود میکنم"],
        "meaning_candidate": "The teacher-text contrasts no entry before a condition versus entry mentioned after a piercing condition; neither a historical fill nor an algorithmic piercing definition.",
        "rule_category": "CONDITIONAL_CONSTRAINT", "required_missing": ["piercing_definition", "position_direction", "candle_trigger", "stop_loss", "risk_limit"],
    },
    "A21-STOP-BEHIND-LIQUIDITY": {
        "anchor_phrases": ["لیکویدیتی بوده", "استاپلاس خیلی خوبه", "ریسکش رو بپذیرم"],
        "meaning_candidate": "Illustrated stop relative to liquidity pivot and acceptance of risk is a location/risk concept, not a quantified risk strategy.",
        "rule_category": "RISK_CONCEPT", "required_missing": ["valid_pivot", "stop_buffer", "risk_budget"],
    },
    "A24-RR-ARITHMETIC": {
        "anchor_phrases": ["استاپلاست ده دولاره", "13 دولار"],
        "meaning_candidate": "A specific $10 risk and $13 reward example implies reward/risk=1.3; no universal minimum is licensed.",
        "rule_category": "ARITHMETIC_ONLY", "required_missing": ["universal_rr_policy_not_proven"],
    },
    "A25-TARGET2-RISKFREE": {
        "anchor_phrases": ["تارگیت دو", "استاپلاس رو ورداری بیاری", "به عنوان مثال دارم میگم"],
        "meaning_candidate": "Moving stop to break-even at target two is an educational example, not a universal trailing rule.",
        "rule_category": "ILLUSTRATIVE_RISK_CONCEPT", "required_missing": ["applicability_to_given_trade", "actual_target2", "commission_and_spread", "new_stop_price"],
    },
}

STATES = {
    "A04-QUOTE-MECHANICS": [{"side":"BUY"}, {"side":"SELL"}],
    "A12-CANDLE-BODY": [{"body":2,"shadow":1}],
    "A13-WEAK-TREND-REVERSE": [
        {"trend_regime":"weak","proposal":"WITH_TREND"},
        {"trend_regime":"weak","proposal":"REVERSAL","correction_seen":False},
        {"trend_regime":"weak","proposal":"REVERSAL","correction_seen":True},
        {"trend_regime":"unknown","proposal":"WITH_TREND"}],
    "A14-TREND-TYPES": [{"visible_trend":"range"}],
    "A15-BREAKOUT-VS-PULLBACK": [{"breakout_occurred":True,"proposal":"IMMEDIATE"},
                                  {"breakout_occurred":True,"proposal":"AFTER_PULLBACK"},
                                  {"breakout_occurred":False,"proposal":"IMMEDIATE"}],
    "A18-ENTRY-SCHEMATIC": [{"hypothetical_entry":True}],
    "A19-PIERCING-EXAMPLE": [{"piercing_condition_met":False,"proposal":"ENTER"},
                               {"piercing_condition_met":True,"proposal":"ENTER"},
                               {"piercing_condition_met":None,"proposal":"ENTER"}],
    "A21-STOP-BEHIND-LIQUIDITY": [{"liquidity_pivot_candidate":True}],
    "A24-RR-ARITHMETIC": [{"risk":10,"reward":13}, {"risk":0,"reward":13}],
    "A25-TARGET2-RISKFREE": [{"target2_reached":False,"proposal":"MOVE_STOP"},
                               {"target2_reached":True,"proposal":"MOVE_STOP"}],
}


def recheck_source(case: dict) -> dict:
    """Source-content condition, not semantic accuracy of the recorded words."""
    cid=case.get("case_id")
    spec=SCENARIOS.get(cid)
    if spec is None:raise ValueError(f"unexpected case {cid}")
    for k in ("source_audio_sha256","original_image_sha256"):
        v=case.get(k)
        if not isinstance(v,str) or SHA_RE.fullmatch(v) is None:
            raise ValueError(f"{cid} invalid {k}")
    if not isinstance(case.get("session"),int) or not 1<=case["session"]<=25:
        raise ValueError(f"{cid} invalid session")
    if not isinstance(case.get("speech_start_seconds"),(int,float)):
        raise ValueError(f"{cid} invalid speech time")
    ctx=case.get("machine_context")
    if not isinstance(ctx,list) or len(ctx)<3:raise ValueError(f"{cid} missing context")
    exact_texts=[r.get("text") for r in ctx]
    if any(not isinstance(t,str) for t in exact_texts):raise ValueError(f"{cid} invalid context")
    # The teacher's exact words are not asserted independently. Read recorded ASR only.
    joined=" ".join(exact_texts)
    not_found=[p for p in spec["anchor_phrases"] if p not in joined]
    if not_found:raise ValueError(f"{cid} missing anchor phrases {not_found}")
    if case.get("teacher_semantics_verified") is not False or case.get("historical_order_proven") is not False:
        raise ValueError(f"{cid} unsupported certification")
    return {"anchor_text_sha256":hashlib.sha256(joined.encode("utf8")).hexdigest(),
            "anchor_phrases":list(spec["anchor_phrases"])}


def symbolic_contrast(cid: str, state: dict) -> dict:
    """Explicit text-derived restrictions; NEVER returns live order action.

    A potential contradiction is with a *provisional wording interpretation*,
    not proof that the real instructor would reject a trade in the real market.
    """
    if cid not in SCENARIOS:raise ValueError("unknown case")
    if not isinstance(state,dict):raise TypeError("symbolic state must be object")
    label="CONCEPT_OR_MISSING_ENTRY_RULE"
    conflicts=False
    details=[]
    if cid=="A13-WEAK-TREND-REVERSE":
        if state.get("trend_regime")=="weak" and state.get("proposal")=="WITH_TREND":
            label="CONFLICTS_WITH_LITERAL_WEAK_TREND_REVERSAL_ONLY"
            conflicts=True
        elif state.get("trend_regime")=="weak" and state.get("proposal")=="REVERSAL":
            label="REVERSAL_MENTIONED_BUT_CORRECTION_AND_ENTRY_STRATEGY_NOT_OPERATIONAL"
        else:label="TREND_REGIME_NOT_ESTABLISHED"
    elif cid=="A15-BREAKOUT-VS-PULLBACK":
        label="UNKNOWN_BREAKOUT_BRANCH_CANNOT_AUTO_SELECT_ENTRY"
    elif cid=="A19-PIERCING-EXAMPLE":
        if state.get("piercing_condition_met") is False and state.get("proposal")=="ENTER":
            label="CONFLICTS_WITH_LITERAL_WAIT_FOR_PIERCING_EXAMPLE"
            conflicts=True
        elif state.get("piercing_condition_met") is True:
            label="ENTRY_DESCRIBED_IF_PIERCING_BUT_PARAMETERS_UNKNOWN"
        else:label="PIERCING_STATE_UNKNOWN"
    elif cid=="A24-RR-ARITHMETIC":
        risk,reward=state.get("risk"),state.get("reward")
        if type(risk) in (int,float) and type(reward) in (int,float) and math.isfinite(risk) and math.isfinite(reward) and risk>0 and reward>=0:
            details.append({"illustrative_reward_to_risk_ratio":round(reward/risk,8)})
            label="ARITHMETIC_ILLUSTRATION_NOT_MINIMUM_RR"
        else:label="INVALID_RISK_REWARD_EXAMPLE"
    elif cid=="A25-TARGET2-RISKFREE":
        label="BREAK_EVEN_CONDITIONAL_ILLUSTRATION_NOT_GENERAL_RULE" if state.get("target2_reached") is True else "TARGET2_NOT_REACHED_IN_EXAMPLE"
    return {"case_id":cid,"input_state":state,"text_candidate_result":label,
            "provisional_text_conflict":conflicts,
            "contextual_notes":details,
            "teacher_wording_audio_verified":False,
            "teacher_expected_action_certified":False,
            "motor_action_executed":False,
            "engine_matches_teacher_certified":False,
            "real_or_demo_order_permitted":False}


def compile_review(cases_path: Path) -> dict:
    cases=json.loads(Path(cases_path).read_text(encoding="utf8"))
    if len(cases)!=10 or len({c.get("case_id") for c in cases})!=10 or set(c.get("case_id") for c in cases)!=set(SCENARIOS):
        raise ValueError("expected 10 original teacher-context candidate IDs")
    ordered=sorted(cases,key=lambda c:(c["session"],c["speech_start_seconds"]))
    output=[]
    for c in ordered:
        anchored=recheck_source(c)
        spec=SCENARIOS[c["case_id"]]
        output.append({"case_id":c["case_id"],"session":c["session"],
                       "source_audio_sha256":c["source_audio_sha256"],
                       "source_image_sha256":c["original_image_sha256"],
                       "speech_start_seconds":c["speech_start_seconds"],
                       "original_source_segment_id":c.get("source_segment_id"),
                       "machine_quote_unverified":c["machine_quote"],
                       "source_context_text_sha256":anchored["anchor_text_sha256"],
                       "context_evidence_exact_phrases":anchored["anchor_phrases"],
                       "meaning_candidate_not_teacher_certified":spec["meaning_candidate"],
                       "rule_category":spec["rule_category"],
                       "requirements_before_certification":spec["required_missing"],
                       "example_hypothetical_permitted":True,
                       "historical_execution_proven":False,
                       "source_acoustic_wording_verified":False,
                       "teacher_role_verified":False,
                       "visual_meaning_reviewed_as_teacher_intent":False,
                       "decision_examples":[symbolic_contrast(c["case_id"],s) for s in STATES[c["case_id"]]],
                       "teacher_vs_motor_test_status":"BLOCKED_NO_INDEPENDENT_TEACHER_DECISION",
                       "trade_permission":False})
    return {"schema":"artin_ten_teacher_conditional_text_replay_v1",
            "session_count_with_cases":len(set(x["session"] for x in output)),
            "cases":output,"source_anchored_cases":len(output),
            "counterfactual_tests":sum(len(x["decision_examples"]) for x in output),
            "text_candidate_conflicts":sum(e["provisional_text_conflict"] for x in output for e in x["decision_examples"]),
            "teacher_audio_25_sessions_certified":False,
            "teacher_motor_decision_matches_certified":0,
            "validated_executable_rules":0,
            "automated_trading_allowed":False,
            "scope":"Source-anchored unverified machine text plus manually viewed original lesson screenshots; not independent listening to 25 original videos or live MT5 replays."}


def main():
    a=argparse.ArgumentParser();a.add_argument("private_cases",type=Path);a.add_argument("output",type=Path)
    args=a.parse_args()
    result=compile_review(args.private_cases)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({key:result[key] for key in ("source_anchored_cases","counterfactual_tests","text_candidate_conflicts","teacher_motor_decision_matches_certified","automated_trading_allowed")},ensure_ascii=False))
if __name__=="__main__":main()