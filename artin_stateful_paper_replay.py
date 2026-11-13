"""Deterministic paper position state reducer for sourced Artin classroom actions.

Consumes output of artin_classroom_trade_actions.execute. It never sends
orders, invents fills or realizes P&L. An externally supplied paper position
is required; teacher classroom speech alone cannot create a position.
"""
from decimal import Decimal, InvalidOperation


class PaperReplayError(ValueError):
    pass


def _decimal(value):
    if type(value) not in (str, int):
        raise PaperReplayError('EXACT_PAPER_PRICE_REQUIRED')
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        raise PaperReplayError('INVALID_PAPER_PRICE') from None
    if not number.is_finite() or number <= 0:
        raise PaperReplayError('POSITIVE_PAPER_PRICE_REQUIRED')
    return number


def replay(actions_result, position):
    if actions_result.get('schema') != 'artin_classroom_trade_actions_result_v1':
        raise PaperReplayError('CLASSROOM_ACTION_RESULT_REQUIRED')
    if actions_result.get('orders_sent') != 0 or actions_result.get('broker_connected') is not False:
        raise PaperReplayError('PAPER_ONLY_SOURCE_REQUIRED')
    if not isinstance(position, dict) or position.get('side') not in ('BUY', 'SELL'):
        raise PaperReplayError('EXPLICIT_PAPER_POSITION_REQUIRED')
    side = position['side']
    entry = _decimal(position.get('entry'))
    stop = _decimal(position.get('current_stop'))
    lots = _decimal(position.get('lots'))
    if (side == 'BUY' and stop >= entry) or (side == 'SELL' and stop <= entry):
        raise PaperReplayError('INITIAL_STOP_WRONG_SIDE')
    rows = actions_result.get('classroom_decision_actions')
    if not isinstance(rows, list):
        raise PaperReplayError('CLASSROOM_ACTIONS_REQUIRED')
    seen = set()
    journal = []
    triggered = False
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('execution'), dict):
            raise PaperReplayError('INVALID_CLASSROOM_ACTION')
        ident = row.get('event_id')
        if not isinstance(ident, str) or not ident or ident in seen:
            raise PaperReplayError('DUPLICATE_CLASSROOM_EVENT')
        seen.add(ident)
        action = row['execution']
        decision = action.get('decision')
        if action.get('order_created') is not False:
            raise PaperReplayError('BROKER_ACTION_FORBIDDEN')
        before = str(stop)
        if decision in ('MOVE_STOP_TO_ENTRY_PAPER', 'PAPER_STOP_MOVE_ACCEPTED'):
            if triggered:
                raise PaperReplayError('STOP_MOVE_AFTER_TRIGGER')
            old = _decimal(action.get('old_stop'))
            new = _decimal(action.get('new_stop'))
            before_lots = _decimal(action.get('lots_before'))
            after_lots = _decimal(action.get('lots_after'))
            if old != stop or before_lots != lots or after_lots != lots:
                raise PaperReplayError('PAPER_POSITION_STATE_MISMATCH')
            if ((side == 'BUY' and new <= stop) or
                    (side == 'SELL' and new >= stop)):
                raise PaperReplayError('STOP_MUST_TIGHTEN')
            if decision == 'MOVE_STOP_TO_ENTRY_PAPER' and new != entry:
                raise PaperReplayError('RISKFREE_MUST_MOVE_TO_ENTRY')
            stop = new
        elif decision == 'STOP_EXIT_TRIGGER_PAPER_NOT_A_FILL':
            if triggered:
                raise PaperReplayError('DUPLICATE_STOP_TRIGGER')
            if (_decimal(action.get('stop')) != stop or
                    _decimal(action.get('entry')) != entry or
                    _decimal(action.get('lots')) != lots):
                raise PaperReplayError('STOP_TRIGGER_STATE_MISMATCH')
            triggered = True
        elif decision == 'PAPER_POSITION_HELD_STOP_NOT_HIT':
            if triggered:
                raise PaperReplayError('QUOTE_AFTER_STOP_TRIGGER')
            if _decimal(action.get('stop')) != stop:
                raise PaperReplayError('QUOTE_STOP_STATE_MISMATCH')
        journal.append({'event_id': ident, 'decision': decision,
                        'stop_before': before, 'stop_after': str(stop),
                        'stop_triggered_in_model': triggered,
                        'broker_fill_verified': False})
    return {'schema': 'artin_stateful_paper_replay_v1',
            'side': side, 'entry': str(entry), 'current_stop': str(stop),
            'lots': str(lots), 'stop_triggered_in_model': triggered,
            'position_closed_by_broker': False, 'realized_pnl': None,
            'orders_sent': 0, 'journal': journal}


def execute_sourced_paper_replay(events_doc, source_folder, core_folder, position):
    """Run cited teacher actions then reduce their paper position state.

    Both stages are in-memory; errors produce no partial output and no orders.
    """
    from artin_classroom_trade_actions import execute
    actions = execute(events_doc, source_folder, core_folder)
    state = replay(actions, position)
    return {'schema': 'artin_sourced_paper_execution_v1',
            'classroom_actions': actions,
            'paper_position': state,
            'orders_sent': 0,
            'broker_connected': False,
            'teacher_semantic_certification_auto_granted': False}
