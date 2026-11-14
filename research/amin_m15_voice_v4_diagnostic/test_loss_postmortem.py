#!/usr/bin/env python3
"""Standard-library tests for retrospective V4 loss diagnosis."""
import tempfile
import csv
import json
from pathlib import Path
import loss_postmortem as p

def run():
    sample = [
        {"decision_index":1, "exit_day_utc":"2026-01-02","event":"TARGET",
         "p_tp_calibrated":.4,"pnl_usd_assumed_fixed_001_lot":20},
        {"decision_index":2,"exit_day_utc":"2026-01-02","event":"STOP",
         "p_tp_calibrated":.4,"pnl_usd_assumed_fixed_001_lot":-10},
        {"decision_index":3,"exit_day_utc":"2026-01-05","event":"STOP",
         "p_tp_calibrated":.4,"pnl_usd_assumed_fixed_001_lot":-10},
    ]
    a=p.describe(sample)
    assert a["trades"]==3
    assert a["net_usd_assumed"]==0
    assert a["realized_payoff_break_even_win_rate"]==.3333
    assert a["win_rate"]==.3333
    assert a["worst_loss_streak"]==2
    assert a["tp_event_rate"]==.3333
    assert a["mean_predicted_tp_probability"]==.4
    assert p.wilson(0,0)==[None,None]
    assert p.loss_run([1,-2,-2,3,-1])==2
    assert p.decide(a,a,a)["strategy_approved"] is False
    with tempfile.TemporaryDirectory() as td:
        directory=Path(td)
        for part in p.PARTS:
            for view in p.SIDES:
                with (directory/f"{part}_{view}_trades.csv").open("w",encoding="utf-8",newline="") as f:
                    writer=csv.DictWriter(f,fieldnames=list(sample[0]))
                    writer.writeheader()
                    writer.writerows(sample)
        data=p.make_report(directory)
        assert len(data["blocks"])==3
        assert not data["decision"]["orders_allowed"]
        assert data["blocks"]["calibration"]["filtered"]["realized_payoff_break_even_win_rate"]==.3333
    print("POSTMORTEM_UNIT_TESTS_PASS")

if __name__=="__main__":
    run()
