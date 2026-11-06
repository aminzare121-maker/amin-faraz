"""Raw closed-price path into S16 core candidates, never automatic entry facts.

FVG source references are already causal. Wick/meaningful-pivot selection and
later candle exceptions are NOT solved by this closed-price geometry adapter.
"""
from pullback_topology import PathPoint,PathReference,PullbackTopology

class ClosedPullbackBridge:
    def __init__(self,interval,source):
        self.interval=interval;self.source=source;self.previous=None;self.models={}
    def fork(self):
        x=ClosedPullbackBridge(self.interval,self.source);x.previous=self.previous
        x.models={k:m.fork() for k,m in self.models.items()};return x
    def step(self,bar,zone_events):
        emitted=[]
        for identity,m in self.models.items():
            if m.stage in ('CORE_CONFIRMED','REVIEW_MISSING_PATH','REVIEW_REFERENCE_REASSESSMENT'):continue
            previous=m.stage
            result=m.step(PathPoint(bar.closed_at,bar.close,self.source+':CLOSE:'+str(bar.opened_at)))
            if result['events'] or result['stage']!=previous:emitted.append(result)
        for side in ('BUY','SELL'):
            refs=[e for e in zone_events if e['side']==side]
            if len(refs)!=1 or self.previous is None:continue
            e=refs[0]
            if not e['body_cross'] or e['series_gap'] or e['history_unknown'] or e['prior_far_edge_crosses']:continue
            if e['reference_known_at']>self.previous.closed_at:continue
            identity=e['zone_id']+':'+side+':BREAK:'+str(bar.closed_at)
            if identity in self.models:continue
            ref=PathReference(identity,e['reference_known_at'],e['edge'],e['reference_known_at'],self.source+':FVG_REFERENCE')
            m=PullbackTopology(side,ref,'CLOSED_PRICE_PATH',self.interval)
            m.step(PathPoint(self.previous.closed_at,self.previous.close,self.source+':PREVIOUS_CLOSE'))
            result=m.step(PathPoint(bar.closed_at,bar.close,self.source+':BREAK_CLOSE'))
            self.models[identity]=m;emitted.append(result)
        self.previous=bar
        return emitted
