"""Research adapter to original pure sizing/risk/trailing functions. No broker.

Operational risk vetoes remain UNASSESSED, never converted into authorization.
Bar-close trailing is a declared approximation to the live quote-driven cycle.
"""
from dataclasses import replace, asdict
from decimal import Decimal as D
from historical_candidates import SOURCE  # explicit source location, imports pure strategy
from amin_mt5.model import Policy, SymbolSpec, Exposure, Account, Stage, Market, Intent
from amin_mt5.strategy import size_and_target
from amin_mt5.risk import evaluate, update_stage
from amin_mt5.adaptive_exit import plan as trailing
from amin_mt5.learning import fit

UNASSESSED = frozenset(('DEMO_ACCOUNT_REQUIRED','DISCONNECTED','MARKET_CLOSED',
    'NEWS_NOT_CLEARED','RECONCILIATION_REQUIRED','MARGIN_LIMIT'))

class Management:
    def __init__(self, capital='10000', policy=None, spec=None, adaptive_exit=True):
        if type(adaptive_exit) is not bool:raise ValueError('EXIT_MODE')
        self.adaptive_exit=adaptive_exit
        self.policy=policy or Policy(); self.spec=spec or SymbolSpec()
        self.equity=D(capital)
        if not self.equity.is_finite() or self.equity<=0:raise ValueError('CAPITAL')
        self.stage=Stage.initial('',Account('OFFLINE_SCENARIO',str(self.equity),'0'))
        self.exposure=Exposure();self.failures=[];self.peak=None;self.blocked=False
        self.sampled_equity=[];self.stage_trace=[]

    def prepare(self, setup, entry, bar, history, spread):
        if self.blocked:raise ValueError('UNRESOLVED_CAPITAL_PATH')
        if not isinstance(setup,dict):raise ValueError('ORIGINAL_PLAN_REQUIRED')
        now=bar['time']*1000;p=self.policy;s=self.spec
        self.stage=update_stage(self.stage,str(self.equity),now,p)
        order=size_and_target(setup,str(entry),self.stage.active_capital,str(self.equity),
            s,policy=p,exposure=self.exposure)
        if order is None:
            self.failures.append(dict(time=bar['time'],reasons=['SIZING_REJECTED']))
            return None
        vol=D(order['volume']);stop=D(order['stop_loss'])
        quote=bar['open']+(spread if setup['side']=='buy' else D(0))
        # Conservative original risk envelope; actual scenario fee is separately recorded.
        risk=(max(abs(entry-stop),abs(quote-stop))+D(p.max_slippage))*vol*D(s.contract_size)+D(p.commission_per_lot)*vol
        account=Account('OFFLINE_SCENARIO',str(self.equity),'0',mode='unknown')
        market=Market(str(bar['open']),str(bar['open']+spread),
            str(history[-1]['close']+spread/2),now,now,connected=False,session_open=False,news_clear=False)
        intent=Intent('offline',s.symbol,setup['side'],str(vol),str(stop),str(entry),now,
            'OFFLINE_DIAGNOSTIC',('SYNTHETIC_EXECUTION_CONTEXT',),'0',str(risk),take_profit='0')
        result=evaluate(p,self.stage,account,s,market,self.exposure,intent,now,reconciled=False)
        self.stage=result.stage
        failures=[x for x in result.reasons if x not in UNASSESSED]
        if failures:
            self.failures.append(dict(time=bar['time'],reasons=failures));return None
        self.stage=replace(self.stage,daily_orders=self.stage.daily_orders+1)
        self.peak=entry
        return dict(volume=str(vol),stop_loss=str(stop),initial_risk_usd=str(risk),equity_before=str(self.equity))

    def on_close(self,entry,initial,side,quote,old,closed,vol,fee,slip):
        if any(b['time']>closed[-1]['time'] for b in closed):raise ValueError('LOOKAHEAD_CLOSE')
        sign=D(1) if side=='buy' else D(-1)
        marked=self.equity+sign*(quote-sign*slip-entry)*D(self.spec.contract_size)*vol-fee*vol
        self.sampled_equity.append(str(marked))
        if marked<=0:
            self.blocked=True
            return dict(should_modify=False,reason='NONPOSITIVE_SCENARIO_EQUITY')
        self.stage=update_stage(self.stage,str(marked),(closed[-1]['time']+900)*1000,self.policy)
        self.stage_trace.append(asdict(self.stage))
        if not self.adaptive_exit:return dict(should_modify=False,reason='FIXED_EXIT_CONTROL')
        if len(closed)<14:return dict(should_modify=False,reason='ATR_WARMUP')
        atr=sum((b['high']-b['low'] for b in closed[-14:]),D(0))/14
        if atr<=0:return dict(should_modify=False,reason='ATR_ZERO')
        result=trailing(entry,initial,side,quote,old,self.peak,atr,
            self.spec.tick_size,self.spec.minimum_stop_distance,
            D(self.policy.commission_per_lot)/D(self.spec.contract_size)+D(self.policy.max_slippage))
        self.peak=D(result['peak_price'])
        return result

    def settle(self,net,time):
        if net is None:self.blocked=True;return
        self.equity+=net
        if self.equity<=0:self.blocked=True;return
        self.stage=update_stage(self.stage,str(self.equity),time*1000,self.policy)

def train_past(rows, cutoff):
    """Independent temporal protocol. Exit labels must be available before cutoff."""
    past=[r for r in rows if r['time']<cutoff]
    model=fit(past)
    return dict(status='NO_TRAIN/INSUFFICIENT_SAMPLE' if model is None else 'TRAIN_PAST_ONLY',
                train_rows=len(past),cutoff=cutoff,model=model)
