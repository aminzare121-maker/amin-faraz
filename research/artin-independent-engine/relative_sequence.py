"""Source-selected causal sequence measurements, not a strength classifier.

No implicit window/N/ATR or STRONG Fact is created. A sourced integer start time
must be known before target opens. Decimal prices are converted to exact Fraction
before subtraction/division, so active Decimal context cannot round the ratio.
Missing selection/history/gap/availability returns UNKNOWN, not a negative pattern.
"""
from fractions import Fraction
from entry_engine import Fact
from raw_geometry import Candle

def measure(prior_bars,target,selected_start,source_id,at,interval_seconds):
    if type(at) is not int or at<0:raise ValueError('nonnegative integer decision time required')
    if type(interval_seconds) is not int or interval_seconds<=0:raise ValueError('explicit positive interval required')
    if not isinstance(source_id,str) or not source_id.strip():raise ValueError('history source id required')
    if type(prior_bars) is not tuple or not isinstance(target,Candle) or any(not isinstance(b,Candle) for b in prior_bars):
        raise ValueError('immutable tuple of prior Candles and target Candle required')
    previous=None
    if target.closed_at-target.opened_at!=interval_seconds:raise ValueError('target duration differs from interval')
    for b in prior_bars:
        if b.closed_at-b.opened_at!=interval_seconds:raise ValueError('bar duration differs from interval')
        if previous is not None and (b.opened_at<=previous.opened_at or b.opened_at<previous.closed_at):
            raise ValueError('strict ascending nonoverlapping history then target required')
        previous=b
    base=dict(candidate_only=True,actionable=False,strength_label=None,source_id=source_id,
              target_opened_at=target.opened_at,target_known_at=target.closed_at,
              parent_open_times=(),selection_source=None,selection_known_at=None)
    def unknown(reason):return dict(base,status='UNKNOWN',reason=reason,target_body_to_context_max_body=None,
                                    target_larger_than_every_prior_body=None)
    if selected_start is None:return unknown('MISSING_SOURCED_SEQUENCE_START')
    if not isinstance(selected_start,Fact):raise ValueError('selected_start must be sourced Fact or None')
    base.update(selection_source=selected_start.source,selection_known_at=selected_start.known_at)
    if type(selected_start.value) is not int or selected_start.value<0:
        raise ValueError('sequence start must be nonnegative integer open time')
    if selected_start.known_at>target.opened_at:return unknown('SEQUENCE_SELECTION_NOT_KNOWN_BEFORE_TARGET')
    if target.closed_at>at:return unknown('TARGET_NOT_CLOSED_AS_OF_DECISION')
    if any(b.closed_at>target.opened_at for b in prior_bars):return unknown('FUTURE_OR_UNCLOSED_PRIOR_HISTORY')
    if selected_start.value>=target.opened_at:return unknown('SEQUENCE_START_NOT_PRIOR_TO_TARGET')
    if not any(b.opened_at==selected_start.value for b in prior_bars):return unknown('SELECTED_START_BAR_MISSING')
    context=tuple(b for b in prior_bars if b.opened_at>=selected_start.value)
    base['parent_open_times']=tuple(b.opened_at for b in context)+(target.opened_at,)
    if not context:return unknown('EMPTY_PRIOR_SEQUENCE')
    if any(b.closed_at>target.opened_at for b in context):return unknown('PRIOR_BAR_NOT_CLOSED_BEFORE_TARGET')
    if any(a.closed_at!=b.opened_at for a,b in zip(context,context[1:]+(target,))):
        return unknown('GAP_IN_SELECTED_SEQUENCE')
    body=lambda b:abs(Fraction(b.close)-Fraction(b.open))
    target_body=body(target)
    maximum=max(body(b) for b in context)
    maximum_range=max(Fraction(b.high)-Fraction(b.low) for b in context)
    if maximum==0:
        return dict(base,status='UNDEFINED',reason='ZERO_CONTEXT_MAX_BODY',target_body=target_body,
                    context_max_body=maximum,context_max_range=maximum_range,
                    target_body_to_context_max_body=None,target_larger_than_every_prior_body=None)
    return dict(base,status='MEASURED',reason='SOURCE_SELECTED_SEQUENCE_GEOMETRY_ONLY',
                target_body=target_body,context_max_body=maximum,context_max_range=maximum_range,
                target_range=Fraction(target.high)-Fraction(target.low),
                target_body_to_context_max_body=target_body/maximum,
                target_larger_than_every_prior_body=target_body>maximum)
