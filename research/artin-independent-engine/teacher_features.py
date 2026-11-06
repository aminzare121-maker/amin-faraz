"""Source-bounded candle predicates. No indicator or chosen tolerance.

Session13 compares body to shadows without an extracted unambiguous choice of
sum versus largest shadow. We return a result only when both readings agree.
These predicates do not establish trend strength, a trading zone or sentiment.
"""
from dataclasses import dataclass
from raw_geometry import geometry

@dataclass(frozen=True)
class Predicate:
    value: object  # bool or None (unresolved); never silently coerce None to False
    reason: str
    sources: tuple

BODY_SHADOW=((13,2259.38,2319.48),(13,2493.94,2517.38))

def candle_predicates(candle):
    g=geometry(candle)
    largest=max(g.upper_wick,g.lower_wick)
    total=g.upper_wick+g.lower_wick
    confidence=(True if g.body>total else False if g.body<=largest else None)
    doubt=(True if largest>g.body else False if total<=g.body else None)
    # Strict equality is reported separately; no arbitrary near-zero epsilon.
    fullbody=True if g.body>0 and total==0 else None
    doji=True if g.body==0 else None
    return {
        'confidence_shape':Predicate(confidence,'BODY_VS_BOTH_SHADOW_READINGS',BODY_SHADOW),
        'doubt_shape':Predicate(doubt,'BODY_VS_BOTH_SHADOW_READINGS',BODY_SHADOW),
        'fullbody_or_marubozu':Predicate(fullbody,'EXACT_NO_SHADOW_SUBSET_NOT_A_TOLERANCE',((21,2299,2307),(21,2345,2375))),
        'doji_confirmed':Predicate(doji,'EXACT_ZERO_BODY_SUBSET_NOT_NEAR_ZERO_CLASSIFIER',((21,3829.5,3848.5),)),
    }
