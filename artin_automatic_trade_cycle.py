"""Automated signal -> FXM risk gate -> paper position -> TP/SL -> PnL.

No external human-provided SETUP events. The recognizer reads only closed
OHLC from the broker file. This simulator is a *scenario*, NOT a successful
teacher-semantics test or a live broker fill. Every simulation input is explicit
because the uploaded candle file lacks true bid/ask, costs and lot contract.

Unlike the prior manually annotated 13-route motor this has a real unattended
OHLC decision loop. Two measurable PDF subsets are recognized; other 11
routes must not be mislabeled as implemented.
"""
from __future__ import annotations
import argparse,json,hashlib
from dataclasses import dataclass
from decimal import Decimal as D
from pathlib import Path
from core.capital import Instrument, Costs, size_position
from fxm_teacher_policy import AccountRisk, winrate_target_policy, proposed_multi_targets,day_trade_permission
from artin_automatic_teacher_recognizer import parse_bars, run_scan, AutoRecognizer, Bar, InputError

class ScenarioError(ValueError):pass

@dataclass
class Paper:
    signal:object
    side:str
    entry:D
    stop:D
    lots:D
    rr:D
    targets:tuple
    mode:str
    opened_at:int
    stage:int=0


def run_auto_paper(bars,*,initial_balance,reference_balance,risk_pct,winrate,winrate_source,
                   contract_value,min_lot,lot_step,round_trip_fee_per_lot,spread,mode='SINGLE_RR',
                   broker_day_offset_minutes=None):
    """Run a declared-parameters scenario on measured bars (not actual fills).

    Winrate is user/caller-supplied evidence, NOT measured from a hypothetical
    win rate on the same future bars. No parameter optimization/look-ahead.
    """
    if not bars:raise ScenarioError('NO_BARS')
    initial_balance,reference_balance,risk_pct=map(D,(initial_balance,reference_balance,risk_pct))
    winrate,spread=D(winrate),D(spread)
    if spread<0:raise ScenarioError('NEGATIVE_SPREAD')
    if not 1<=risk_pct<=2:raise ScenarioError('FXM_RISK_1_2_PERCENT_ONLY')
    if not isinstance(winrate_source,str) or not winrate_source.strip():
        raise ScenarioError('WINRATE_SOURCE_REQUIRED')
    if mode not in ('SINGLE_RR','THREE_TP'):raise ScenarioError('UNKNOWN_FXM_MODE')
    if mode=='THREE_TP':
        if not (D('45')<winrate<D('66')):raise ScenarioError('FXM_THREE_TP_BAND_REQUIRED')
        rr=D('1.8')
    else:
        policy=winrate_target_policy(str(winrate),evidence_source=winrate_source)
        if policy['status']!='RR_CANDIDATE_FROM_HANDOUT':
            raise ScenarioError('FXM_RR_NOT_UNAMBIGUOUS:'+policy['status'])
        rr=D(policy['rr'])
    instrument=Instrument(D(contract_value),D(min_lot),D(lot_step))
    costs=Costs(D(round_trip_fee_per_lot),D('0'))
    detector=AutoRecognizer();balance=initial_balance
    position=None;pending=[];trades=[];rejected={};new_signals=0
    stopped=False;stop_at=None;day=None;day_outcomes=[]
    if broker_day_offset_minutes is not None:
        if type(broker_day_offset_minutes) is not int or not -840<=broker_day_offset_minutes<=840:
            raise ScenarioError('INVALID_SOURCE_DECLARED_DAY_OFFSET')
    else:
        # Cannot apply FXM p.5 without the broker's clock/day definition.
        # Paper scenario remains diagnostic and records this missing protection.
        pass
    def block(reason):rejected[reason]=rejected.get(reason,0)+1
    def sign(side):return D(1) if side=='BUY' else D(-1)
    def exit_now(p,bar,reason,raw_exit):
        nonlocal position,balance,day_outcomes
        price=raw_exit
        # A gap through the active stop fills at the *worse* open in this
        # scenario; actual broker slippage is still unknown.
        if reason=='STOP' and sign(p.side)*(bar.open-p.stop)<0:
            price=bar.open if p.side=='BUY' else bar.open+spread
        gross=sign(p.side)*(price-p.entry)*p.lots*instrument.money_per_price_unit_per_lot
        fee=p.lots*costs.round_trip_fee_per_lot
        net=gross-fee
        balance+=net
        trades.append(dict(opened_at=p.opened_at,closed_at=bar.t+900,
            side=p.side,route=p.signal.route,zone_id=p.signal.zone_id,
            signal_at=p.signal.at,entry=str(p.entry),entry_reference=str(p.signal.observed_price),
            initial_stop=str(p.signal.operational_stop),final_stop=str(p.stop),
            exit=str(price),reason=reason,lots=str(p.lots),net_scenario=str(net),
            balance_after=str(balance),original_sources=p.signal.sources,
            intrabar_order_known=False,broker_fill_verified=False))
        day_outcomes.append('TP' if net>0 else 'SL')
        position=None
    for bar in bars:
        if broker_day_offset_minutes is not None:
            proposed_day=(bar.t+broker_day_offset_minutes*60)//86400
            if proposed_day!=day:
                day=proposed_day;day_outcomes=[]
        # Signal is only allowed when its decision bar has actually closed.
        if pending:
            eligible=[s for s in pending if s.at==bar.t]
            pending=[s for s in pending if s.at>bar.t]
            if eligible:
                if position is not None:block('ALREADY_IN_PAPER_POSITION')
                elif len(eligible)!=1:block('AMBIGUOUS_SIMULTANEOUS_SIGNALS')
                elif stopped:block('FXM_DRAWDOWN_STOP')
                elif broker_day_offset_minutes is not None and day_trade_permission(day_outcomes)['status']!='PAPER_DAY_SEQUENCE_CONTINUE':
                    block('FXM_DAILY_STOP')
                else:
                    candidate=eligible[0]
                    side=candidate.side
                    entry=bar.open+spread if side=='BUY' else bar.open
                    sl=D(candidate.operational_stop)
                    if sign(side)*(entry-sl)<=0:block('STRUCTURAL_STOP_INVALID_AT_NEXT_OPEN')
                    else:
                        ar=AccountRisk(balance,reference_balance,risk_pct).assess()
                        if ar['status']!='RISK_BUDGET_AVAILABLE':
                            stopped=True;stop_at=bar.t;block(ar['status'])
                        else:
                            sizing=size_position(side,entry,sl,D(ar['per_trade_risk_budget']),instrument,costs)
                            if sizing['status']!='ACCEPT':block('FXM_'+sizing['reason'])
                            else:
                                distance=sign(side)*(entry-sl)
                                if mode=='THREE_TP':
                                    targets=tuple(entry+sign(side)*distance*q for q in (D('0.8'),D('1.3'),D('1.8')))
                                else:targets=(entry+sign(side)*distance*rr,)
                                position=Paper(candidate,side,entry,sl,sizing['lots'],rr,targets,mode,bar.t)
        # Same candle's high/low cannot give a known intrabar path. Existing
        # stop is checked first. Newly moved SL takes effect next bar only.
        if position is not None:
            p=position
            hit_stop=(bar.low<=p.stop if p.side=='BUY' else bar.high+spread>=p.stop)
            if hit_stop:
                exit_now(p,bar,'STOP',p.stop)
            elif p.mode=='SINGLE_RR':
                hit_tp=(bar.high>=p.targets[0] if p.side=='BUY' else bar.low+spread<=p.targets[0])
                if hit_tp:exit_now(p,bar,'TP',p.targets[0])
            else:
                hit3=(bar.high>=p.targets[2] if p.side=='BUY' else bar.low+spread<=p.targets[2])
                hit2=(bar.high>=p.targets[1] if p.side=='BUY' else bar.low+spread<=p.targets[1])
                hit1=(bar.high>=p.targets[0] if p.side=='BUY' else bar.low+spread<=p.targets[0])
                if hit3:exit_now(p,bar,'TP3',p.targets[2])
                elif hit2 and p.stage<2:
                    p.stop=p.targets[0];p.stage=2
                elif hit1 and p.stage<1:
                    p.stop=p.entry;p.stage=1
        if AccountRisk(balance,reference_balance,risk_pct).assess()['status']!='RISK_BUDGET_AVAILABLE':
            stopped=True;stop_at=stop_at or bar.t
        emitted=detector.step(bar)
        if emitted:
            new_signals+=len(emitted)
            pending.extend(emitted)
    return dict(schema='artin_auto_teacher_paper_scenario_v1',mode=mode,
        engine='RAW_OHLC_AUTONOMOUS_PDF_SUBSET_NO_MANUAL_FACT_TAGS',
        bar_count=len(bars),signal_count=new_signals,candidate_counts=detector.counts,
        finished_trades=len(trades),open_position=None if position is None else dict(entry=str(position.entry),
            stop=str(position.stop),lots=str(position.lots),opened_at=position.opened_at),
        initial_balance=str(initial_balance),final_balance_scenario=str(balance),
        net_scenario=str(balance-initial_balance),risk_pct=str(risk_pct),
        scenario_winrate_pct=str(winrate),scenario_winrate_source=winrate_source,
        scenario_spread=str(spread),instrument_contract_scenario=str(instrument.money_per_price_unit_per_lot),
        round_trip_fee_per_lot_scenario=str(costs.round_trip_fee_per_lot),
        broker_day_offset_minutes_source_required=broker_day_offset_minutes is None,
        fxm_day_trading_sequence_applied=broker_day_offset_minutes is not None,
        stopped_on_20pct_drawdown=stopped,stop_at=stop_at,
        blocked_signals=rejected,
        trades=trades,
        assumptions=['next-bar-open paper fill, not guaranteed broker fill',
          'M15 OHLC intrabar ordering unknown: prior stop takes precedence over targets',
          'bid-only candles; declared constant spread scenario is not measured bid/ask',
          'stop at opposite FVG boundary is an operational structural reference, not teacher-certified choice',
          'winrate input is caller-provided and NOT generated from the future backtest',
          'not the full 13-route teacher algorithm'],
        strategy_semantics_verified=False,broker_fills_verified=False,orders_submitted=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bars',required=True);p.add_argument('--out',required=True)
    p.add_argument('--initial-balance',required=True);p.add_argument('--reference-balance',required=True)
    p.add_argument('--risk-pct',required=True)
    p.add_argument('--scenario-winrate',required=True);p.add_argument('--scenario-winrate-source',required=True)
    p.add_argument('--contract-value',required=True);p.add_argument('--min-lot',required=True)
    p.add_argument('--lot-step',required=True);p.add_argument('--fee-per-lot',required=True)
    p.add_argument('--spread',required=True)
    p.add_argument('--mode',choices=['SINGLE_RR','THREE_TP'],default='SINGLE_RR')
    p.add_argument('--broker-day-offset-minutes',type=int)
    a=p.parse_args();bars,digest=parse_bars(a.bars)
    result=run_auto_paper(bars,initial_balance=a.initial_balance,reference_balance=a.reference_balance,
        risk_pct=a.risk_pct,winrate=a.scenario_winrate,winrate_source=a.scenario_winrate_source,
        contract_value=a.contract_value,min_lot=a.min_lot,lot_step=a.lot_step,
        round_trip_fee_per_lot=a.fee_per_lot,spread=a.spread,mode=a.mode,
        broker_day_offset_minutes=a.broker_day_offset_minutes)
    result['input_sha256']=digest
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.resolve()==Path(a.bars).resolve():raise ScenarioError('NO_OVERWRITE_INPUT')
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('bar_count','signal_count','finished_trades','net_scenario','blocked_signals','strategy_semantics_verified','orders_submitted')},ensure_ascii=False))
if __name__=='__main__':main()