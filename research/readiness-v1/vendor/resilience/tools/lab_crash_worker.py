"""Controlled child process for kill/restart tests of the synthetic lab only.

The test parent owns and kills this process handle. A ready marker means the
named cut point was reached; it is not a test of physical power loss.
"""
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
import argparse
import json
import os
import platform
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from faraz_core.authorization import authorize_entry, pin_policy
from faraz_core.execution import BrokerEvent, DemoBinding, MockBroker, Phase, intent_from_authorization, replay
from tests.test_decision import fixture
from faraz_lab.durable import DurableExecutor


SEED = 41207
ZERO = Decimal("0")


def scenario(seed=SEED):
    context, request = fixture()
    context = replace(context, signal_id=f"process-lab-signal-{seed}",
                      daily_loss_limit="100", total_loss_limit="200")
    request = replace(request, risk_budget="27.50")
    policy = pin_policy(context, request)
    authorization = authorize_entry(context, request, 2000)
    intent = intent_from_authorization(authorization, policy)
    binding = DemoBinding(context.account_key, context.account_revision,
                          policy=policy, budget_epoch_id="process-lab-epoch", epoch_risk_limit="30")
    fill = BrokerEvent("process-lab-fill", intent.client_intent_id, 1, "FILL", intent.account_id,
                       intent.account_revision, ".03", "process-lab-order", "process-lab-entry-deal",
                       "process-lab-position")
    close = BrokerEvent("process-lab-close", intent.client_intent_id, 2, "CLOSE", intent.account_id,
                        intent.account_revision, deal_id="process-lab-close-deal",
                        position_id="process-lab-position", authoritative=True, terminal_proof=True,
                        close_volume=".01", realized_pnl="-2.10", net_costs_confirmed=True,
                        cost_evidence_id="process-lab-close-cost", close_order_id="process-lab-close-order",
                        net_pnl_provenance="SYNTHETIC_CONFIRMED_NET", budget_epoch_id="process-lab-epoch")
    return binding, authorization, intent, fill, close


def metrics(state):
    known, unknown, unfilled_margin = ZERO, ZERO, ZERO
    with localcontext() as context:
        context.prec = 128
        for record in state.intents:
            if not record.reservation_made:
                continue
            live = record.filled_volume - record.closed_volume
            unfilled = ZERO if record.terminal_status else record.intent.volume - record.filled_volume
            model = record.intent.authorization.request.model
            per_lot = record.intent.entry_price * Decimal(model.contract_size)
            known += live * per_lot
            if record.phase == Phase.RESERVED:
                known += unfilled * per_lot
            else:
                unknown += unfilled * per_lot
            unfilled_margin += unfilled * Decimal(model.margin_per_lot)
    trace = []
    for entry in state.trace:
        row = {"operation": entry.operation}
        if entry.operation == "apply_event":
            event = entry.arguments[0]
            row.update(event_kind=event.kind, event_id=event.event_id, sequence=event.sequence)
        trace.append(row)
    return {"open_risk": str(state.ledger.open_risk),
            "reserved_risk": str(state.ledger.reserved_risk),
            "unknown_risk": str(state.ledger.unknown_risk),
            "held_risk": str(state.ledger.total),
            "known_notional": str(known), "unknown_notional": str(unknown),
            "unfilled_margin": str(unfilled_margin),
            "charged_loss": str(state.budget.realized_loss),
            "epoch": state.budget.epoch_id, "epoch_limit": str(state.budget.risk_limit),
            "durable_attempt_markers": len(state.requests),
            "phases": [record.phase.value for record in state.intents],
            "current_stop_observations": sum(record.protection.observation_current for record in state.intents),
            "quarantined_events": len(state.quarantined),
            "replay_equal": replay(state.trace) == state, "recovery_trace": trace}


def write_marker(path, record):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def run(args):
    binding, authorization, intent, fill, close = scenario(args.seed)
    broker = MockBroker((fill, close))
    holder = {}
    occurrences = {}

    def hook(label):
        occurrences[label] = occurrences.get(label, 0) + 1
        if label != args.cut or occurrences[label] != args.occurrence:
            return
        write_marker(args.marker, {
            "seed": args.seed, "cut_point": label, "occurrence": occurrences[label],
            "python": platform.python_version(), "actual_mock_attempts": len(broker.attempted),
            "committed_state": metrics(holder["executor"].state),
            "fault_model": "actual_process_termination_not_hardware_power_loss"})
        while True:
            time.sleep(.02)

    executor = DurableExecutor.create(args.journal, binding, cut_hook=hook)
    holder["executor"] = executor
    try:
        executor.transition("propose", intent)
        executor.transition("approve", intent.client_intent_id, intent.requested_risk)
        executor.transition("reserve", intent.client_intent_id, "30", "30")
        executor.send(broker, intent.client_intent_id, authorization, 1000)
        if args.observe_stop:
            executor.transition("observe_stop", intent.client_intent_id, "3995", True)
        result = metrics(executor.state)
        result.update(seed=args.seed, actual_mock_attempts=len(broker.attempted),
                      python=platform.python_version(), mode="completed")
        print(json.dumps(result, sort_keys=True))
    finally:
        executor.close()


def recover(args):
    binding, authorization, intent, fill, close = scenario(args.seed)
    executor = DurableExecutor.open(args.journal, binding=binding)
    broker = MockBroker()
    try:
        before = metrics(executor.state)
        duplicate_loss = None
        conflicting_close_rejected = None
        if args.exercise_events:
            executor.transition("apply_event", close)
            executor.transition("apply_event", replace(close, event_id="process-lab-repeat-close", sequence=3))
            duplicate_loss = str(executor.state.budget.realized_loss)
            try:
                executor.transition("apply_event", replace(close, realized_pnl="-99"))
            except ValueError as error:
                conflicting_close_rejected = str(error)
            else:
                raise AssertionError("Conflicting close was accepted")
            executor.transition("apply_event", replace(fill, event_id="process-lab-late-fill",
                                                        cumulative_filled=Decimal(".04"),
                                                        deal_id="process-lab-late-entry-deal"))
        try:
            executor.send(broker, intent.client_intent_id, authorization, 1000)
        except ValueError as error:
            resend_rejection = str(error)
        else:
            raise AssertionError("Recovered request reached mock again")
        result = metrics(executor.state)
        result.update(seed=args.seed, python=platform.python_version(), mode="fresh_process_recovery",
                      actual_mock_attempts=len(broker.attempted), before_event_exercise=before,
                      resend_rejection=resend_rejection,
                      duplicate_close_charged_loss=duplicate_loss,
                      conflicting_close_rejection=conflicting_close_rejected)
        print(json.dumps(result, sort_keys=True))
    finally:
        executor.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "recover"))
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--marker", type=Path)
    parser.add_argument("--cut", default="none")
    parser.add_argument("--occurrence", type=int, default=1)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--exercise-events", action="store_true")
    parser.add_argument("--observe-stop", action="store_true")
    args = parser.parse_args()
    if args.cut != "none" and args.marker is None:
        parser.error("A marker is required for a paused cut point")
    if args.occurrence < 1:
        parser.error("Occurrence must be positive")
    if args.mode == "run":
        run(args)
    else:
        recover(args)


if __name__ == "__main__":
    main()
