"""Experimental interval envelopes, never an entry classifier or probability.

Caller supplies evidence-labelled feature intervals and groups. All edits/crops of
the same original figure MUST share a group; this module cannot infer provenance.
Fit takes an explicit availability time. Prediction fully inside exactly one class
envelope is still UNKNOWN if its box intersects any other class envelope (inclusive
boundary contact). Envelopes can bridge holes between samples: a matching candidate
is coverage of the bounding box, not empirical support for every interior point.
No calibration claim, STRONG Fact, order, network or existing engine dependency.
"""
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
import hashlib
import json

def _time(v):
    if type(v) is not int or v<0:raise ValueError('nonnegative integer time required')

def _text(v):
    if not isinstance(v,str) or not v.strip():raise ValueError('nonempty evidence identifier required')

def _exact(v):
    sign,digits,exponent=v.as_tuple();digits=list(digits)
    if not any(digits):return '0'
    while digits[-1]==0:digits.pop();exponent+=1
    return ('-' if sign else '')+''.join(map(str,digits))+'e'+str(exponent)

@dataclass(frozen=True)
class Interval:
    low: Decimal
    high: Decimal
    def __post_init__(self):
        if any(not isinstance(x,Decimal) or not x.is_finite() for x in (self.low,self.high)):
            raise ValueError('finite exact Decimal endpoints required')
        if self.low>self.high:raise ValueError('interval low exceeds high')

@dataclass(frozen=True)
class Sample:
    label: str
    features: object
    source: str
    known_at: int
    group: str
    def __post_init__(self):
        for x in (self.label,self.source,self.group):_text(x)
        _time(self.known_at)
        if not hasattr(self.features,'items') or not self.features:raise ValueError('feature mapping required')
        for k,v in self.features.items():
            _text(k)
            if not isinstance(v,Interval):raise ValueError('Interval features required')
        object.__setattr__(self,'features',MappingProxyType(dict(self.features)))

@dataclass(frozen=True)
class Prediction:
    label: object
    status: str
    reason: str
    model_fingerprint: str
    candidate_only: bool=True
    actionable: bool=False

@dataclass(frozen=True)
class EnvelopeModel:
    feature_schema: tuple
    samples: tuple
    envelopes: tuple
    trained_at: int

    def __post_init__(self):
        _time(self.trained_at)
        if type(self.feature_schema) is not tuple or not self.feature_schema or len(set(self.feature_schema))!=len(self.feature_schema):
            raise ValueError('explicit unique feature schema tuple required')
        for k in self.feature_schema:_text(k)
        if type(self.samples) is not tuple or not self.samples:raise ValueError('nonempty immutable samples required')
        for s in self.samples:
            if not isinstance(s,Sample) or set(s.features)!=set(self.feature_schema):raise ValueError('sample schema mismatch')
            if s.known_at>self.trained_at:raise ValueError('training sample unavailable at fit time')
        expected=[]
        for label in sorted({s.label for s in self.samples}):
            rows=[s for s in self.samples if s.label==label]
            expected.append((label,tuple(Interval(min(s.features[k].low for s in rows),max(s.features[k].high for s in rows)) for k in self.feature_schema)))
        if self.envelopes!=tuple(expected):raise ValueError('envelopes must match immutable training evidence')

    @classmethod
    def fit(cls,samples,feature_schema,trained_at):
        samples=tuple(samples);schema=feature_schema
        # Validate evidence before computing envelopes, including missing schemas.
        if type(schema) is not tuple or not schema or any(not isinstance(s,Sample) or set(s.features)!=set(schema) for s in samples):
            raise ValueError('samples and explicit schema required')
        env=[]
        for label in sorted({s.label for s in samples}):
            rows=[s for s in samples if s.label==label]
            env.append((label,tuple(Interval(min(s.features[k].low for s in rows),max(s.features[k].high for s in rows)) for k in schema)))
        return cls(schema,samples,tuple(env),trained_at)

    def serialize(self):
        def box(v):return {'type':'DecimalInterval','low':_exact(v.low),'high':_exact(v.high)}
        rows=[dict(label=s.label,source=s.source,known_at=s.known_at,group=s.group,
                   features={k:box(s.features[k]) for k in self.feature_schema}) for s in self.samples]
        rows.sort(key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False))
        return dict(version='EXPERIMENTAL_INTERVAL_ENVELOPE_V1',feature_schema=list(self.feature_schema),trained_at=self.trained_at,
                    samples=rows,envelopes=[dict(label=l,features={k:box(v) for k,v in zip(self.feature_schema,vs)}) for l,vs in self.envelopes],
                    coverage=self.coverage,candidate_only=True,actionable=False)

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.serialize(),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

    @property
    def coverage(self):
        return {label:dict(samples=sum(s.label==label for s in self.samples),
                           groups=sorted({s.group for s in self.samples if s.label==label}),
                           sources=sorted({s.source for s in self.samples if s.label==label})) for label,_ in self.envelopes}

    def predict(self,features,at):
        _time(at)
        if not hasattr(features,'keys') or set(features)!=set(self.feature_schema) or any(not isinstance(v,Interval) for v in features.values()):
            raise ValueError('prediction feature schema mismatch')
        def result(label,reason):return Prediction(label,'CANDIDATE' if label is not None else 'UNKNOWN',reason,self.fingerprint)
        if at<self.trained_at:return result(None,'MODEL_NOT_AVAILABLE_AT_DECISION_TIME')
        query=tuple(features[k] for k in self.feature_schema)
        inside=[];intersect=[]
        for label,env in self.envelopes:
            if all(e.low<=q.low<=q.high<=e.high for q,e in zip(query,env)):inside.append(label)
            if all(q.low<=e.high and e.low<=q.high for q,e in zip(query,env)):intersect.append(label)
        if len(inside)!=1:return result(None,'OUTSIDE_OR_NOT_UNIQUELY_CONTAINED')
        if any(label!=inside[0] for label in intersect):return result(None,'OVERLAPPING_OTHER_CLASS')
        return result(inside[0],'UNIQUE_NONOVERLAPPING_ENVELOPE_CANDIDATE')

def leave_one_group_out(samples,feature_schema):
    """Group holdout; each held sample trains only on evidence known by its time.

    This is evidence-separation evaluation, not a market return or probability.
    """
    samples=tuple(samples)
    if not samples or any(not isinstance(s,Sample) for s in samples):raise ValueError('samples required')
    rows=[]
    for group in sorted({s.group for s in samples}):
        for held in (s for s in samples if s.group==group):
            train=tuple(s for s in samples if s.group!=group and s.known_at<=held.known_at)
            prediction=EnvelopeModel.fit(train,feature_schema,held.known_at).predict(held.features,held.known_at) if train else None
            rows.append(dict(held_group=group,held_source=held.source,expected_label=held.label,
                             training_groups=sorted({s.group for s in train}),training_sources=sorted({s.source for s in train}),
                             prediction=None if prediction is None else prediction.label,
                             status='UNKNOWN' if prediction is None else prediction.status,
                             correct=prediction is not None and prediction.label==held.label,
                             reason='NO_OTHER_GROUP_AVAILABLE' if prediction is None else prediction.reason))
    return dict(mode='LEAVE_ONE_GROUP_OUT_AS_OF_EVIDENCE',rows=rows,total=len(rows),
                candidate_predictions=sum(r['prediction'] is not None for r in rows),correct_candidates=sum(r['correct'] for r in rows),
                unknown=sum(r['prediction'] is None for r in rows),candidate_only=True,actionable=False,
                grouping_must_keep_all_edits_of_same_figure_together=True)
