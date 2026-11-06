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

    def prepare(self,rule_id,observation,entry_price,initial_stop,target_price,aggregate_risk_remaining):
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
        self.plan=MappingProxyType(dict(side=observation.side,entry=entry_price,stop=initial_stop,target=target_price,
                       lots=sized['lots'],risk_budget=budget,box_fingerprint=self._box_fp,
                       target_definition=self.box.target_definition))
        self.last_at=observation.at;self.current_stop=initial_stop;self.state='PREPARED'
        return self._event('PAPER_ENTRY_INTENT',plan=self.plan.copy(),entry_decision=decision,
                           sizing=sized,execution_authorized=False)

    def fill_entry(self,fill_price,lots):
        self._fixed()
        if self.state!='PREPARED':raise ValueError('prepared intent required')
        number(fill_price);number(lots)
        if lots>self.plan['lots'] or lots<self.instrument.min_lot or lots%self.instrument.lot_step:
            raise ValueError('fill volume outside planned contract grid')
        self.fill=MappingProxyType(dict(entry=fill_price,lots=lots))
        sign=Decimal(1) if self.plan['side']=='BUY' else Decimal(-1)
        distance=sign*(fill_price-self.plan['stop'])
        modeled_loss=((distance+self.costs.adverse_price_allowance)*self.instrument.money_per_price_unit_per_lot+self.costs.round_trip_fee_per_lot)*lots
        invalid=distance<=0 or sign*(self.plan['target']-fill_price)<=0 or modeled_loss>self.plan['risk_budget']
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
            return self._event('EXIT_TRIGGER',reason='STOP' if stop else 'TARGET',
                               exit_quote=exit_quote,quote_side='BID' if side=='BUY' else 'ASK',
                               at=at,realized_pnl=None,fill_assumed=False)
        return self._event('NO_EXIT_TRIGGER',at=at,realized_pnl=None)

    def manage(self,label,new_stop,trigger,at):
        self._fixed();self._time(at)
        if self.state not in ('OPEN','OPEN_REVIEW'):raise ValueError('open paper trade required')
        if label not in self.box.management_choices:
            return self._event('REJECT',reason='MANAGEMENT_NOT_IN_FIXED_BOX')
        if not isinstance(trigger,Fact) or trigger.value is not True or trigger.known_at>at:
            return self._event('REVIEW',reason='MANAGEMENT_TRIGGER_NOT_ESTABLISHED')
        result=move_stop(label,self.plan['side'],self.fill['entry'],self.plan['stop'],
                         self.current_stop,new_stop,self.fill['lots'],self.instrument,self.costs)
        if result['status']=='ACCEPT':self.current_stop=new_stop;self.last_at=at
        return self._event(result['status'],management=result,trigger_source=trigger.source,
                           trigger_known_at=trigger.known_at,at=at,realized_pnl=None)

    def close(self,exit_fill,actual_round_trip_fee):
        self._fixed()
        if self.state not in ('OPEN','OPEN_REVIEW','CLOSED_PENDING_COST'):raise ValueError('open or pending-cost paper trade required')
        if self.exit_fill is not None:
            if exit_fill is not None and exit_fill!=self.exit_fill:raise ValueError('recorded exit fill cannot be changed')
            exit_fill=self.exit_fill
        result=account_fill(self.plan['side'],self.fill['entry'],exit_fill,self.fill['lots'],self.instrument,actual_round_trip_fee)
        if exit_fill is not None:
            self.exit_fill=exit_fill
            self.state='CLOSED_PENDING_COST'
        if result['status']=='CLOSED':self.state='CLOSED'
        return self._event(result['status'],accounting=result)
