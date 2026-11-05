"""Finite synthetic demonstration. Never starts a background service or terminal."""
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from faraz_core.decision import decide_entry
from faraz_core.authorization import authorize_entry, pin_policy
from faraz_core.execution import (DemoBinding, Intent, MemoryExecutor, MockBroker,
                                  BrokerEvent, replay, intent_from_authorization)
from faraz_core.money import open_lot, apply_cash_event, CashEvent, CloseDeal, close_lot
from faraz_core.exits import Position, MarketRules, compare_candidates
from faraz_core.temporal import Candle, Quote
from faraz_core.risk import ExposureAmount
from tests.test_decision import fixture


def notional_guard_trace():
    """Review regression: correct risk/volume cannot disguise omitted notional."""
    context, request = fixture()
    request = replace(request, notional_cap='6000')
    policy = pin_policy(context, request)
    original = authorize_entry(context, request, 2000)
    first = intent_from_authorization(original, policy)
    executor = MemoryExecutor(DemoBinding(context.account_key, context.account_revision,
                              policy=policy, budget_epoch_id='synthetic-notional-epoch',
                              epoch_risk_limit='20'))
    for operation, arguments in (
            ('propose', (first,)), ('approve', (first.client_intent_id, first.requested_risk)),
            ('reserve', (first.client_intent_id, '20', '20'))):
        executor.transition(operation, *arguments)
    fill = BrokerEvent('synthetic-notional-fill', first.client_intent_id, 1, 'FILL',
                       first.account_id, 0, '.01', 'synthetic-notional-order',
                       'synthetic-notional-deal', 'synthetic-notional-position')
    broker = MockBroker((fill,))
    executor.send(broker, first.client_intent_id, original, 1000)
    second_context = replace(context, signal_id='synthetic-notional-second',
                              positions_and_pending=1)
    second_request = replace(request, available_margin='990', held_risk='5.50',
                             exposures=(ExposureAmount(first.account_id, first.symbol,
                                         first.side, 'POSITION', 'synthetic-notional-position',
                                         '.01'),))
    second_auth = authorize_entry(second_context, second_request, 2000)
    second = intent_from_authorization(second_auth, policy)
    for operation, arguments in (
            ('propose', (second,)), ('approve', (second.client_intent_id, second.requested_risk)),
            ('reserve', (second.client_intent_id, '20', '20'))):
        executor.transition(operation, *arguments)
    before = executor.state
    try:
        executor.send(broker, second.client_intent_id, second_auth, 1000)
    except ValueError as error:
        rejection = str(error)
    else:
        raise AssertionError('Omitted held notional reached mock')
    assert rejection == 'FRESH_SNAPSHOT_UNDERREPORTS_HELD_NOTIONAL'
    assert executor.state == before and len(broker.attempted) == 1
    first_decision = decide_entry(context, request)
    honest = decide_entry(second_context,
                           replace(second_request, held_notional=first_decision.risk.notional))
    assert honest.action == 'NO_TRADE' and 'NOTIONAL_CAP' in honest.reasons
    assert replay(executor.state.trace) == executor.state
    return {'notional_cap': str(request.notional_cap),
            'first_committed_entry_notional': str(first_decision.risk.notional),
            'second_entry_notional': str(first_decision.risk.notional),
            'combined_notional': str(first_decision.risk.notional * 2),
            'reported_known_risk': str(second_request.held_risk),
            'reported_position_volume': '.01',
            'reported_known_notional': str(second_request.held_notional),
            'reported_unknown_notional': str(second_request.held_unknown_notional),
            'rejection': rejection, 'mock_attempts_after_rejection': len(broker.attempted),
            'honest_snapshot_action': honest.action, 'honest_snapshot_reasons': honest.reasons,
            'logical_replay_equal': True, 'evidence_source': 'OFFLINE_SYNTHETIC'}


def build_demo():
    context, request = fixture()
    proposal = decide_entry(context, request)
    assert proposal.action == 'ENTRY_PROPOSAL' and not proposal.can_execute
    policy = pin_policy(context, request)
    authorization = authorize_entry(context, request, 2000)
    executor = MemoryExecutor(DemoBinding(context.account_key, context.account_revision,
                              policy=policy, budget_epoch_id='synthetic-entry-epoch',
                              epoch_risk_limit='20'))
    intent = intent_from_authorization(authorization, policy)
    executor.transition('propose', intent)
    executor.transition('approve', intent.client_intent_id, proposal.risk.risk)
    executor.transition('reserve', intent.client_intent_id, '30', '30')
    mock = MockBroker(lose_response=True)
    executor.send(mock, intent.client_intent_id, authorization, context.decision_ms)
    unknown = executor.state.get(intent.client_intent_id)
    assert unknown.ledger.total == proposal.risk.risk
    duplicate_blocked = False
    try:
        executor.send(mock, intent.client_intent_id, authorization, context.decision_ms)
    except ValueError:
        duplicate_blocked = True
    recovered = replay(executor.state.trace)
    assert recovered == executor.state

    partial_context = replace(context, account_key='synthetic-partial-account',
                               bound_account_key='synthetic-partial-account',
                               signal_id='synthetic-partial-signal',
                               daily_loss_limit='100', total_loss_limit='200')
    partial_request = replace(request, account_id='synthetic-partial-account', risk_budget='27.50')
    partial_policy = pin_policy(partial_context, partial_request)
    partial_auth = authorize_entry(partial_context, partial_request, 2000)
    partial = MemoryExecutor(DemoBinding('synthetic-partial-account', 0,
                             policy=partial_policy, budget_epoch_id='synthetic-partial-epoch',
                             epoch_risk_limit='30'))
    partial_intent = intent_from_authorization(partial_auth, partial_policy)
    for name, args in [('propose', (partial_intent,)),
                       ('approve', (partial_intent.client_intent_id, '27.50')),
                       ('reserve', (partial_intent.client_intent_id, '30', '30'))]:
        partial.transition(name, *args)
    fill = BrokerEvent('synthetic-fill-event', partial_intent.client_intent_id, 1,
                       'FILL', partial_intent.account_id, 0, '.03',
                       'synthetic-order', 'synthetic-deal', 'synthetic-position')
    partial.send(MockBroker((fill,)), partial_intent.client_intent_id,
                 partial_auth, partial_context.decision_ms)
    partial_hold = partial.state.ledger
    assert partial_hold.open_risk == Decimal('16.50')
    assert partial_hold.unknown_risk == Decimal('11.00')

    # Only a complete synthetic cancellation clears the unfilled order slice.
    cancel = BrokerEvent('synthetic-cancel-event', partial_intent.client_intent_id, 2,
                         'CANCELLED', partial_intent.account_id, 0, '.03',
                         'synthetic-order', terminal_proof=True)
    partial.transition('apply_event', cancel)
    costed = apply_cash_event(open_lot('synthetic-filled-lot', 'BUY', '4000.20',
                                      '.03', '100', confirmed=True),
                             CashEvent('synthetic-entry-fee', 'ENTRY_FEE', '-.30', True))
    closed = close_lot(costed, CloseDeal('synthetic-close-deal', '.03', '3999.70', '-.30', True))
    close_event = BrokerEvent('synthetic-close-event', partial_intent.client_intent_id, 3,
                              'CLOSE', partial_intent.account_id, 0,
                              deal_id='synthetic-close-deal', position_id='synthetic-position',
                              authoritative=True, terminal_proof=True,
                              close_volume='.03', realized_pnl=closed.allocation.money.net,
                              budget_epoch_id='synthetic-partial-epoch', net_costs_confirmed=True,
                              cost_evidence_id='synthetic-cost-allocation',
                              close_order_id='synthetic-close-order',
                              net_pnl_provenance='SYNTHETIC_CONFIRMED_NET')
    partial.transition('apply_event', close_event)
    assert partial.state.ledger.total == 0
    assert partial.state.budget.realized_loss == Decimal('2.10')
    assert replay(partial.state.trace) == partial.state

    fill_ms = 15 * 900000
    candles = tuple(Candle(i * 900000, 900000, (i + 1) * 900000,
                           '100', '101', '99', '100') for i in range(15))
    quotes = tuple(Quote(fill_ms + offset, fill_ms + offset, bid, ask)
                   for offset, bid, ask in [(100,'111','111.2'), (200,'110','110.2'),
                                            (300,'104','104.2'), (400,'103','103.2'),
                                            (3600100,'102','102.2')])
    results = compare_candidates(Position('buy','100','1','95','5.2','.2'), quotes,
                                 fill_ms, MarketRules(), candles)
    return {
        'scope': 'synthetic arithmetic and state replay only',
        'private_data_or_legacy_models_used': False,
        'broker_or_mt5_connection': False, 'order_authority': False,
        'entry_proposal': asdict(proposal),
        'notional_guard': notional_guard_trace(),
        'unknown_risk': str(unknown.ledger.unknown_risk),
        'duplicate_mock_send_blocked': duplicate_blocked,
        'mock_attempts': len(mock.attempted), 'logical_replay_equal': recovered == executor.state,
        'partial': {'open_risk': str(partial_hold.open_risk),
                    'unknown_risk': str(partial_hold.unknown_risk),
                    'total': str(partial_hold.total)},
        'settlement': {'held_risk_after_confirmed_close': str(partial.state.ledger.total),
                       'charged_realized_loss': str(partial.state.budget.realized_loss),
                       'epoch_cap_unchanged': str(partial.state.budget.risk_limit),
                       'net_pnl': str(closed.allocation.money.net),
                       'evidence_source': 'OFFLINE_SYNTHETIC'},
        'candidate_comparison': [asdict(result) for result in results],
        'market_performance_validated': False,
        'limitations': ['Fixed shared synthetic trace; no policy winner is inferred.',
                       'Replay assumes synthetic initial SL installation and modeled latency.',
                       'Memory replay does not establish disk durability.',
                       'No live broker configuration, cost, account or session was verified.'],
    }


def main():
    report = build_demo()
    encoded = json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n'
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    (reports / 'synthetic-demo.json').write_text(encoded, encoding='utf-8')
    summary = {'mock_attempts': report['mock_attempts'],
               'notional_guard': report['notional_guard'],
               'unknown_risk': report['unknown_risk'], 'partial': report['partial'],
               'settlement': report['settlement'],
               'logical_replay_equal': report['logical_replay_equal'],
               'candidate_net_estimates': {r['candidate']: str(r['estimated_net_cash'])
                                         for r in report['candidate_comparison']},
               'report_sha256': hashlib.sha256(encoded.encode()).hexdigest()}
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
