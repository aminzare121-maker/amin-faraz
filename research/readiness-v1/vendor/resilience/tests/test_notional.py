"""Independent numeric regressions for synthetic pre-send commitment accounting."""
from dataclasses import replace
from decimal import Decimal
import unittest

from faraz_core.authorization import authorize_entry, pin_policy
from faraz_core.decision import decide_entry
from faraz_core.execution import (
    BrokerEvent, DemoBinding, MemoryExecutor, MockBroker, Phase, apply_event,
    approve, intent_from_authorization, propose, replay, reserve,
    send_synthetic, start, timeout,
)
from faraz_core.risk import ExposureAmount
from tests.test_decision import fixture


D = Decimal


class NotionalCommitmentTests(unittest.TestCase):
    def seed(self, phase="RESERVED", cap="10000"):
        context, request = fixture()
        self.context = replace(context, signal_id="notional-first",
                               daily_loss_limit="100", total_loss_limit="200",
                               max_positions_and_pending=10)
        self.request = replace(request, notional_cap=cap)
        authorization = authorize_entry(self.context, self.request, 2000)
        policy = pin_policy(self.context, self.request)
        self.first = intent_from_authorization(authorization, policy)
        state = start(DemoBinding(self.context.account_key, 0, policy=policy,
                                 budget_epoch_id="notional-fixed-epoch", epoch_risk_limit="30"))
        state = self.add(state, authorization)
        if phase != "RESERVED":
            state = send_synthetic(state, self.first.client_intent_id, authorization, 1000)
        if phase == "UNKNOWN":
            state = timeout(state, self.first.client_intent_id)
        if phase in ("FILLED", "PARTIAL", "CANCELLED_PARTIAL", "CLOSED"):
            amount = ".004" if phase in ("PARTIAL", "CANCELLED_PARTIAL") else ".01"
            state = apply_event(state, self.event("first-fill", 1, "FILL", amount,
                                                 deal_id="first-entry-deal",
                                                 position_id="first-position"))
        if phase == "CANCELLED_PARTIAL":
            state = apply_event(state, self.event("first-cancel", 2, "CANCELLED", ".004",
                                                 terminal_proof=True))
        if phase == "CLOSED":
            state = apply_event(state, self.event(
                "first-close", 2, "CLOSE", None, deal_id="first-close-deal",
                position_id="first-position", close_volume=".01", realized_pnl="0",
                terminal_proof=True, authoritative=True, net_costs_confirmed=True,
                close_order_id="first-close-order", cost_evidence_id="first-net-cost",
                net_pnl_provenance="SYNTHETIC_CONFIRMED_NET",
                budget_epoch_id="notional-fixed-epoch"))
        return state

    def event(self, key, sequence, kind, amount, **fields):
        return BrokerEvent(key, self.first.client_intent_id, sequence, kind,
                           self.context.account_key, 0, cumulative_filled=amount,
                           order_id="first-order", **fields)

    def add(self, state, authorization):
        intent = intent_from_authorization(authorization, state.binding.policy)
        state = propose(state, intent)
        state = approve(state, intent.client_intent_id, intent.requested_risk)
        return reserve(state, intent.client_intent_id, "30", "30")

    def snapshot(self, state, known="0", unknown="0", extra_margin=None,
                 free_margin="1000", side="BUY", symbol=None):
        """Supply correct risk/volume while controlling the reviewed money fields."""
        first = state.get(self.first.client_intent_id)
        open_volume = first.filled_volume - first.closed_volume
        unfilled = D("0") if first.terminal_status else self.first.volume - first.filled_volume
        rows = []
        if open_volume:
            rows.append(ExposureAmount(self.context.account_key, self.first.symbol,
                                       self.first.side, "POSITION", "first-position", open_volume))
        if unfilled:
            rows.append(ExposureAmount(self.context.account_key, self.first.symbol,
                                       self.first.side, "PENDING", "first-unfilled", unfilled))
        context = replace(self.context, signal_id="notional-second", signal_side=side,
                          positions_and_pending=int(bool(open_volume + unfilled)))
        request = replace(self.request, exposures=tuple(rows), side=side,
                          held_risk=first.ledger.open_risk + first.ledger.reserved_risk,
                          held_unknown_risk=first.ledger.unknown_risk,
                          held_notional=known, held_unknown_notional=unknown,
                          held_unknown_margin=(unfilled * D("1000") if extra_margin is None
                                               else extra_margin),
                          available_margin=free_margin)
        if side == "SELL":
            request = replace(request, entry="4000", stop="4005.20")
        if symbol is not None:
            context = replace(context, quote_symbol=symbol)
            request = replace(request, symbol=symbol)
        return context, request

    def send_second(self, state, context, request):
        authorization = authorize_entry(context, request, 2000)
        state = self.add(state, authorization)
        executor = MemoryExecutor(trace=state.trace)
        broker = MockBroker()
        executor.send(broker, intent_from_authorization(authorization, state.binding.policy).client_intent_id,
                      authorization, 1000)
        self.assertEqual(len(broker.attempted), 1)
        self.assertEqual(replay(executor.state.trace), executor.state)
        return executor.state

    def reject_second(self, state, context, request, reason):
        # The supplied snapshot itself allows the second proposal. Rejection
        # must therefore come from independent executor reconciliation.
        self.assertEqual(decide_entry(context, request).action, "ENTRY_PROPOSAL")
        authorization = authorize_entry(context, request, 2000)
        state = self.add(state, authorization)
        executor = MemoryExecutor(trace=state.trace)
        broker = MockBroker()
        previous = executor.state
        with self.assertRaisesRegex(ValueError, reason):
            executor.send(broker, intent_from_authorization(authorization, state.binding.policy).client_intent_id,
                          authorization, 1000)
        self.assertIs(executor.state, previous)
        self.assertEqual(broker.attempted, ())
        self.assertEqual(replay(executor.state.trace), executor.state)

    def test_cap6000_zero_notional_cannot_hide_first_reserved_open_or_unknown(self):
        for phase in ("RESERVED", "FILLED", "UNKNOWN"):
            with self.subTest(phase=phase):
                state = self.seed(phase, cap="6000")
                # Each .01 * 100 * 4000.20 = 4000.20, total8000.40 >6000.
                self.assertEqual(self.first.volume * D("100") * self.first.entry_price, D("4000.20"))
                self.reject_second(state, *self.snapshot(state),
                                   "FRESH_SNAPSHOT_UNDERREPORTS_HELD_NOTIONAL")

    def test_honest_cap6000_snapshot_vetoes_second_proposal(self):
        state = self.seed("FILLED", cap="6000")
        context, request = self.snapshot(state, known="4000.20")
        decision = decide_entry(context, request)
        self.assertEqual(decision.action, "NO_TRADE")
        self.assertIn("NOTIONAL_CAP", decision.reasons)

    def test_known_and_unknown_notional_cannot_offset_each_other(self):
        for phase, known, unknown in (("RESERVED", "0", "4000.20"),
                                      ("UNKNOWN", "4000.20", "0")):
            with self.subTest(phase=phase):
                state = self.seed(phase)
                self.reject_second(state, *self.snapshot(state, known, unknown),
                                   "FRESH_SNAPSHOT_UNDERREPORTS_HELD_NOTIONAL")

    def test_correct_reserved_and_unknown_snapshots_send_without_counting_current_reserve(self):
        for phase, known, unknown in (("RESERVED", "4000.20", "0"),
                                      ("UNKNOWN", "0", "4000.20")):
            with self.subTest(phase=phase):
                state = self.seed(phase)
                result = self.send_second(state, *self.snapshot(state, known, unknown,
                                                                free_margin="20"))
                self.assertEqual(len(result.requests), 1 if phase == "RESERVED" else 2)

    def test_partial_fill_requires_both_notional_slices_and_only_unfilled_extra_margin(self):
        state = self.seed("PARTIAL")
        # .004 open =>1600.08; .006 unresolved =>2400.12 and margin6.
        self.reject_second(state, *self.snapshot(state, "1600.08", "0", free_margin="16"),
                           "FRESH_SNAPSHOT_UNDERREPORTS_HELD_NOTIONAL")
        result = self.send_second(state, *self.snapshot(state, "1600.08", "2400.12",
                                                        free_margin="16"))
        self.assertEqual(result.get(self.first.client_intent_id).filled_volume, D(".004"))

    def test_unfilled_margin_cannot_be_reported_as_zero_even_when_notional_is_complete(self):
        for phase, known, unknown in (("RESERVED", "4000.20", "0"),
                                      ("UNKNOWN", "0", "4000.20")):
            with self.subTest(phase=phase):
                state = self.seed(phase)
                self.reject_second(state, *self.snapshot(state, known, unknown,
                                                          extra_margin="0", free_margin="10"),
                                   "FRESH_SNAPSHOT_UNDERREPORTS_UNRESOLVED_MARGIN")

    def test_confirmed_open_margin_is_not_deducted_from_free_margin_twice(self):
        state = self.seed("FILLED")
        # Opening margin10 is already absent from reported free10; new10 fits.
        result = self.send_second(state, *self.snapshot(state, known="4000.20",
                                                        extra_margin="0", free_margin="10"))
        self.assertEqual(len(result.requests), 2)

    def test_confirmed_cancel_releases_only_unfilled_notional_and_margin(self):
        state = self.seed("CANCELLED_PARTIAL")
        self.assertEqual(state.get(self.first.client_intent_id).terminal_status, "CANCELLED")
        self.reject_second(state, *self.snapshot(state),
                           "FRESH_SNAPSHOT_UNDERREPORTS_HELD_NOTIONAL")
        self.send_second(state, *self.snapshot(state, known="1600.08",
                                               extra_margin="0", free_margin="10"))

    def test_confirmed_close_releases_notional_without_leaving_phantom_margin(self):
        state = self.seed("CLOSED", cap="6000")
        self.assertEqual(state.get(self.first.client_intent_id).closed_volume, D(".01"))
        self.send_second(state, *self.snapshot(state, extra_margin="0", free_margin="10"))

    def test_opposite_side_or_other_symbol_never_nets_away_prior_notional(self):
        for fields in ({"side": "SELL"}, {"symbol": "SECOND.SYNTHETIC"}):
            with self.subTest(fields=fields):
                state = self.seed("FILLED", cap="6000")
                self.reject_second(state, *self.snapshot(state, **fields),
                                   "FRESH_SNAPSHOT_UNDERREPORTS_HELD_NOTIONAL")

if __name__ == "__main__":
    unittest.main()
