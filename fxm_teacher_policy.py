"""FXM teacher-handout rules, pages 2--7, for the existing Artin paper motor.

Only explicit, auditable rules are executable. Ambiguous or unobserved teacher
conditions fail closed. NO broker/order or account-login API exists here.
The existing 13-entry engine and its pinned implementation are not modified.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Optional

from core.capital import Instrument, Costs, size_position

PDF_SOURCE = 'FXM.pdf'


class FXMError(ValueError):
    pass


def dec(value, field='number', allow_zero=False):
    if type(value) not in (int, str, Decimal):
        raise FXMError('EXACT_NUMBER_REQUIRED:' + field)
    try:
        value = Decimal(value)
    except (InvalidOperation, ValueError):
        raise FXMError('INVALID_NUMBER:' + field) from None
    if not value.is_finite() or (value < 0 if allow_zero else value <= 0):
        raise FXMError('OUT_OF_RANGE:' + field)
    return value


@dataclass(frozen=True)
class AccountRisk:
    """Reference balance is the fixed start-of-plan account balance, p.2.

    The teacher's example is $1000 -> 20% loss; treating the reference as a
    high-water mark instead would be an unwarranted policy change.
    """
    balance: Decimal
    reference_balance: Decimal
    risk_pct: Decimal

    def __post_init__(self):
        for name in ('balance', 'reference_balance', 'risk_pct'):
            object.__setattr__(self, name, dec(getattr(self, name), name))

    def assess(self):
        drawdown = (self.reference_balance - self.balance) / self.reference_balance * 100
        if drawdown >= 20:
            return {'status': 'STOP_FXM_20_PERCENT_BALANCE_DRAWDOWN',
                    'drawdown_pct': str(drawdown), 'source': 'FXM.pdf#page=2',
                    'orders_enabled': False}
        if self.risk_pct < 1 or self.risk_pct > 2:
            return {'status': 'REJECT_FXM_RISK_MUST_BE_1_TO_2_PERCENT',
                    'source': 'FXM.pdf#page=2', 'orders_enabled': False}
        return {'status': 'RISK_BUDGET_AVAILABLE',
                'per_trade_risk_budget': str(self.balance * self.risk_pct / 100),
                'drawdown_pct': str(drawdown),
                'source': 'FXM.pdf#page=2', 'orders_enabled': False}


def risk_sized_plan(account: AccountRisk, side, entry, structural_stop,
                    instrument: Instrument, costs: Costs, *, stop_source, entry_source):
    """Size without moving a teacher-defined structural SL to fit the volume."""
    gate = account.assess()
    if gate['status'] != 'RISK_BUDGET_AVAILABLE':
        return gate
    if side not in ('BUY', 'SELL'):
        return {'status': 'REVIEW_SIDE_REQUIRED', 'orders_enabled': False}
    if not all(isinstance(s, str) and s.strip() for s in (stop_source, entry_source)):
        return {'status': 'REVIEW_TEACHER_ENTRY_AND_STOP_SOURCES_REQUIRED', 'orders_enabled': False}
    entry, stop = dec(entry, 'entry'), dec(structural_stop, 'structural_stop')
    sizing = size_position(side, entry, stop, dec(gate['per_trade_risk_budget']), instrument, costs)
    if sizing['status'] != 'ACCEPT':
        return {'status': 'NO_TRADE_'+sizing['reason'], 'orders_enabled': False,
                'source': ['FXM.pdf#page=2', 'FXM.pdf#page=3', stop_source]}
    return {'status': 'PAPER_SIZED_ONLY', 'risk_budget': gate['per_trade_risk_budget'],
            'lots': str(sizing['lots']), 'modeled_max_loss': str(sizing['modeled_loss']),
            'entry': str(entry), 'structural_stop_unchanged': str(stop),
            'source': ['FXM.pdf#page=2', 'FXM.pdf#page=3', entry_source, stop_source],
            'teacher_entry_verified_by_this_step': False, 'orders_enabled': False}


def winrate_target_policy(winrate, *, evidence_source):
    """Return only nonoverlapping readings from the handwritten p.4 table.

    The page has conflicting 50%, 50--61%, 60--100% rows and note >66%; in
    these ranges a distinct teacher-confirmed branch is necessary. Never
    quietly pick one RR over another.
    """
    w = dec(winrate, 'winrate_pct', allow_zero=True)
    if w > 100:
        raise FXMError('WINRATE_ABOVE_100_PERCENT')
    if not isinstance(evidence_source, str) or not evidence_source.strip():
        return {'status': 'REVIEW_WINRATE_EVIDENCE_REQUIRED', 'orders_enabled': False}
    if w <= 33:
        return {'status': 'NO_TRADE_WINRATE_0_TO_33', 'source': 'FXM.pdf#page=4',
                'orders_enabled': False}
    if 33 < w < 40:
        rr = '2'
    elif 40 < w < 45:
        rr = '1.8'
    elif 66 < w <= 100:
        rr = '0.8'
    else:
        return {'status': 'REVIEW_CONFLICTING_OR_UNSPECIFIED_RR_BAND',
                'winrate_pct': str(w), 'source': 'FXM.pdf#page=4',
                'reason': 'Handwritten RR rows overlap or exclude this threshold',
                'orders_enabled': False}
    return {'status': 'RR_CANDIDATE_FROM_HANDOUT', 'winrate_pct': str(w),
            'rr': rr, 'source': ['FXM.pdf#page=4', evidence_source],
            'teacher_entry_verified_by_this_step': False, 'orders_enabled': False}


def timeframe_notes(style):
    """Only instructional timeframes explicitly written on pp.3,6,7.

    This is metadata and never entry authorization or indicator selection.
    """
    result = {
        'DAY_TRADE': {'stop_reference_mins': 15, 'source': 'FXM.pdf#page=3'},
        'SCALP': {'entry_reference_mins': 5, 'stop_reference_mins': 5,
                  'target_reference_mins': 30, 'source': 'FXM.pdf#page=6'},
        'FAST_SCALP': {'entry_reference_mins': 1, 'stop_reference_mins': 1,
                       'target_reference_mins': 15, 'source': 'FXM.pdf#page=7'},
    }
    if style not in result:
        raise FXMError('UNKNOWN_FXM_TRADING_STYLE')
    return {'style': style, **result[style], 'trading_signal_generated': False}


def proposed_multi_targets(side, entry, initial_stop, *, teacher_branch_confirmed, teacher_branch_source=None):
    """P.4 diagram: TP1=.8 R, TP2=1.3 R, TP3=1.8 R.

    Conditional multi-target choice is not guessed from overlapping winrates.
    """
    if teacher_branch_confirmed is not True or not (isinstance(teacher_branch_source, str) and teacher_branch_source.strip()):
        return {'status': 'WAIT_FOR_TEACHER_MULTI_TARGET_BRANCH_CONFIRMATION',
                'orders_enabled': False}
    if side not in ('BUY', 'SELL'):
        raise FXMError('INVALID_SIDE')
    entry = dec(entry, 'entry')
    stop = dec(initial_stop, 'initial_stop')
    sign = Decimal(1) if side == 'BUY' else Decimal(-1)
    distance = sign * (entry - stop)
    if distance <= 0:
        raise FXMError('INVALID_STRUCTURAL_STOP')
    return {'status': 'PAPER_TARGETS_CALCULATED',
            'tp1': str(entry + sign * distance * Decimal('0.8')),
            'tp2': str(entry + sign * distance * Decimal('1.3')),
            'tp3': str(entry + sign * distance * Decimal('1.8')),
            'source': ['FXM.pdf#page=4', teacher_branch_source], 'orders_enabled': False}


@dataclass(frozen=True)
class PaperPosition:
    """Explicit quote-driven FXM stop ladder. No fill, broker, or order calls."""
    side: str
    entry: Decimal
    initial_stop: Decimal
    current_stop: Decimal
    tp1: Decimal
    tp2: Decimal
    tp3: Decimal
    volume: Decimal
    stage: int = 0
    pending_exit: Optional[str] = None
    last_at: Optional[int] = None

    def __post_init__(self):
        if self.side not in ('BUY', 'SELL'):
            raise FXMError('INVALID_SIDE')
        for name in ('entry', 'initial_stop', 'current_stop', 'tp1', 'tp2', 'tp3', 'volume'):
            object.__setattr__(self, name, dec(getattr(self, name), name))
        sign = Decimal(1) if self.side == 'BUY' else Decimal(-1)
        if not (sign*(self.entry-self.initial_stop)>0 and
                sign*(self.current_stop-self.initial_stop)>=0 and
                sign*(self.tp1-self.entry)>0 and sign*(self.tp2-self.tp1)>0 and
                sign*(self.tp3-self.tp2)>0):
            raise FXMError('INVALID_POSITION_OR_TARGET_STRUCTURE')
        if type(self.stage) is not int or not 0 <= self.stage <= 2:
            raise FXMError('INVALID_TP_STAGE')
        if self.pending_exit not in (None, 'STOP_TOUCH', 'TP3_TOUCH'):
            raise FXMError('INVALID_PENDING_EXIT')
        if self.last_at is not None and (type(self.last_at) is not int or self.last_at < 0):
            raise FXMError('INVALID_LAST_OBSERVATION_TIME')

    def observe_quote(self, bid, ask, at):
        """For buy use BID, for sell ASK. No realized PnL/fill assumed."""
        if type(at) is not int or at < 0 or (self.last_at is not None and at < self.last_at):
            raise FXMError('NONMONOTONIC_OR_INVALID_QUOTE_TIME')
        bid, ask = dec(bid, 'bid'), dec(ask, 'ask')
        if bid > ask:
            raise FXMError('INVALID_BID_ASK_SPREAD')
        if self.pending_exit is not None:
            return self, {'status': 'AWAITING_BROKER_OR_PAPER_EXIT_FILL',
                          'pending_exit': self.pending_exit, 'orders_enabled': False}
        quote = bid if self.side == 'BUY' else ask
        sign = Decimal(1) if self.side == 'BUY' else Decimal(-1)
        if sign * (quote - self.current_stop) <= 0:
            next_pos = replace(self, pending_exit='STOP_TOUCH', last_at=at)
            return next_pos, {'status': 'PAPER_STOP_TOUCH', 'exit_fill_verified': False,
                              'realized_pnl': None, 'orders_enabled': False,
                              'source': 'FXM.pdf#page=4'}
        if sign * (quote - self.tp3) >= 0:
            next_pos = replace(self, pending_exit='TP3_TOUCH', last_at=at)
            return next_pos, {'status': 'PAPER_TP3_CLOSE_ALL_TRIGGER', 'exit_fill_verified': False,
                              'realized_pnl': None, 'orders_enabled': False,
                              'source': 'FXM.pdf#page=4'}
        requested_stage = 2 if sign * (quote - self.tp2) >= 0 else 1 if sign * (quote - self.tp1) >= 0 else 0
        if requested_stage <= self.stage:
            return replace(self, last_at=at), {
                'status': 'PAPER_HOLD', 'current_stop': str(self.current_stop), 'orders_enabled': False}
        desired = self.tp1 if requested_stage == 2 else self.entry
        # Never loosen a stop already protecting more than the teacher ladder.
        target_stop = desired if sign * (desired-self.current_stop) > 0 else self.current_stop
        next_pos = replace(self, current_stop=target_stop, stage=requested_stage, last_at=at)
        return next_pos, {'status': 'PAPER_MOVE_STOP_TO_TP1' if requested_stage == 2 else 'PAPER_MOVE_STOP_TO_ENTRY',
                          'old_stop': str(self.current_stop), 'new_stop': str(target_stop),
                          'lots_before': str(self.volume), 'lots_after': str(next_pos.volume),
                          'exit_fill_verified': False, 'realized_pnl': None,
                          'source': 'FXM.pdf#page=4', 'orders_enabled': False}


def day_trade_permission(outcomes):
    """P.5 classroom day-trade stop sequence, per trading day.

    TP/SL here are *recorded closed trade outcomes*, never inferred from a
    touched price or a synthetic candle. BREAK_EVEN/unknown -> REVIEW.
    """
    if not isinstance(outcomes, (list, tuple)) or any(x not in ('TP', 'SL') for x in outcomes):
        return {'status': 'REVIEW_VERIFIED_CLOSED_OUTCOMES_REQUIRED', 'orders_enabled': False}
    n = len(outcomes)
    if outcomes.count('SL') >= 5:
        reason = 'STOP_AFTER_FIVE_STOPS'
    elif n >= 3 and outcomes[:3].count('SL') >= 2:
        reason = 'STOP_INITIAL_THREE_ONE_TP_TWO_SL_OR_THREE_SL'
    elif n >= 4 and outcomes[:3].count('TP') == 2 and 'SL' in outcomes[3:]:
        reason = 'STOP_AFTER_SECOND_SL_IN_TWO_TP_ONE_SL_BRANCH'
    elif n >= 4 and outcomes[:3].count('TP') == 3 and 'SL' in outcomes[3:]:
        reason = 'STOP_FIRST_SL_AFTER_THREE_TP'
    else:
        return {'status': 'PAPER_DAY_SEQUENCE_CONTINUE', 'closed_trades': n,
                'source': 'FXM.pdf#page=5', 'orders_enabled': False}
    return {'status': 'STOP_FXM_DAY_TRADE_SEQUENCE', 'reason': reason,
            'closed_trades': n, 'source': 'FXM.pdf#page=5', 'orders_enabled': False}