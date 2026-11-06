"""Connected offline execution ledger. Source events are fills, never bar touches.

Explicit specs bind one decision to its source-backed stop/target/contract/box.
No inferred OHLC fill ordering, chosen risk ratio, fee or contract multiplier.
Missing specs block execution transparently rather than fabricate zero PnL.
"""
from decimal import Decimal
from capital import Instrument,Costs,BoxPlan
from entry_engine import Fact
from trade_machine import TradeMachine

def exact(v,positive=False):
    if type(v) not in (str,int,Decimal):raise ValueError('exact decimal required')
    n=Decimal(v)
    if not n.is_finite() or n<0 or positive and n==0:raise ValueError('nonnegative finite decimal required')
    return n

def moment(t):
    if type(t) is not int or t<0:raise ValueError('nonnegative integer time required')
    return t

class MonthlyExecutor:
    def __init__(self,engine,initial_cash,fixed_lots,document=None):
        self.engine=engine;self.initial_cash=exact(initial_cash,True);self.cash=self.initial_cash
        self.lots=exact(fixed_lots,True);self.trades={};self.records=[];self.accepted_decisions=0
        self.closed_ids=set();self.specs={};self.events=[];self.last_at=None;self.finished=False
        self.boxes={};self.instrument_models={};self.cost_models={}
        document={} if document is None else document
        for spec in document.get('specs',[]):
            key=(moment(spec['at']),spec['side'],spec['rule_id'])
            if key in self.specs:raise ValueError('duplicate execution specification')
            if not isinstance(spec.get('source'),str) or not spec['source'].strip():raise ValueError('execution source required')
            moment(spec['known_at']);self.specs[key]=dict(spec)
        for e in document.get('events',[]):
            moment(e['at']);moment(e['known_at'])
            if e['known_at']<e['at']:raise ValueError('event cannot be available before occurrence')
            if not isinstance(e.get('source'),str) or not e['source'].strip():raise ValueError('event source required')
            self.events.append(dict(e))
        if any(a['known_at']>b['known_at'] for a,b in zip(self.events,self.events[1:])):
            raise ValueError('execution events must be in availability order')

    def _record(self,kind,**values):
        r={'kind':kind,**values};self.records.append(r);return r

    def _reserved(self):
        return sum((t.plan['risk_budget'] for t in self.trades.values() if t.state!='CLOSED'),Decimal(0))

    def accept(self,decision,observation):
        if self.finished:raise ValueError('replay already finished')
        if decision.status!='ELIGIBLE':return None
        self.accepted_decisions+=1
        key=(observation.at,observation.side,decision.rule_id);s=self.specs.get(key)
        if s is None:return self._record('EXECUTION_BLOCKED',at=observation.at,side=observation.side,
            rule_id=decision.rule_id,reason='MISSING_SOURCE_BACKED_EXECUTION_SPEC')
        if s['known_at']>observation.at:return self._record('EXECUTION_BLOCKED',at=observation.at,
            reason='FUTURE_EXECUTION_SPEC',side=observation.side,rule_id=decision.rule_id)
        trade_id=s['trade_id']
        if not isinstance(trade_id,str) or not trade_id or trade_id in self.trades:raise ValueError('unique trade id required')
        i,c,b=s['instrument'],s['costs'],s['box']
        instrument=Instrument(exact(i['money_per_price_unit_per_lot'],True),exact(i['min_lot'],True),exact(i['lot_step'],True))
        costs=Costs(exact(c['round_trip_fee_per_lot']),exact(c['adverse_price_allowance']))
        box=BoxPlan(b['box_id'],exact(b['risk_budget'],True),b['target_definition'],tuple(b['management_choices']),b['declared_before_box'])
        instrument_id=s.get('instrument_model_id','EXPLICIT_SINGLE_CONTRACT_MODEL')
        cost_id=s.get('cost_model_id','EXPLICIT_SINGLE_COST_MODEL')
        for registry,key,value in ((self.boxes,box.box_id,box.fingerprint),
                                   (self.instrument_models,instrument_id,instrument),
                                   (self.cost_models,cost_id,costs)):
            if not isinstance(key,str) or not key.strip():raise ValueError('nonempty model identity required')
            if key in registry and registry[key]!=value:raise ValueError('fixed box or model identity changed: '+key)
        t=TradeMachine(self.engine,box,instrument,costs)
        remaining=max(Decimal(0),self.cash-self._reserved())
        result=t.prepare(decision.rule_id,observation,exact(s['entry_price'],True),exact(s['initial_stop'],True),
            exact(s['target_price'],True),remaining,fixed_lots=self.lots)
        if result['status']=='PAPER_ENTRY_INTENT':
            self.trades[trade_id]=t;self.boxes[box.box_id]=box.fingerprint
            self.instrument_models[instrument_id]=instrument;self.cost_models[cost_id]=costs
        return self._record('ENTRY_PREPARATION',trade_id=trade_id,at=observation.at,side=observation.side,
            rule_id=decision.rule_id,source=s['source'],result=result)

    def advance(self,at,strict=False):
        moment(at)
        if self.last_at is not None and at<self.last_at:raise ValueError('replay clock cannot move backwards')
        self.last_at=at;pending=[]
        for e in self.events:
            if e['known_at']>at:pending.append(e);continue
            t=self.trades.get(e['trade_id'])
            if t is None:
                if strict:self._record('EXECUTION_EVENT_UNMATCHED',trade_id=e['trade_id'],at=e['at'],reason='NO_PREPARED_ENTRY')
                else:pending.append(e)
                continue
            if e['at']<t.last_at:raise ValueError('execution event precedes known trade history')
            k=e['event']
            if k=='fill_entry':r=t.fill_entry(exact(e['fill_price'],True),self.lots)
            elif k=='quote':r=t.quote(exact(e['bid'],True),exact(e['ask'],True),e['at'])
            elif k=='manage':
                r=t.manage(e['label'],exact(e['new_stop'],True),Fact(e['trigger'],e['known_at'],e['source']),e['at'])
            elif k=='close':r=t.close(None if e.get('exit_fill') is None else exact(e['exit_fill'],True),
                None if e.get('actual_round_trip_fee') is None else exact(e['actual_round_trip_fee']))
            else:raise ValueError('unsupported execution event')
            # fill/close methods have no clock argument; the coordinator enforces it.
            t.last_at=e['at']
            if t.state=='CLOSED' and e['trade_id'] not in self.closed_ids:
                self.cash+=r['accounting']['net_pnl'];self.closed_ids.add(e['trade_id'])
            self._record('EXECUTION_EVENT',trade_id=e['trade_id'],at=e['at'],known_at=e['known_at'],
                source=e['source'],event=k,result=r)
        self.events=pending

    def summary(self):
        opened=[t for t in self.trades.values() if t.fill is not None]
        return {'monthly_trade_executor_connected':True,'eligible_decisions_routed':self.accepted_decisions,
            'paper_intents':len(self.trades),'paper_trades_opened':len(opened),
            'paper_buy_trades':sum(t.plan['side']=='BUY' for t in opened),
            'paper_sell_trades':sum(t.plan['side']=='SELL' for t in opened),
            'closed_trades':len(self.closed_ids),'unresolved_trades':sum(t.state!='CLOSED' for t in self.trades.values()),
            'awaiting_entry_fill':sum(t.state=='PREPARED' for t in self.trades.values()),
            'filled_open_trades':sum(t.state in ('OPEN','OPEN_REVIEW') for t in self.trades.values()),
            'closed_pending_cost':sum(t.state=='CLOSED_PENDING_COST' for t in self.trades.values()),
            'pending_events_after_cutoff':len(self.events),
            'unmatched_execution_events':sum(r['kind']=='EXECUTION_EVENT_UNMATCHED' for r in self.records),
            'execution_blocked':sum(r['kind']=='EXECUTION_BLOCKED' for r in self.records),
            'initial_cash_usd':str(self.initial_cash),'requested_fixed_lots':str(self.lots),
            'bookkeeping_cash_end_usd':str(self.cash),'bookkeeping_cash_change_usd':str(self.cash-self.initial_cash),
            'actual_lot_applied':bool(opened),'orders_sent':0}
