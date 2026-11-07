"""Immutable synthetic PnL ledger with signed confirmed costs and exact shares.

Prices and amounts are caller-supplied offline inputs. A mark is an estimate;
realized PnL requires explicitly confirmed opening and closing deals. This module
has no broker, persistence, clock, currency conversion or market-data adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, MAX_EMAX, MIN_EMIN, localcontext
from typing import Tuple

from .numbers import dec, natural


def _d(value: object, label: str, *, nonnegative=False, positive=False) -> Decimal:
    try:
        result = dec(value)
    except ValueError:
        raise ValueError("INVALID_OR_UNKNOWN_" + label) from None
    if (nonnegative and result < 0) or (positive and result <= 0):
        raise ValueError("INVALID_" + label)
    return result


def _identity(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("INVALID_" + label)
    return value


def _precision(values) -> int:
    return max(64, 32 + sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent)
                            for v in values))


def _share(amount: Decimal, part: Decimal, whole: Decimal) -> Decimal:
    """Exact rational share, truncated toward zero on a stable decimal scale.

    Keep at least 28 fractional decimal places and every decimal place already
    present in the booked cost. Remainders stay in the lot until the last close.
    Integer arithmetic avoids ambient precision and repeating-decimal drift.
    """
    exponent = min(amount.as_tuple().exponent, -28)
    a, b = amount.as_integer_ratio()
    p, q = part.as_integer_ratio()
    w, z = whole.as_integer_ratio()
    numerator = abs(a) * p * z * (10 ** (-exponent))
    denominator = b * q * w
    units = numerator // denominator
    return Decimal((int(a < 0), tuple(int(c) for c in str(units)), exponent))


@dataclass(frozen=True)
class CashEvent:
    event_id: str
    kind: str
    amount: object
    confirmed: bool
    # Assigned by apply_cash_event; records cost timing for ledger verification.
    after_closures: int = 0


@dataclass(frozen=True)
class CloseDeal:
    deal_id: str
    volume: object
    price: object
    exit_fee: object
    confirmed: bool


@dataclass(frozen=True)
class MoneyBreakdown:
    status: str
    volume: Decimal
    gross: Decimal
    booked_entry_fees: Decimal
    booked_swap: Decimal
    booked_exit_fee: Decimal
    unpaid_exit_cost: Decimal
    slippage_reserve: Decimal
    net: Decimal


@dataclass(frozen=True)
class ClosedAllocation:
    deal: CloseDeal
    money: MoneyBreakdown


@dataclass(frozen=True)
class LotLedger:
    lot_id: str
    side: str
    entry_price: Decimal
    original_volume: Decimal
    remaining_volume: Decimal
    contract_size: Decimal
    entry_confirmed: bool
    remaining_entry_fees: Decimal = Decimal("0")
    remaining_swap: Decimal = Decimal("0")
    cash_events: Tuple[CashEvent, ...] = ()
    closures: Tuple[ClosedAllocation, ...] = ()


@dataclass(frozen=True)
class CloseResult:
    ledger: LotLedger
    allocation: ClosedAllocation
    applied: bool


def open_lot(lot_id: str, side: str, entry_price: object, volume: object,
             contract_size: object, *, confirmed: bool) -> LotLedger:
    _identity(lot_id, "LOT_ID")
    if side not in ("BUY", "SELL"):
        raise ValueError("INVALID_SIDE")
    if type(confirmed) is not bool:
        raise ValueError("EXPLICIT_CONFIRMATION_REQUIRED")
    entry = _d(entry_price, "ENTRY_PRICE", positive=True)
    size = _d(volume, "VOLUME", positive=True)
    contract = _d(contract_size, "CONTRACT_SIZE", positive=True)
    return LotLedger(lot_id, side, entry, size, size, contract, confirmed)


def _validate_ledger(ledger: LotLedger):
    if not isinstance(ledger, LotLedger):
        raise ValueError("INVALID_LEDGER")
    _identity(ledger.lot_id, "LOT_ID")
    if ledger.side not in ("BUY", "SELL") or type(ledger.entry_confirmed) is not bool:
        raise ValueError("INVALID_LEDGER")
    if not isinstance(ledger.cash_events, tuple) or not isinstance(ledger.closures, tuple):
        raise ValueError("IMMUTABLE_LEDGER_REQUIRED")
    numeric_fields = ("entry_price", "original_volume", "remaining_volume", "contract_size",
                      "remaining_entry_fees", "remaining_swap")
    if any(not isinstance(getattr(ledger, name), Decimal) for name in numeric_fields):
        raise ValueError("CANONICAL_DECIMAL_LEDGER_REQUIRED")
    for name in ("entry_price", "original_volume", "contract_size"):
        _d(getattr(ledger, name), name.upper(), positive=True)
    remaining = _d(ledger.remaining_volume, "REMAINING_VOLUME", nonnegative=True)
    if remaining > ledger.original_volume:
        raise ValueError("INVALID_REMAINING_VOLUME")
    _d(ledger.remaining_entry_fees, "REMAINING_ENTRY_FEES")
    _d(ledger.remaining_swap, "REMAINING_SWAP")
    if any(not isinstance(event, CashEvent) for event in ledger.cash_events):
        raise ValueError("INVALID_LEDGER_CASH_EVENT")
    if any(not isinstance(item, ClosedAllocation) or not isinstance(item.deal, CloseDeal)
           or not isinstance(item.money, MoneyBreakdown) for item in ledger.closures):
        raise ValueError("INVALID_LEDGER_CLOSURE")
    # Frozen records remain constructible/replaceable by callers. Rebuild the
    # accounting history instead of trusting independently supplied balances.
    ids = set()
    values = [getattr(ledger, name) for name in numeric_fields]
    last_cost_index = 0
    for event in ledger.cash_events:
        _identity(event.event_id, "EVENT_ID")
        if event.event_id in ids:
            raise ValueError("DUPLICATE_LEDGER_EVENT_ID")
        ids.add(event.event_id)
        if event.kind not in ("ENTRY_FEE", "SWAP") or event.confirmed is not True:
            raise ValueError("INVALID_LEDGER_CASH_EVENT")
        if not isinstance(event.amount, Decimal):
            raise ValueError("CANONICAL_DECIMAL_LEDGER_REQUIRED")
        values.append(_d(event.amount, "CASH_AMOUNT"))
        index = natural(event.after_closures)
        if index < last_cost_index or index > len(ledger.closures):
            raise ValueError("INVALID_LEDGER_COST_TIMING")
        if event.kind == "ENTRY_FEE" and index != 0:
            raise ValueError("LATE_ENTRY_FEE_REQUIRES_RECONCILIATION")
        last_cost_index = index
    money_fields = ("volume", "gross", "booked_entry_fees", "booked_swap", "booked_exit_fee",
                    "unpaid_exit_cost", "slippage_reserve", "net")
    for item in ledger.closures:
        deal, money = item.deal, item.money
        _deal(deal)
        if deal.deal_id in ids:
            raise ValueError("DUPLICATE_LEDGER_EVENT_ID")
        ids.add(deal.deal_id)
        if not ledger.entry_confirmed or deal.confirmed is not True or money.status != "REALIZED":
            raise ValueError("INVALID_LEDGER_CONFIRMED_DEAL")
        if any(not isinstance(value, Decimal) for value in (deal.volume, deal.price, deal.exit_fee)):
            raise ValueError("CANONICAL_DECIMAL_LEDGER_REQUIRED")
        values.extend((deal.volume, deal.price, deal.exit_fee))
        for name in money_fields:
            value = getattr(money, name)
            if not isinstance(value, Decimal):
                raise ValueError("CANONICAL_DECIMAL_LEDGER_REQUIRED")
            values.append(_d(value, "CLOSED_" + name.upper()))
    with localcontext() as ctx:
        ctx.prec = _precision(values)
        ctx.Emax, ctx.Emin = MAX_EMAX, MIN_EMIN
        remaining = ledger.original_volume
        fees = swap = Decimal("0")
        for index in range(len(ledger.closures) + 1):
            for event in ledger.cash_events:
                if event.after_closures == index:
                    if remaining == 0:
                        raise ValueError("CASH_EVENT_ON_CLOSED_LOT")
                    if event.kind == "ENTRY_FEE":
                        fees += event.amount
                    else:
                        swap += event.amount
            if index == len(ledger.closures):
                break
            deal, money = ledger.closures[index].deal, ledger.closures[index].money
            if deal.volume > remaining:
                raise ValueError("LEDGER_CLOSE_EXCEEDS_REMAINING_VOLUME")
            if deal.volume == remaining:
                closed_fees, closed_swap = fees, swap
            else:
                closed_fees, closed_swap = _share(fees, deal.volume, remaining), _share(swap, deal.volume, remaining)
            gross = _gross(ledger, deal.volume, deal.price)
            net = gross + closed_fees + closed_swap + deal.exit_fee
            expected = MoneyBreakdown("REALIZED", deal.volume, gross, closed_fees, closed_swap,
                                      deal.exit_fee, Decimal("0"), Decimal("0"), net)
            if money != expected:
                raise ValueError("LEDGER_CLOSURE_ACCOUNTING_MISMATCH")
            remaining -= deal.volume
            fees -= closed_fees
            swap -= closed_swap
        if (remaining != ledger.remaining_volume or fees != ledger.remaining_entry_fees
                or swap != ledger.remaining_swap):
            raise ValueError("LEDGER_BALANCE_CONSERVATION_MISMATCH")


def apply_cash_event(ledger: LotLedger, event: CashEvent) -> LotLedger:
    """Book a confirmed signed ENTRY_FEE or SWAP once.

    ENTRY_FEE applies to the opening lot and must arrive before any close. SWAP
    explicitly applies to the currently remaining position. Late entry-cost
    reconciliation needs a separate accounting workflow and is rejected here.
    """
    _validate_ledger(ledger)
    if not isinstance(event, CashEvent):
        raise ValueError("INVALID_CASH_EVENT")
    _identity(event.event_id, "EVENT_ID")
    if event.kind not in ("ENTRY_FEE", "SWAP"):
        raise ValueError("INVALID_CASH_KIND")
    amount = _d(event.amount, "CASH_AMOUNT")
    if event.confirmed is not True:
        raise ValueError("CASH_EVENT_NOT_CONFIRMED")
    natural(event.after_closures)
    for old in ledger.cash_events:
        if old.event_id == event.event_id:
            if (old.kind, old.amount, old.confirmed) != (event.kind, amount, True):
                raise ValueError("CONFLICTING_DUPLICATE_EVENT")
            return ledger
    normalized = CashEvent(event.event_id, event.kind, amount, True, len(ledger.closures))
    if any(item.deal.deal_id == event.event_id for item in ledger.closures):
        raise ValueError("EVENT_ID_ALREADY_USED_BY_DEAL")
    if ledger.remaining_volume == 0:
        raise ValueError("CASH_EVENT_ON_CLOSED_LOT")
    if event.kind == "ENTRY_FEE" and ledger.closures:
        raise ValueError("LATE_ENTRY_FEE_REQUIRES_RECONCILIATION")
    with localcontext() as ctx:
        ctx.prec = _precision((ledger.remaining_entry_fees, ledger.remaining_swap, amount))
        ctx.Emax, ctx.Emin = MAX_EMAX, MIN_EMIN
        fees = ledger.remaining_entry_fees + (amount if event.kind == "ENTRY_FEE" else 0)
        swap = ledger.remaining_swap + (amount if event.kind == "SWAP" else 0)
        return LotLedger(ledger.lot_id, ledger.side, ledger.entry_price,
                         ledger.original_volume, ledger.remaining_volume,
                         ledger.contract_size, ledger.entry_confirmed, fees, swap,
                         ledger.cash_events + (normalized,), ledger.closures)


def _gross(ledger: LotLedger, volume: Decimal, price: Decimal) -> Decimal:
    change = price - ledger.entry_price if ledger.side == "BUY" else ledger.entry_price - price
    return change * volume * ledger.contract_size


def mark_pnl(ledger: LotLedger, bid: object, ask: object, *, unpaid_exit_cost: object,
             slippage_reserve: object) -> MoneyBreakdown:
    """Buy exits at bid, sell exits at ask; spread is already in gross.

    Booked fees/swap are signed. Unpaid exit/slippage are nonnegative total
    reserves for this remaining volume and are subtracted exactly once.
    """
    _validate_ledger(ledger)
    bid_value = _d(bid, "BID", positive=True)
    ask_value = _d(ask, "ASK", positive=True)
    if bid_value > ask_value:
        raise ValueError("CROSSED_QUOTE")
    unpaid = _d(unpaid_exit_cost, "UNPAID_EXIT_COST", nonnegative=True)
    slip = _d(slippage_reserve, "SLIPPAGE_RESERVE", nonnegative=True)
    values = (bid_value, ask_value, unpaid, slip, ledger.entry_price,
              ledger.remaining_volume, ledger.contract_size,
              ledger.remaining_entry_fees, ledger.remaining_swap)
    with localcontext() as ctx:
        ctx.prec = _precision(values)
        ctx.Emax, ctx.Emin = MAX_EMAX, MIN_EMIN
        gross = _gross(ledger, ledger.remaining_volume,
                       bid_value if ledger.side == "BUY" else ask_value)
        net = gross + ledger.remaining_entry_fees + ledger.remaining_swap - unpaid - slip
        return MoneyBreakdown("ESTIMATED", ledger.remaining_volume, gross,
                              ledger.remaining_entry_fees, ledger.remaining_swap,
                              Decimal("0"), unpaid, slip, net)


def _deal(deal: CloseDeal) -> CloseDeal:
    if not isinstance(deal, CloseDeal):
        raise ValueError("INVALID_CLOSE_DEAL")
    _identity(deal.deal_id, "DEAL_ID")
    if type(deal.confirmed) is not bool:
        raise ValueError("EXPLICIT_CONFIRMATION_REQUIRED")
    return CloseDeal(deal.deal_id, _d(deal.volume, "CLOSE_VOLUME", positive=True),
                     _d(deal.price, "CLOSE_PRICE", positive=True),
                     _d(deal.exit_fee, "EXIT_FEE"), deal.confirmed)


def _allocation(ledger: LotLedger, deal: CloseDeal, status: str,
                unpaid: Decimal, slip: Decimal) -> MoneyBreakdown:
    if deal.volume > ledger.remaining_volume:
        raise ValueError("CLOSE_EXCEEDS_REMAINING_VOLUME")
    values = (ledger.entry_price, ledger.remaining_volume, ledger.contract_size,
              ledger.remaining_entry_fees, ledger.remaining_swap, deal.volume,
              deal.price, deal.exit_fee, unpaid, slip)
    with localcontext() as ctx:
        ctx.prec = _precision(values)
        ctx.Emax, ctx.Emin = MAX_EMAX, MIN_EMIN
        if deal.volume == ledger.remaining_volume:
            fees, swap = ledger.remaining_entry_fees, ledger.remaining_swap
        else:
            fees = _share(ledger.remaining_entry_fees, deal.volume, ledger.remaining_volume)
            swap = _share(ledger.remaining_swap, deal.volume, ledger.remaining_volume)
        gross = _gross(ledger, deal.volume, deal.price)
        net = gross + fees + swap + deal.exit_fee - unpaid - slip
        return MoneyBreakdown(status, deal.volume, gross, fees, swap,
                              deal.exit_fee, unpaid, slip, net)


def estimate_close(ledger: LotLedger, deal: CloseDeal, *, unpaid_exit_cost: object,
                   slippage_reserve: object) -> MoneyBreakdown:
    """A hypothetical close never changes the ledger or becomes REALIZED."""
    _validate_ledger(ledger)
    normalized = _deal(deal)
    unpaid = _d(unpaid_exit_cost, "UNPAID_EXIT_COST", nonnegative=True)
    slip = _d(slippage_reserve, "SLIPPAGE_RESERVE", nonnegative=True)
    return _allocation(ledger, normalized, "ESTIMATED", unpaid, slip)


def close_lot(ledger: LotLedger, deal: CloseDeal) -> CloseResult:
    """Apply a confirmed deal once and allocate booked costs proportionally.

    Replaying the same id/payload returns applied=False and its prior allocation.
    Reusing an id with different values fails instead of silently dropping data.
    """
    _validate_ledger(ledger)
    normalized = _deal(deal)
    for old in ledger.closures:
        if old.deal.deal_id == normalized.deal_id:
            if old.deal != normalized:
                raise ValueError("CONFLICTING_DUPLICATE_DEAL")
            return CloseResult(ledger, old, False)
    if any(event.event_id == normalized.deal_id for event in ledger.cash_events):
        raise ValueError("DEAL_ID_ALREADY_USED_BY_CASH_EVENT")
    if not ledger.entry_confirmed or not normalized.confirmed:
        raise ValueError("REALIZED_PNL_REQUIRES_CONFIRMED_DEALS")
    money = _allocation(ledger, normalized, "REALIZED", Decimal("0"), Decimal("0"))
    allocation = ClosedAllocation(normalized, money)
    with localcontext() as ctx:
        ctx.prec = _precision((ledger.remaining_volume, normalized.volume,
                               ledger.remaining_entry_fees, ledger.remaining_swap,
                               money.booked_entry_fees, money.booked_swap))
        ctx.Emax, ctx.Emin = MAX_EMAX, MIN_EMIN
        updated = LotLedger(ledger.lot_id, ledger.side, ledger.entry_price,
                            ledger.original_volume, ledger.remaining_volume - normalized.volume,
                            ledger.contract_size, ledger.entry_confirmed,
                            ledger.remaining_entry_fees - money.booked_entry_fees,
                            ledger.remaining_swap - money.booked_swap,
                            ledger.cash_events, ledger.closures + (allocation,))
    return CloseResult(updated, allocation, True)
