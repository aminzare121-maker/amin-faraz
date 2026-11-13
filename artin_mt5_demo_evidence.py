"""Strict MT5 DEMO execution receipt validator; never places orders.

A successful CI unit test is NOT a successful broker DEMO test.
Receipts must be exported by the actual MT5 terminal and cross-checked.
"""
from decimal import Decimal, InvalidOperation


class DemoEvidenceError(ValueError):
    pass


def _decimal(value):
    if type(value) not in (str, int):
        raise DemoEvidenceError('DEMO_EXACT_NUMBER_REQUIRED')
    try:
        n = Decimal(value)
    except (InvalidOperation, ValueError):
        raise DemoEvidenceError('DEMO_INVALID_NUMBER') from None
    if not n.is_finite():
        raise DemoEvidenceError('DEMO_NONFINITE_NUMBER')
    return n


def evaluate_demo_receipt(receipt):
    if not isinstance(receipt, dict) or receipt.get('schema') != 'artin_mt5_demo_receipt_v1':
        raise DemoEvidenceError('DEMO_RECEIPT_SCHEMA_REQUIRED')
    if receipt.get('account_mode') != 'DEMO':
        raise DemoEvidenceError('REAL_ACCOUNT_FORBIDDEN')
    if receipt.get('terminal_connected') is not True:
        raise DemoEvidenceError('DEMO_TERMINAL_CONNECTION_NOT_VERIFIED')
    if receipt.get('symbol') != 'XAUUSD':
        raise DemoEvidenceError('DEMO_SYMBOL_MISMATCH')
    if not isinstance(receipt.get('terminal_id'), str) or not receipt['terminal_id'].strip():
        raise DemoEvidenceError('DEMO_TERMINAL_ID_REQUIRED')
    if not isinstance(receipt.get('run_id'), str) or not receipt['run_id'].strip():
        raise DemoEvidenceError('DEMO_RUN_ID_REQUIRED')
    events = receipt.get('events')
    if not isinstance(events, list) or not events:
        raise DemoEvidenceError('DEMO_EVENTS_REQUIRED')
    seen = set()
    entered = set()
    closed = set()
    for event in events:
        if not isinstance(event, dict):
            raise DemoEvidenceError('DEMO_EVENT_OBJECT_REQUIRED')
        ticket = event.get('ticket')
        if type(ticket) is not int or ticket <= 0:
            raise DemoEvidenceError('DEMO_TICKET_REQUIRED')
        kind = event.get('kind')
        key = (ticket, kind)
        if key in seen:
            raise DemoEvidenceError('DEMO_DUPLICATE_TICKET_EVENT')
        seen.add(key)
        if kind == 'ENTRY_FILLED':
            if ticket in entered:
                raise DemoEvidenceError('DEMO_DUPLICATE_ENTRY')
            entered.add(ticket)
            if event.get('side') not in ('BUY', 'SELL') or _decimal(event.get('lots')) <= 0:
                raise DemoEvidenceError('DEMO_ENTRY_INVALID')
            if _decimal(event.get('fill_price')) <= 0:
                raise DemoEvidenceError('DEMO_FILL_PRICE_INVALID')
        elif kind == 'EXIT_FILLED':
            if ticket not in entered or ticket in closed:
                raise DemoEvidenceError('DEMO_EXIT_WITHOUT_OPEN_POSITION')
            closed.add(ticket)
            if _decimal(event.get('fill_price')) <= 0:
                raise DemoEvidenceError('DEMO_FILL_PRICE_INVALID')
        elif kind == 'STOP_MODIFIED':
            if ticket not in entered or ticket in closed:
                raise DemoEvidenceError('DEMO_STOP_MODIFY_WITHOUT_OPEN_POSITION')
            if _decimal(event.get('new_stop')) <= 0:
                raise DemoEvidenceError('DEMO_STOP_INVALID')
        else:
            raise DemoEvidenceError('DEMO_EVENT_KIND_UNSUPPORTED')
    return {'schema':'artin_mt5_demo_assessment_v1',
            'run_id':receipt['run_id'], 'terminal_id':receipt['terminal_id'],
            'account_mode':'DEMO', 'symbol':'XAUUSD',
            'filled_entries':len(entered), 'filled_exits':len(closed),
            'open_tickets':sorted(entered-closed),
            'evidence_structurally_valid':True,
            'broker_receipt_independently_authenticated':False,
            'teacher_strategy_match_verified':False,
            'demo_success_certified':False}
