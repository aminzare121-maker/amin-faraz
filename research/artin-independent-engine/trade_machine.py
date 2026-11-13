"""One independent offline paper lifecycle; triggers are never fills or orders.

Caller supplies sourced observations, actual paper fills, explicit costs, target and
remaining aggregate budget. Instances do not share an account or enforce a global
one-position rule. Budget reservation across instances belongs to the caller.
"""
from decimal import Decimal
from types import MappingProxyType
from entry_engine import Fact
from capital import size_position, account_fill, move_stop

def number(v):
    if not isinstance(v,Decimal) or not v.is_finite() or v<=0:
        raise ValueError('explicit positive finite Decimal required')
    return v

class TradeMachine:
    def __init__(self,engine,box,instrument,costs):
        self.engine,self.box,self.instrument,self.costs=engine,box,instrument,costs
        self._box_fp,self._engine_fp=box.fingerprint,engine.fingerprint
        self._contract=instrument,costs
        self.state='NEW';self.trace=[];self.plan=None;self.fill=None;self.last_at=None;self.exit_fill=None
        self.modeled_exposure=None;self.budget_overrun=False;self.last_event_known_at=None;self.last_coordinator_at=None

    def _event(self,status,**fields):
        result=dict(status=status,state=self.state,order_created=False,**fields)
        self.trace.append(result.copy())
        return result

    def _fixed(self):
        if self.box.fingerprint!=self._box_fp or self.engine.fingerprint!=self._engine_fp:
            raise ValueError('fixed box/entry plan changed')
        if (self.instrument,self.costs)!=self._contract:
            raise ValueError('fixed contract or cost model changed')

    def _time(self,at):
        if type(at) is not int or at<0 or (self.last_at is not None and at<self.last_at):
            raise ValueError('nondecreasing explicit observation time required')

    def prepare(self,rule_id,observation,entry_price,initial_stop,target_price,aggregate_risk_remaining,fixed_lots=None):
        self._fixed()
        if self.state!='NEW':raise ValueError('trade already prepared')
        for v in (entry_price,initial_stop,target_price):number(v)
        if not isinstance(aggregate_risk_remaining,Decimal) or not aggregate_risk_remaining.is_finite() or aggregate_risk_remaining<0:
            raise ValueError('explicit nonnegative finite aggregate budget required')
        if aggregate_risk_remaining==0:
            return self._event('REJECT',reason='AGGREGATE_RISK_EXHAUSTED')
        decision=self.engine.evaluate(rule_id,observation)
        if decision.status!='ELIGIBLE':
            return self._event(decision.status,reasons=decision.reasons,entry_decision=decision)
        sign=Decimal(1) if observation.side=='BUY' else Decimal(-1)
        if sign*(target_price-entry_price)<=0:
            return self._event('REJECT',reason='TARGET_WRONG_SIDE')
        budget=min(self.box.risk_budget,aggregate_risk_remaining)
        sized=size_position(observation.side,entry_price,initial_stop,budget,self.instrument,self.costs)
        if sized['status']!='ACCEPT':return self._event('REJECT',reason=sized['reason'])
        if fixed_lots is not None:
            number(fixed_lots)
            if fixed_lots<self.instrument.min_lot or fixed_lots%self.instrument.lot_step:
                return self._event('REJECT',reason='FIXED_LOT_OUTSIDE_CONTRACT_GRID')
            if fixed_lots>sized['lots']:
                return self._event('REJECT',reason='REQUESTED_FIXED_LOT_EXCEEDS_DECLARED_RISK_BUDGET')
            maximum_budget_lots=sized['lots']
            fixed_loss=sized['modeled_loss']/maximum_budget_lots*fixed_lots
            sized={**sized,'lots':fixed_lots,'modeled_loss':fixed_loss,'volume_policy':'EXPLICIT_FIXED_LOT',
                   'maximum_budget_lots':maximum_budget_lots}
        self.plan=MappingProxyType(dict(side=observation.side,entry=entry_price,stop=initial_stop,target=target_price,
                       lots=sized['lots'],risk_budget=budget,box_fingerprint=self._box_fp,
                       target_definition=self.box.target_definition,
                       volume_policy='EXPLICIT_FIXED_LOT' if fixed_lots is not None else 'RISK_BUDGET_SIZING'))
        self.last_at=observation.at;self.current_stop=initial_stop;self.state='PREPARED'
        return self._event('PAPER_ENTRY_INTENT',plan=self.plan.copy(),entry_decision=decision,
                           sizing=sized,execution_authorized=False)

    def fill_entry(self,fill_price,lots):
        self._fixed()
        if self.state!='PREPARED':raise ValueError('prepared intent required')
        number(fill_price);number(lots)
        if self.plan['volume_policy']=='EXPLICIT_FIXED_LOT' and lots!=self.plan['lots']:
            raise ValueError('fixed-lot paper replay must retain requested volume')
        if lots>self.plan['lots'] or lots<self.instrument.min_lot or lots%self.instrument.lot_step:
            raise ValueError('fill volume outside planned contract grid')
        self.fill=MappingProxyType(dict(entry=fill_price,lots=lots))
        sign=Decimal(1) if self.plan['side']=='BUY' else Decimal(-1)
        distance=sign*(fill_price-self.plan['stop'])
        modeled_loss=((distance+self.costs.adverse_price_allowance)*self.instrument.money_per_price_unit_per_lot+self.costs.round_trip_fee_per_lot)*lots
        invalid=distance<=0 or sign*(self.plan['target']-fill_price)<=0 or modeled_loss>self.plan['risk_budget']
        self.modeled_exposure=max(Decimal(0),modeled_loss)
        self.budget_overrun=modeled_loss>self.plan['risk_budget']
        self.state='OPEN_REVIEW' if invalid else 'OPEN'
        return self._event(self.state,fill=self.fill.copy(),modeled_loss=modeled_loss,
                           reason='FILL_RECORDED_REQUIRES_REVIEW' if invalid else 'PAPER_FILL_RECORDED',realized_pnl=None)

    def quote(self,bid,ask,at):
        self._fixed();self._time(at);number(bid);number(ask)
        if bid>ask:raise ValueError('bid exceeds ask')
        if self.state not in ('OPEN','OPEN_REVIEW'):raise ValueError('open paper trade required')
        self.last_at=at
        side=self.plan['side'];exit_quote=bid if side=='BUY' else ask
        stop=exit_quote<=self.current_stop if side=='BUY' else exit_quote>=self.current_stop
        target=exit_quote>=self.plan['target'] if side=='BUY' else exit_quote<=self.plan['target']
        if stop or target:
            self.state='EXIT_PENDING_FILL'
            return self._event('EXIT_TRIGGER',reason='STOP' if stop else 'TARGET',
                               exit_quote=exit_quote,quote_side='BID' if side=='BUY' else 'ASK',
                               at=at,realized_pnl=None,fill_assumed=False)
        return self._event('NO_EXIT_TRIGGER',at=at,realized_pnl=None)

    def manage(self,label,new_stop,trigger,at):
        self._fixed();self._time(at)
        # A rejected/reviewed management observation still advances the causal clock.
        # Otherwise a later direct manage() call could replay an earlier timestamp.
        if self.state in ('OPEN','OPEN_REVIEW'):
            self.last_at=at
        if self.state=='OPEN_REVIEW':
            return self._event('REVIEW',reason='INVALID_ENTRY_FILL_REQUIRES_REVIEW_BEFORE_MANAGEMENT',realized_pnl=None)
        if self.state!='OPEN':raise ValueError('open paper trade required')
        if label=='fulltarget':
            return self._event('REJECT',reason='FULLTARGET_IS_EXIT_OUTCOME_NOT_STOP_MOVE')
        if label not in self.box.management_choices:
            return self._event('REJECT',reason='MANAGEMENT_NOT_IN_FIXED_BOX')
        if (not isinstance(trigger,Fact) or trigger.value is not True
                or type(trigger.known_at) is not int or trigger.known_at<0
                or trigger.known_at>at or not isinstance(trigger.source,str)
                or not trigger.source.strip()):
            return self._event('REVIEW',reason='MANAGEMENT_TRIGGER_NOT_ESTABLISHED')
        result=move_stop(label,self.plan['side'],self.fill['entry'],self.plan['stop'],
                         self.current_stop,new_stop,self.fill['lots'],self.instrument,self.costs)
        if result['status']=='ACCEPT':self.current_stop=new_stop;self.last_at=at
        return self._event(result['status'],management=result,trigger_source=trigger.source,
                           trigger_known_at=trigger.known_at,at=at,realized_pnl=None)

    def close(self,exit_fill,actual_round_trip_fee):
        self._fixed()
        if self.state not in ('OPEN','OPEN_REVIEW','EXIT_PENDING_FILL','CLOSED_PENDING_COST'):raise ValueError('open or pending-cost paper trade required')
        if self.exit_fill is not None:
            if exit_fill is not None and exit_fill!=self.exit_fill:raise ValueError('recorded exit fill cannot be changed')
            exit_fill=self.exit_fill
        result=account_fill(self.plan['side'],self.fill['entry'],exit_fill,self.fill['lots'],self.instrument,actual_round_trip_fee)
        if exit_fill is not None:
            self.exit_fill=exit_fill
            self.state='CLOSED_PENDING_COST'
        if result['status']=='CLOSED':self.state='CLOSED'
        return self._event(result['status'],accounting=result)

def execution_event(trade,event,available_at,fill_lots=None):
    """Shared timed/source-checked offline dispatch, never inventing fill evidence.

    available_at is coordinator clock; event at is occurrence and known_at is
    availability. Both paths require all three explicit timestamps/source fields.
    """
    def moment(v):
        if type(v) is not int or v<0:raise ValueError('explicit nonnegative event time required')
        return v
    def exact(v):
        if type(v) not in (str,int,Decimal):raise ValueError('exact event decimal required')
        n=Decimal(v)
        if not n.is_finite():raise ValueError('finite event decimal required')
        return n
    at=moment(event['at']);known=moment(event['known_at']);moment(available_at)
    if known<at or known>available_at:raise ValueError('event availability inconsistent with coordinator clock')
    if trade.last_coordinator_at is not None and available_at<trade.last_coordinator_at:
        raise ValueError('coordinator clock must be nondecreasing')
    source=event['source']
    if not isinstance(source,str) or not source.strip():raise ValueError('execution event source required')
    trade._time(at)
    # Events are consumed only when available; later dispatches cannot rewind
    # the evidence-availability clock even if occurrence timestamps ascend.
    if trade.last_event_known_at is not None and known<trade.last_event_known_at:
        raise ValueError('event availability must be nondecreasing')
    kind=event['event']
    if kind=='fill_entry':
        lots=exact(event['lots']) if fill_lots is None else fill_lots
        r=trade.fill_entry(exact(event['fill_price']),lots)
    elif kind=='quote':r=trade.quote(exact(event['bid']),exact(event['ask']),at)
    elif kind=='manage':
        trigger=event['trigger']
        f=Fact(trigger['value'],trigger['known_at'],trigger['source']) if isinstance(trigger,dict) else Fact(trigger,known,source)
        r=trade.manage(event['label'],exact(event['new_stop']),f,at)
    elif kind=='close':
        r=trade.close(None if event.get('exit_fill') is None else exact(event['exit_fill']),
                      None if event.get('actual_round_trip_fee') is None else exact(event['actual_round_trip_fee']))
    else:raise ValueError('unsupported execution event')
    trade.last_at=at
    trade.last_event_known_at=known
    trade.last_coordinator_at=available_at
    metadata=dict(event_at=at,event_known_at=known,event_source=source)
    r.update(metadata);trade.trace[-1].update(metadata)
    return r
