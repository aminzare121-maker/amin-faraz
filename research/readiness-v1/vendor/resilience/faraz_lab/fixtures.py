"""Fresh synthetic inputs and exact numeric evidence; no legacy/account data."""
from dataclasses import replace
from decimal import Decimal, localcontext
from faraz_core.authorization import authorize_entry, pin_policy
from faraz_core.execution import DemoBinding, BrokerEvent, intent_from_authorization, Phase
from tests.test_decision import fixture


def scenario():
    context, request = fixture()
    context = replace(context, signal_id="lab-synthetic-signal", daily_loss_limit="100",
                      total_loss_limit="200", max_positions_and_pending=10)
    request = replace(request, risk_budget="27.50")
    authorization = authorize_entry(context, request, 2000)
    policy = pin_policy(context, request)
    binding = DemoBinding(context.account_key, context.account_revision, policy=policy,
                          budget_epoch_id="lab-synthetic-epoch", epoch_risk_limit="30")
    return authorization, binding, intent_from_authorization(authorization, policy)


def reserve_intent(executor, authorization):
    intent = intent_from_authorization(authorization, executor.state.binding.policy)
    executor.transition("propose", intent)
    executor.transition("approve", intent.client_intent_id, intent.requested_risk)
    executor.transition("reserve", intent.client_intent_id, "30", "30")
    return intent


def fill_event(intent):
    return BrokerEvent("lab-fill", intent.client_intent_id, 1, "FILL", intent.account_id,
                       intent.account_revision, ".03", "lab-order", "lab-entry-deal", "lab-position")


def close_event(intent):
    return BrokerEvent("lab-close", intent.client_intent_id, 2, "CLOSE", intent.account_id,
                       intent.account_revision, deal_id="lab-close-deal", position_id="lab-position",
                       terminal_proof=True, authoritative=True, close_volume=".01", realized_pnl="-2.10",
                       budget_epoch_id="lab-synthetic-epoch", net_costs_confirmed=True,
                       cost_evidence_id="lab-close-cost", close_order_id="lab-close-order",
                       net_pnl_provenance="SYNTHETIC_CONFIRMED_NET")


def summary(state):
    known_notional = Decimal(0)
    unknown_notional = Decimal(0)
    extra_margin = Decimal(0)
    with localcontext() as precision:
        precision.prec = 128
        for record in state.intents:
            if not record.reservation_made:
                continue
            request = record.intent.authorization.request
            open_volume = record.filled_volume - record.closed_volume
            unfilled = Decimal(0) if record.terminal_status else record.intent.volume - record.filled_volume
            unit = record.intent.entry_price * Decimal(request.model.contract_size)
            known_notional += open_volume * unit
            if record.phase == Phase.RESERVED:
                known_notional += unfilled * unit
            else:
                unknown_notional += unfilled * unit
            extra_margin += unfilled * Decimal(request.model.margin_per_lot)
    return {"open_risk": str(state.ledger.open_risk),
            "reserved_risk": str(state.ledger.reserved_risk),
            "unknown_risk": str(state.ledger.unknown_risk),
            "known_notional": str(known_notional), "unknown_notional": str(unknown_notional),
            "unfilled_margin": str(extra_margin), "charged_loss": str(state.budget.realized_loss),
            "epoch": state.budget.epoch_id, "epoch_limit": str(state.budget.risk_limit),
            "durable_attempt_markers": len(state.requests), "trace_operations": [x.operation for x in state.trace]}
