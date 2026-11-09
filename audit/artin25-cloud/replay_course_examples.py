"""Replay arithmetic observed in course notes; never place orders or certify meaning."""
import json
from decimal import Decimal as D, ROUND_FLOOR

def floor_step(value, step):
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step

def evaluate():
    cases = []
    def check(name, actual, expected, lesson, evidence):
        ok = actual == expected
        cases.append(dict(id=name, actual=str(actual), expected=str(expected), passed=ok,
                          lesson=lesson, evidence=evidence, independent_blind_test=False))
        if not ok: raise AssertionError(name)
    # Direct calculator/board values; point-to-money conversion is deliberately NOT generalized.
    check("risk_1000_at_2pct", D(1000)*D(".02"), D(20),24,"CASE24:1197.86")
    check("example_20_div_133_floor_001",floor_step(D(20)/D(133),D(".01")),D(".15"),24,"CASE24:1197.86")
    check("reward20_risk10",D(20)/D(10),D(2),24,"CASE24:2963.84")
    check("fib_target_coordinate_1_8",D("1.8")-D(1),D(".8"),24,"CASE24:1468.22")
    check("target13_initial_risk10",D(13)/D(10),D("1.3"),24,"CASE24:2431..2541")
    check("reduced_sl_not_partial_close",D(10)-D(5),D(5),24,"CASE24:2431..2541")
    check("16_at_08_exact",D(16)*D(".8"),D("12.8"),25,"CASE25:838.16/997.14")
    check("16_at_08_not_exact13",D(16)*D(".8") != D(13),True,25,"CASE25:teacher approximation")
    check("low_lot_example_reject",D(10)/D(2460) < D(".01"),True,25,"CASE25:2534..2618")
    check("lot_30_div_2460_floor",floor_step(D(30)/D(2460),D(".01")),D(".01"),25,"CASE25:2689..2718/2893.12")
    check("box_dd_30pct",D(1000)*(D(1)-D(".30")),D(700),25,"CASE25:3289.8/3400.24")
    check("daily_dd_3pct",D(1000)*D(".03"),D(30),25,"CASE25:3757..3864")
    check("profit5_more_than_dd3",D(".05") > D(".03"),True,25,"CASE25:4220..4312")
    check("withdraw_example",D(1050)-D(50),D(1000),25,"CASE25:4315..4754; no withdrawal executed")
    check("three_buy_below_half",D("4797.12") < D("4803.21"),True,19,"expanded:3668/3680/3695")
    check("star_sell_above_leg_half",D("4972.22") > D(4960),True,19,"expanded:4430/4468; visual approximate line")
    check("star_sell_below_first_body_half",D("4972.22") < D(4989),True,19,"expanded:4430/4468; unresolved ASR contradiction")
    # These checks validate arithmetic/fidelity observations, NOT semantic approval or an entry engine.
    return dict(schema="artin_course_example_replay_v1", tests=cases,
                passed=sum(x["passed"] for x in cases), orders_placed=0,
                engine_ready=False, semantic_verified_sessions=0,
                direct_listening=False, blind_source_conformance_complete=False,
                limitations=["No OHLC-independent market replay","Broker contract/point conversion not validated",
                             "ASR StarSELL below/above disagreement unresolved","Full trading tree deferred by teacher"])
if __name__ == "__main__":
    result = evaluate()
    with open("course_example_replay_result.json","w",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ("passed","orders_placed","engine_ready","semantic_verified_sessions")}))
