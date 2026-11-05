"""Execution hook for the existing research runner, reusing strategy/risk/learning.
The installed robot and original evaluator are not modified.
"""
from dataclasses import replace
from datetime import datetime,timezone
from decimal import Decimal
from amin_mt5.strategy import plan,size_and_target
from amin_mt5.learning import predict
from amin_mt5.model import SymbolSpec,Stage,Account,Policy
from amin_mt5.risk import update_stage
from execution_scenarios import replay,spread_at

def evaluate_segment(bars,start,end,context,candidate,model=None,intrabar_policy='stop_first'):
    candidate.validate();i=max(start,candidate.lookback+4);rows=[];equity=10000.0;control_equities={}
    policy=Policy();spec=SymbolSpec(contract_size='100')
    day=datetime.fromtimestamp(bars[i]['time'],timezone.utc).date().isoformat()
    stage=Stage.initial(day,Account('research','10000','10000','demo'))
    while i<end-1:
        entry_index=i+1;entry_time=bars[entry_index]['time']
        stage=update_stage(stage,str(equity),entry_time*1000,policy)
        if equity<=10000*(1-float(policy.max_total_drawdown)) or float(stage.active_capital)<float(policy.minimum_active):break
        if (equity<=float(stage.day_start_equity)*(1-float(policy.max_daily_drawdown)) or
            (policy.daily_profit_target_halts and equity>=float(stage.day_start_equity)*(1+float(policy.daily_profit_target))) or
            (policy.max_daily_orders is not None and stage.daily_orders>=policy.max_daily_orders)):
            i+=1;continue
        # Pass only information actually available by the decision boundary.
        history=[b for b in bars[max(0,i-65):i+1] if b['observed_at']<=entry_time]
        setup=plan(history,entry_time,candidate)
        if not setup or predict(model,setup['learning_features'])<.55:i+=1;continue
        if setup['signal_time']+900>entry_time:raise ValueError('LOOKAHEAD_SIGNAL')
        spread,_=spread_at(entry_time,context.get('quotes',{}),context.get('assumed_spread'),context.get('receipt_ids',()))
        direction=1 if setup['side']=='buy' else -1
        entry=Decimal(str(bars[entry_index]['open']))+(spread if direction==1 else 0)+direction*Decimal(str(context['slippage']))
        sizing=size_and_target(setup,str(entry),stage.active_capital,str(equity),spec,str(context['slippage']),str(context['commission']),policy=policy)
        if not sizing:i+=1;continue
        if context.get('exit_policy','adaptive_existing') not in ('adaptive_existing','fixed_sltp'):raise ValueError('EXIT_POLICY')
        target=sizing.get('take_profit') if context.get('exit_policy')=='fixed_sltp' else None
        order=dict(side=setup['side'],signal_available=entry_time,lots=sizing['volume'],contract=100,stop=sizing['stop_loss'],target=target)
        kwargs={k:context[k] for k in ('quotes','receipt_ids','assumed_spread','slippage','swap','assumed_swap','commission','swap_schedule') if k in context}
        # Existing strategies have adaptive stops and no fixed TP; controlled tests may use TP.
        adaptive=None if order['target'] is not None else dict(initial_atr=max(float(setup['features']['range_atr_proxy']),.01),tick_size=spec.tick_size,minimum_stop_distance=spec.minimum_stop_distance)
        result=replay(bars[entry_index:end],order,**kwargs,intrabar_policy=intrabar_policy,adaptive=adaptive)
        net=result['net_with_known_costs']
        row=dict(time=result['exit_time'],entry_time=entry_time,signal_time=setup['signal_time'],net=None if net is None else float(net),learning_features=setup['learning_features'],trace=result,order=order)
        if context.get('matched_control_spec') is not None:
            from matched_controls import SPEC,paired
            if context['matched_control_spec']!=SPEC:raise ValueError('CONTROL_PROTOCOL_CHANGED')
            row['matched_controls']=paired(bars[entry_index:end],order,context,adaptive,intrabar_policy,result,equity,control_equities)
        rows.append(row)
        # Cannot safely size or learn subsequent orders from an unknown equity path.
        if net is None:break
        equity+=float(net);stage=replace(stage,daily_orders=stage.daily_orders+1)
        i=next((k for k in range(entry_index,end) if bars[k]['time']+900==result['exit_time']),end-1)+1
    return rows
