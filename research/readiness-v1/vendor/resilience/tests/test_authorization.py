"""Logical authorization regressions using supplied synthetic observations only."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import unittest

from faraz_core.authorization import (
    DECISION_VERSION, EntryAuthorization, authorize_entry, pin_policy,
    validate_authorization, validate_fresh_authorization,
)
from faraz_core.decision import EntryContext
from faraz_core.risk import LinearRiskModel, RiskRequest, VolumeRules
from faraz_core.temporal import Quote


def authorization_fixture():
    request = RiskRequest(
        "synthetic-account", "SYNTH", "BUY", "4000.20", "3995", "10",
        VolumeRules(".01", ".01", "1", "2"),
        LinearRiskModel("100", "10", "10", "10", "0", "1000"),
        (), "1000", "100000", "30", "0", "0", "0", "0", "0",
    )
    context = EntryContext(
        1000, "synthetic-account", "synthetic-account", 1, 1, "DEMO", "USD",
        "HEDGING", True, True, True, True, 1000, True, 1000, True, 1000, 1000,
        Quote(1000, 1000, "4000", "4000.20"), "signal-1", 1000, "BUY", "policy-1",
        ".01", "0", ".50", "0", "20", "0", "50", 0, 2, "SYNTH", 1, 1000,
    )
    return context, request


def refreshed(context, now=1100, **changes):
    values = dict(decision_ms=now, account_observed_ms=now, session_available_ms=now,
                  news_available_ms=now, signal_available_ms=now, risk_observed_ms=now,
                  quote=Quote(now, now, context.quote.bid, context.quote.ask))
    values.update(changes)
    return replace(context, **values)


class AuthorizationTests(unittest.TestCase):
    def test_valid_authorization_recomputes_deterministic_original_decision(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        authorization = authorize_entry(context, request, 1500)
        decision = validate_authorization(authorization, pin, 1100)
        self.assertEqual(decision.action, "ENTRY_PROPOSAL")
        self.assertEqual(decision.risk.volume, Decimal(".01"))
        self.assertEqual(decision.risk.risk, Decimal("5.5"))
        self.assertEqual(decision, validate_authorization(authorization, pin))
        self.assertEqual(authorization.decision_version, DECISION_VERSION)
        with self.assertRaises(FrozenInstanceError):
            authorization.expires_ms = 999999

    def test_forged_no_trade_inputs_cannot_be_used_as_authorization(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        for changes in ({"signal_side": None}, {"connected": False},
                        {"session_open": False}, {"daily_loss": "20"}):
            context_bad = replace(context, **changes)
            forged = EntryAuthorization(context_bad, request, 1500)
            with self.assertRaisesRegex(ValueError, "AUTHORIZATION_NO_TRADE"):
                validate_authorization(forged, pin)
            with self.assertRaisesRegex(ValueError, "AUTHORIZATION_NO_TRADE"):
                authorize_entry(context_bad, request, 1500)

    def test_policy_hash_does_not_authorize_changed_hidden_limits(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        for changes in ({"max_age_ms": 9999}, {"price_tick": ".001"},
                        {"minimum_stop_distance": "1"}, {"max_spread": "9"},
                        {"daily_loss_limit": "200"}, {"total_loss_limit": "500"},
                        {"max_positions_and_pending": 99}):
            changed = replace(context, **changes)
            authorization = EntryAuthorization(changed, request, 1500)
            self.assertEqual(changed.policy_hash, pin.policy_hash)
            with self.assertRaisesRegex(ValueError, "PINNED_POLICY_MISMATCH"):
                validate_authorization(authorization, pin)

    def test_policy_pins_volume_rules_cost_model_and_all_budget_caps(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        variants = (
            replace(request, rules=replace(request.rules, maximum="10")),
            replace(request, rules=replace(request.rules, volume_limit="20")),
            replace(request, model=replace(request.model, gap_reserve_per_lot="1")),
            replace(request, risk_budget="100"),
            replace(request, notional_cap="1000000"),
            replace(request, portfolio_risk_cap="300"),
        )
        for variant in variants:
            with self.assertRaisesRegex(ValueError, "PINNED_POLICY_MISMATCH"):
                validate_authorization(EntryAuthorization(context, variant, 1500), pin)

    def test_policy_numeric_equivalence_is_not_a_textual_bypass(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        equivalent_context = replace(context, max_spread=Decimal("0.5000"), price_tick=Decimal(".01"))
        equivalent_request = replace(request, risk_budget=Decimal("10.0"))
        self.assertEqual(pin_policy(equivalent_context, equivalent_request), pin)

    def test_unknown_algorithm_version_is_refused(self):
        context, request = authorization_fixture()
        forged = EntryAuthorization(context, request, 1500, "unreviewed-v2")
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_DECISION_VERSION"):
            validate_authorization(forged, pin_policy(context, request))

    def test_expiry_and_future_authorization_are_fail_closed(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        authorization = authorize_entry(context, request, 1100)
        validate_authorization(authorization, pin, 1100)
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_EXPIRED"):
            validate_authorization(authorization, pin, 1101)
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_FROM_FUTURE"):
            validate_authorization(authorization, pin, 999)
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_ALREADY_EXPIRED"):
            EntryAuthorization(context, request, 999)

    def test_expiry_cannot_make_stale_observations_current(self):
        context, request = authorization_fixture()
        authorization = authorize_entry(context, request, 10000)
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_RECHECK_NO_TRADE"):
            validate_authorization(authorization, pin_policy(context, request), 2001)

    def test_fresh_recheck_uses_semantics_not_a_new_time_payload_hash(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        original = authorize_entry(context, request, 1500)
        fresh = authorize_entry(refreshed(context), request, 1500)
        original_decision = validate_authorization(original, pin)
        fresh_decision = validate_fresh_authorization(original, fresh, pin, 1100)
        self.assertEqual(original_decision.client_intent_id, fresh_decision.client_intent_id)
        self.assertNotEqual(original_decision.payload_hash, fresh_decision.payload_hash)
        self.assertEqual(original_decision.risk.volume, fresh_decision.risk.volume)

    def test_later_fresh_authorization_cannot_extend_original_expiry(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        original = authorize_entry(context, request, 1050)
        fresh = authorize_entry(refreshed(context), request, 1500)
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_EXPIRED"):
            validate_fresh_authorization(original, fresh, pin, 1100)

    def test_fresh_price_or_stop_change_cannot_silently_rewrite_intent(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        original = authorize_entry(context, request, 1500)
        changed_context = refreshed(context, quote=Quote(1100, 1100, "4000", "4000.21"))
        changed_request = replace(request, entry="4000.21", stop="3995.01")
        fresh = authorize_entry(changed_context, changed_request, 1500)
        with self.assertRaisesRegex(ValueError, "FRESH_AUTHORIZATION_INTENT_CHANGED"):
            validate_fresh_authorization(original, fresh, pin, 1100)

    def test_fresh_signal_or_account_revision_change_is_refused(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        original = authorize_entry(context, request, 1500)
        for changes in ({"signal_id": "other-signal"},
                        {"account_revision": 2, "bound_account_revision": 2, "risk_account_revision": 2}):
            fresh = authorize_entry(refreshed(context, **changes), request, 1500)
            with self.assertRaisesRegex(ValueError, "FRESH_AUTHORIZATION_IDENTITY_CHANGED"):
                validate_fresh_authorization(original, fresh, pin, 1100)

    def test_explicit_current_time_cannot_be_omitted_or_faked_by_old_snapshot(self):
        context, request = authorization_fixture()
        pin = pin_policy(context, request)
        original = authorize_entry(context, request, 1500)
        with self.assertRaisesRegex(ValueError, "CURRENT_FRESH_AUTHORIZATION_REQUIRED"):
            validate_fresh_authorization(original, original, pin, 1100)

    def test_regressing_source_or_loss_counter_is_refused(self):
        context, request = authorization_fixture()
        context = replace(context, daily_loss="1", total_loss="2")
        pin = pin_policy(context, request)
        original = authorize_entry(context, request, 1500)
        variants = (
            refreshed(context, account_observed_ms=999),
            refreshed(context, quote=Quote(999, 1100, "4000", "4000.20")),
            refreshed(context, daily_loss="0"),
        )
        for fresh_context in variants:
            fresh = authorize_entry(fresh_context, request, 1500)
            with self.assertRaisesRegex(ValueError, "REGRESSION"):
                validate_fresh_authorization(original, fresh, pin, 1100)

    def test_mutable_nested_request_input_is_not_immutable_authorization(self):
        context, request = authorization_fixture()
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_AUTHORIZATION_INPUT_REQUIRED"):
            EntryAuthorization(context, replace(request, exposures=[]), 1500)
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_AUTHORIZATION_INPUT_REQUIRED"):
            EntryAuthorization(context, replace(request, model=replace(request.model, entry_cost_per_lot=[])), 1500)


if __name__ == "__main__":
    unittest.main()
