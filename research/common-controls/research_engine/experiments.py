"""Research revision of amin_mt5.experiments: same candidates, causal splits,
learning fit and validation selector; execution is injected through the existing bridge.
No production import points to this module. No financial approval is emitted.
"""
from dataclasses import asdict
from decimal import Decimal
from amin_mt5.strategy import candidates
from amin_mt5.learning import fit
from registry import digest

POLICIES=('stop_first','target_first','unknown')

def metrics(rows):
    resolved=all(r['net'] is not None for r in rows)
    values=[Decimal(str(r['net'])) for r in rows if r['net'] is not None]
    equity=peak=dd=Decimal(0)
    for v in values:
        equity+=v;peak=max(peak,equity);dd=max(dd,peak-equity)
    return dict(trades=len(rows),net_usd=float(equity) if resolved else None,
        max_drawdown_usd=float(dd) if resolved else None,unknown=sum(r['net'] is None for r in rows),
        unclosed=sum(r['trace']['exit_reason']=='DATA_END_MARK' for r in rows),
        rows=rows)

def rank(records,minimum_trades=8):
    """Only validation enters this function. Unknown costs/path never become zero."""
    comparable=len({r['comparison_hash'] for r in records})<=1
    ranked=[]
    for r in records:
        scenarios=r['validation'];reasons=[]
        if not comparable:reasons.append('INCOMPARABLE_ASSUMPTIONS')
        if any(s['net_usd'] is None for s in scenarios.values()):reasons.append('UNKNOWN_COST_OR_PATH')
        if any(s['unclosed'] for s in scenarios.values()):reasons.append('UNCLOSED')
        if any(s['trades']<minimum_trades for s in scenarios.values()):reasons.append('INSUFFICIENT_TRADES')
        worst=None if any(s['net_usd'] is None for s in scenarios.values()) else min(s['net_usd'] for s in scenarios.values())
        dd=None if any(s['max_drawdown_usd'] is None for s in scenarios.values()) else max(s['max_drawdown_usd'] for s in scenarios.values())
        if worst is not None and worst<=0:reasons.append('NONPOSITIVE_WORST_CASE')
        ranked.append(dict(id=r['id'],worst_case_net=worst,max_drawdown=dd,score=None if reasons else worst-dd,
            reasons=reasons,status='BLOCKED' if reasons else 'HYPOTHETICAL_SCENARIO_ONLY',profitability_verified=False))
    eligible=[r for r in ranked if r['score'] is not None]
    eligible.sort(key=lambda r:(-r['score'],r['id']))
    return dict(rows=ranked,scenario_nominee=eligible[0]['id'] if eligible else None,
        verified_best=None,selection_uses_holdout=False,comparable=comparable)

def run_experiment(bars,contexts,*,evaluate,minimum_trades=8,before_holdout=None):
    """Migrate the existing selector to all three execution policies and stresses.
    Fit is train-only and conservative; holdout is consumed only after selection.
    """
    n=len(bars)
    if n<240:raise ValueError('MINIMUM_240_BARS')
    if set(contexts)!= {'base','stress'}:raise ValueError('BASE_AND_STRESS_REQUIRED')
    train_end=n//2;validation_end=n*3//4;embargo=8
    comparison_hash=digest(contexts);results=[];private={}
    def scenarios(start,end,candidate,model=None):
        return {label+':'+policy:metrics(evaluate(bars,start,end,context,candidate,model,policy))
            for label,context in contexts.items() for policy in POLICIES}
    for candidate in candidates():
        train=scenarios(44,train_end,candidate)
        # Unknown labels are never trained; even assumed explicit labels remain hypothetical.
        training=train['stress:stop_first']['rows']
        model=fit([r for r in training if r['trace']['exit_reason']!='DATA_END_MARK']) if all(r['net'] is not None for r in training) else None
        for learned in (False,True):
            if learned and model is None:continue
            fitted=model if learned else None
            ident=candidate.id+('-learned' if learned else '-rules')
            validation=scenarios(train_end+embargo,validation_end,candidate,fitted)
            record=dict(id=ident,candidate=asdict(candidate),model=fitted,train=train,validation=validation,comparison_hash=comparison_hash)
            results.append(record);private[ident]=(candidate,fitted)
    ranking=rank(results,minimum_trades);selected=ranking['scenario_nominee']
    if before_holdout is not None:before_holdout()
    # Sealed here by control flow. Diagnostics on holdout must not reselect.
    holdout=scenarios(validation_end+embargo,n,*private[selected]) if selected else None
    baseline=scenarios(validation_end+embargo,n,candidates()[0])
    return dict(schema=4,method='existing-selector-cost-scenarios-research-revision',candidates=results,
        ranking=ranking,scenario_nominee=selected,selected_candidate=None,out_of_sample=holdout,
        fixed_breakout_baseline=baseline,no_trade_baseline_usd=0,
        split=dict(train=[44,train_end],validation=[train_end+embargo,validation_end],holdout=[validation_end+embargo,n],embargo_bars=embargo),
        selection_uses_holdout=False,market_profitability_verified=False,final_year_validation='BLOCKED',
        trade_allowed=False,demo_review_eligible=False,promotion_eligible=False,live_promotion=False,
        limitations=['Hypothetical research ranking only','Bar-open spread is not intrabar Ask history',
                    'Historical swap and server/session evidence remain unverified','Global fresh-holdout certification not provided'])
