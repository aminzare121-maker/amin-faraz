#!/usr/bin/env python3
"""Pure, broker-independent reference for Artin M15 *capture* recovery.

No MT5 connection, real-broker provenance, market prediction, orders or P/L.
The separate MQL5 source must be compiled and run before its behavior is proven.
A missing exact checkpoint is an error; future candles and synthetic gap bars
must never be inserted. All inputs are explicitly caller-provided closed bars.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence


class RecoveryBlocked(ValueError):
    pass


@dataclass(frozen=True)
class RecoveryBatch:
    mode: str
    epochs: tuple[int, ...]
    pending_before_batch: int
    pending_after_batch: int
    exhausted: bool


def next_closed_batch(
    chronological_closed_epochs: Sequence[int],
    last_committed_epoch: int | None,
    *,
    initial_closed_bars: int = 96,
    batch_bars: int = 256,
    max_catchup_bars: int = 5000,
) -> RecoveryBatch:
    """Choose the oldest missing closed bars, never duplicate or fabricate.

    `chronological_closed_epochs` represents the broker's *already closed*
    available bars. Wall-clock holes (weekends, outages) are preserved.
    """
    if not isinstance(initial_closed_bars, int) or not 1 <= initial_closed_bars <= 5000:
        raise RecoveryBlocked('BAD_BOOTSTRAP_LIMIT')
    if not isinstance(batch_bars, int) or not 1 <= batch_bars <= 1000:
        raise RecoveryBlocked('BAD_BATCH_LIMIT')
    if not isinstance(max_catchup_bars, int) or not batch_bars <= max_catchup_bars <= 500000:
        raise RecoveryBlocked('BAD_BACKFILL_CAP')
    if isinstance(last_committed_epoch, bool) or (last_committed_epoch is not None and
            (not isinstance(last_committed_epoch, int) or last_committed_epoch <= 0 or
             last_committed_epoch % 900)):
        raise RecoveryBlocked('INVALID_COMMITTED_CHECKPOINT')
    bars = tuple(chronological_closed_epochs)
    if len(bars) > 500000:
        raise RecoveryBlocked('BAR_LIMIT')
    last = 0
    for t in bars:
        if isinstance(t, bool) or not isinstance(t, int) or t <= last or t % 900:
            raise RecoveryBlocked('NON_MONOTONIC_OR_OFFGRID_SOURCE_HISTORY')
        last = t
    if last_committed_epoch is None:
        pending = bars[-initial_closed_bars:]
        mode = 'BOOTSTRAP_CLOSED_ONLY'
    else:
        if last_committed_epoch not in bars:
            # do not guess nearest bar and silently skip source history
            raise RecoveryBlocked('EXACT_LAST_COMMITTED_BAR_NOT_IN_BROKER_HISTORY')
        i = bars.index(last_committed_epoch)
        pending = bars[i + 1:]
        mode = 'RECOVER_FROM_CSV_CHECKPOINT'
        if len(pending) > max_catchup_bars:
            raise RecoveryBlocked('CATCHUP_BAR_COUNT_EXCEEDS_CAP')
    batch = pending[:batch_bars]
    return RecoveryBatch(mode, batch, len(pending), len(pending)-len(batch),
                         len(batch) == len(pending))