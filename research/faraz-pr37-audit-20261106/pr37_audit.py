"""Independent offline audit of unchanged PR37. No strategy tuning or broker API.

Private traces stay in --private-dir. --out contains aggregates only.
"""
from __future__ import annotations
import argparse, collections, contextlib, hashlib, importlib.util, json, math, statistics, sys
from datetime import datetime, timezone
from pathlib import Path
from metric_revision_v2 import snap_net
from safe_outputs_v2 import reject_aliases,write_json_atomic

POLICY_SHA='19c8578141bc6b7b3f50377efbdbbdb933fe72f6e4063a3cc2117de92c37fdb6'
NUMERIC_ADDENDUM_SHA='b2e6435bed90c30d818ea089aae4e903b8333876d767fd2749be160428dc18d2'

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def quarter(t):
    d=datetime.fromtimestamp(t,tz=timezone.utc)
    return f'{d.year}-Q{(d.month-1)//3+1}'
def rounded(x): return round(x,6) if x is not None else None
def load_reference(path):
    spec=importlib.util.spec_from_file_location('faraz_v1_reference',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module
def friction_usd(cost,units,lot):
    return (cost['spread_price']+2*cost['slippage_each_side_price'])*units+cost['commission_usd_per_lot_roundtrip']*lot
@contextlib.contextmanager
def costs(module,cost):
    names=('SPREAD_PRICE','SLIPPAGE_PRICE_EACH_SIDE','COMMISSION_USD_PER_LOT_ROUNDTRIP')
    old=[getattr(module,k) for k in names]
    try:
        for name,value in zip(names,(cost['spread_price'],cost['slippage_each_side_price'],cost['commission_usd_per_lot_roundtrip'])):setattr(module,name,value)
        yield
    finally:
        for k,v in zip(names,old):setattr(module,k,v)

def metrics(rows,cost_delta=0.,normalize=False):
    closed=[r for r in rows if r['pnl'] is not None]
    vals=[r['pnl']-cost_delta for r in closed]
    if normalize:vals=[snap_net(v) for v in vals]
    gain=sum(v for v in vals if v>0);loss=sum(v for v in vals if v<0)
    segment_cash=collections.defaultdict(float);segment_peak=collections.defaultdict(float);dds=collections.defaultdict(float)
    for r,pnl in zip(closed,vals):
        k=r['segment'];segment_cash[k]+=pnl;segment_peak[k]=max(segment_peak[k],segment_cash[k]);dds[k]=max(dds[k],segment_peak[k]-segment_cash[k])
    unresolved=sum(r['pnl'] is None for r in rows)
    net=gain+loss;dd=max(dds.values(),default=0.);pf=gain/-loss if loss<0 else None
    return {'entries':len(rows),'closed':len(closed),'unresolved':unresolved,'winning_closed':sum(v>0 for v in vals),'losing_closed':sum(v<0 for v in vals),'breakeven_closed':sum(v==0 for v in vals),'known_partial_net_usd':rounded(net),'known_partial_net_cents_usd':round(net,2),'closed_pf':rounded(pf),'closed_pf_four_decimals':round(pf,4) if pf is not None else None,'closed_expectancy_usd':rounded(net/len(vals)) if vals else None,'max_independent_segment_closed_dd_usd':rounded(dd),'max_independent_segment_closed_dd_cents_usd':round(dd,2),'full_year_net':None,'unknown_pnl_bound':None,'metric_version':'v2_zero_residual_normalized' if normalize else 'legacy_v1'}

def reconstruct(m,candles):
    segments=m.split_segments(candles);traces={f:[] for f in m.FAMILIES};summaries={f:collections.Counter() for f in m.FAMILIES}
    distribution={f:collections.defaultdict(lambda:collections.Counter()) for f in m.FAMILIES}
    funnel=collections.Counter();prefix_checks=0;atr_checks=0
    for si,seg in enumerate(segments):
        sig,atrs=m.signals(seg);n=len(seg)
        tr=[max(b.h-b.l,abs(b.h-seg[i-1].c),abs(b.l-seg[i-1].c)) if i else b.h-b.l for i,b in enumerate(seg)]
        for cut in sorted({x for x in (61,(60+n)//2,n-1) if 60<x<n}):
            ps,pa=m.signals(seg[:cut])
            assert all(ps[f]==sig[f][:cut] for f in m.FAMILIES)
            assert pa==atrs[:cut];prefix_checks+=1
        for i in range(60,n):
            assert math.isclose(atrs[i],statistics.fmean(tr[i-14:i]),rel_tol=1e-12,abs_tol=1e-12);atr_checks+=1
            funnel['post_warmup_positions']+=1
            if atrs[i]<=0:continue
            funnel['positive_atr']+=1
            shorter=statistics.fmean(tr[i-10:i]);longer=statistics.fmean(tr[i-40:i]);c=seg[i]
            if not(longer>0 and shorter/longer<.7):continue
            funnel['compression_gate']+=1
            if not(c.h-c.l>1.6*longer):continue
            funnel['compression_and_expansion']+=1
            if (c.c>max(b.h for b in seg[i-10:i]) and c.c>c.o) or (c.c<min(b.l for b in seg[i-10:i]) and c.c<c.o):funnel['directional_breakout_signal']+=1
        for family in m.FAMILIES:
            s=summaries[family];s['segments_total']+=1
            if n<=60:s['segments_too_short_for_signal']+=1
            raw_idxs={i for i,d in enumerate(sig[family]) if d}
            s['raw_signals']+=len(raw_idxs)
            if raw_idxs:s['segments_with_raw_signal']+=1
            elif n>60:s['eligible_segments_without_raw_signal']+=1
            else:s['short_segments_without_raw_signal']+=1
            qsignal=collections.Counter(quarter(seg[i].t) for i in raw_idxs)
            for q,v in qsignal.items():distribution[family][q]['raw_signals']+=v
            accepted=[];i=60
            while i<n:
                d=sig[family][i]
                if not d:i+=1;continue
                trade,status=m.one_trade(seg,i,d,atrs[i])
                if status in ('RISK_VETO','INVALID_ATR','MISSED_ENTRY'):
                    s[status]+=1;distribution[family][quarter(seg[i].t)][status]+=1;i+=1;continue
                ei=i+1;available=min(m.HORIZON_BARS,n-ei)
                row={'family':family,'segment':si,'signal_index':i,'entry_index':ei,'signal_time':seg[i].t,'entry_time':seg[ei].t,'direction':d,'atr':atrs[i],'stop_distance':m.STOP_ATR_MULTIPLE*atrs[i],'entry_bid':seg[ei].o,'pnl':None,'exit_time':None,'exit_index':None,'reason':None,'observed_bars':available,'observed_end':seg[ei+available-1].t+900,'raw_day_boundary_crossed_observed':seg[ei].t//86400!=seg[ei+available-1].t//86400,'raw_day_boundary_crossed_expected_horizon':seg[ei].t//86400!=(seg[ei].t+7*900)//86400}
                s['accepted_entries']+=1;distribution[family][quarter(row['entry_time'])]['entries']+=1;accepted.append(row)
                if status=='UNRESOLVED_NEXT_GAP_OR_END':
                    row['reason']='SAMPLE_END_BEFORE_HORIZON' if si==len(segments)-1 else 'HISTORY_GAP_BEFORE_HORIZON'
                    s['unresolved']+=1;distribution[family][quarter(row['entry_time'])]['unresolved']+=1
                    s['suppressed_after_unresolved_break']+=sum(k>i for k in raw_idxs)
                    break
                assert status=='RESOLVED'
                pnl,t,reason=trade;xi=(t-seg[0].t)//900
                row.update(pnl=pnl,exit_time=t,exit_index=xi,reason=reason,observed_end=t+900)
                s['closed']+=1;distribution[family][quarter(row['entry_time'])]['closed_by_entry_quarter']+=1
                distribution[family][quarter(t)]['closed_by_exit_quarter']+=1
                distribution[family][quarter(t)]['known_closed_net_by_exit_quarter']+=pnl
                s['suppressed_while_position_open']+=sum(i<k<xi for k in raw_idxs)
                s['suppressed_on_exit_bar']+=int(xi in raw_idxs and xi>i)
                i=max(i+1,xi+1)
            if accepted:s['segments_with_accepted_entry']+=1
            if any(r['pnl'] is not None for r in accepted):s['segments_with_closed']+=1
            if any(r['pnl'] is None for r in accepted):s['segments_with_unknown']+=1
            if accepted and all(r['pnl'] is not None for r in accepted):s['segments_with_entries_all_resolved']+=1
            traces[family].extend(accepted)
    for f,s in summaries.items():
        assert s['raw_signals']==s['accepted_entries']+s['RISK_VETO']+s['INVALID_ATR']+s['MISSED_ENTRY']+s['suppressed_after_unresolved_break']+s['suppressed_while_position_open']+s['suppressed_on_exit_bar'],(f,s)
    return segments,traces,summaries,distribution,dict(funnel),{'prefix_future_invariance_checks':prefix_checks,'all_post_warmup_previous14_ATR_checks':atr_checks}

def unknown_summary(rows):
    unknown=[r for r in rows if r['pnl'] is None]
    return {'entries_total':len(rows),'closed':len(rows)-len(unknown),'unknown':len(unknown),'closed_fraction':rounded((len(rows)-len(unknown))/len(rows)) if rows else None,'primary_causes':dict(collections.Counter(r['reason'] for r in unknown)),'observed_bars_before_cut_histogram':dict(sorted(collections.Counter(str(r['observed_bars']) for r in unknown).items())),'raw_day_crossed_observed':sum(r['raw_day_boundary_crossed_observed'] for r in unknown),'raw_day_crossed_expected_horizon':sum(r['raw_day_boundary_crossed_expected_horizon'] for r in unknown),'server_rollover_semantics_verified':False,'short_unknowns_with_ask_trigger_semantics_unverified':sum(r['direction']==-1 for r in unknown),'no_TP_SL_same_bar_ambiguity_in_reference_model':True,'unknown_imputed':False}

def dependency(traces):
    allrows=[r for rows in traces.values() for r in rows]
    same=collections.Counter(r['entry_time'] for r in allrows)
    overlap=0
    for i,a in enumerate(allrows):
        for b in allrows[i+1:]:
            if a['family']!=b['family'] and max(a['entry_time'],b['entry_time'])<min(a['observed_end'],b['observed_end']):overlap+=1
    return {'method_entries_are_not_unique_portfolio_positions':True,'entry_timestamps_shared_by_multiple_families':sum(v>1 for v in same.values()),'cross_family_observed_exposure_overlap_pairs':overlap,'unresolved_exposure_after_observed_cut_not_measurable':True,'raw_times_or_private_identifiers_published':False}

def run(args):
    policy_path=Path(args.policy);policy=json.loads(policy_path.read_text(encoding='utf-8-sig'))
    assert digest(policy_path)==POLICY_SHA,'Predeclared policy changed'
    assert digest(Path(__file__).with_name('NUMERIC_AUDIT_ADDENDUM.json'))==NUMERIC_ADDENDUM_SHA,'Numeric addendum changed'
    assert digest(args.reference)==policy['locked_program_sha256']
    assert digest(args.first_result)==policy['locked_first_result_sha256']
    private=Path(args.private_dir);tracepath=private/'reference-entry-trace.json';dest=Path(args.out)
    protected=[args.csv,args.reference,args.first_result,args.policy,Path(__file__).with_name('NUMERIC_AUDIT_ADDENDUM.json')]
    reject_aliases(protected,[tracepath,dest])
    m=load_reference(args.reference);candles,sha=m.load_csv(Path(args.csv));assert sha==policy['data_sha256']
    before={'data':digest(args.csv),'reference':digest(args.reference),'first_result':digest(args.first_result)}
    first=json.loads(Path(args.first_result).read_text(encoding='utf-8'))
    segments,traces,summaries,distribution,funnel,causal=reconstruct(m,candles)
    scenarios=policy['cost_scenarios'];units=m.CONTRACT_OZ_PER_LOT*m.LOT
    base_cost=friction_usd(scenarios[0],units,m.LOT);out={}
    firstmap={r['family']:r for r in first['methods']}
    for family,rows in traces.items():
        v=metrics(rows);old=firstmap[family]
        assert (v['entries'],v['closed'],v['unresolved'])==(old['observed_entries'],old['closed'],old['unresolved'])
        assert v['known_partial_net_cents_usd']==old['known_partial_net_usd']
        assert v['closed_pf_four_decimals']==old['known_partial_profit_factor']
        assert v['max_independent_segment_closed_dd_cents_usd']==old['max_independent_segment_closed_dd_usd']
        common=[r for r in rows if all(r['stop_distance']*units+friction_usd(c,units,m.LOT)<=m.RISK_BUDGET_USD for c in scenarios)]
        scenario_results=[]
        for cost in scenarios:
            total=friction_usd(cost,units,m.LOT);delta=total-base_cost;inadmissible=[r for r in rows if r['stop_distance']*units+total>m.RISK_BUDGET_USD]
            with costs(m,cost):
                for r in rows:
                    trade,status=m.one_trade(segments[r['segment']],r['signal_index'],r['direction'],r['atr'])
                    if r in inadmissible:assert status=='RISK_VETO';continue
                    if r['pnl'] is None:assert status=='UNRESOLVED_NEXT_GAP_OR_END';continue
                    assert status=='RESOLVED' and trade[1]==r['exit_time'] and trade[2]==r['reason']
                    assert math.isclose(trade[0],r['pnl']-delta,rel_tol=1e-10,abs_tol=1e-9)
            scenario_results.append({'cost':cost,'assumed_roundtrip_friction_usd':rounded(total),'full_frozen_entry_mathematical_overlay':metrics(rows,delta),'full_frozen_v2_numeric_metrics_same_entries_and_fills':metrics(rows,delta,True),'risk_inadmissible_frozen_entries':len(inadmissible),'risk_inadmissible_closed':sum(r['pnl'] is not None for r in inadmissible),'risk_inadmissible_unknown':sum(r['pnl'] is None for r in inadmissible),'common_risk_admissible_fixed_entry_cohort':metrics(common,delta),'common_risk_admissible_v2_numeric_metrics':metrics(common,delta,True),'actual_closed_residuals_in_zero_tolerance':sum(r['pnl'] is not None and 0<abs(r['pnl']-delta)<=1e-9 for r in rows),'dropped_entries_not_replaced_with_later_signals':True})
        unknown=sum(r['pnl'] is None for r in rows);closed=sum(r['pnl'] is not None for r in rows);net=sum(r['pnl'] for r in rows if r['pnl'] is not None)
        prefix=[]
        for r in rows:
            prefix.append(r)
            if r['pnl'] is None:break
        gate='STOP_RESEARCH_CURRENT_VERSION' if all(c['common_risk_admissible_fixed_entry_cohort']['known_partial_net_usd']<0 for c in scenario_results) else 'INSUFFICIENT_EVIDENCE'
        fullsegrows=[r for r in rows if not any(x['pnl'] is None and x['segment']==r['segment'] for x in rows)]
        out[family]={'reference_matches_first_aggregate':True,'signal_segment_counts':dict(summaries[family]),'unknown_audit':unknown_summary(rows),'quarter_distribution':[dict(period_raw=q,**{k:rounded(v) if isinstance(v,float) else v for k,v in values.items()}) for q,values in sorted(distribution[family].items())],'cost_sensitivity':scenario_results,'survivor_selection':{'closed_share':rounded(closed/len(rows)) if rows else None,'unknown_share':rounded(unknown/len(rows)) if rows else None,'mean_net_usd_per_unknown_needed_for_full_net_zero':rounded(-net/unknown) if unknown else None,'not_a_bound_or_imputed_outcome':True},'closed_only_total_roundtrip_friction_break_even_usd':rounded((net+base_cost*closed)/closed) if closed else None,'additional_friction_to_zero_closed_net_usd':rounded(net/closed) if closed else None,'first_unknown_stopped_prefix':metrics(prefix),'later_entries_blocked_in_prefix':len(rows)-len(prefix),'all_positions_resolved_segment_subset':metrics(fullsegrows),'decision':gate,'complete_sample_gate_passed':closed>=100 and unknown==0,'financial_approval':False}
    write_json_atomic(tracepath,traces,protected+[dest])
    aggregate={'audit_policy_sha256':POLICY_SHA,'numeric_addendum_sha256':NUMERIC_ADDENDUM_SHA,'numeric_addendum_commit':'a5fae84239980f3e8a671628b5b65e537e6e8a22','policy_preregistration_commit':args.policy_commit,'immutable_first_run_commit':'de94202d2da89e07c280a94108f73208c4fb2001','source_program_sha256':digest(args.reference),'source_first_result_sha256':digest(args.first_result),'data_sha256':sha,'rows':len(candles),'segments':len(segments),'gaps':len(segments)-1,'signal_or_ATR_parameters_changed':False,'scenario_entry_sets_frozen_before_comparing_cost_outputs':True,'original_program_or_first_result_modified':False,'reference_trace_sha256':digest(tracepath),'causality_checks':causal,'compression_funnel':funnel,'methods':out,'dependency':dependency(traces),'full_year_net':None,'historical_swap':None,'historical_execution_verified':False,'fresh_holdout':False,'raw_data_or_trade_times_published':False,'overall_decision':'NO_STRATEGY_APPROVED; NO_PARAMETER_SEARCH; INDEPENDENT_PERIOD_PLAN_REQUIRES_NEW_PERMISSION'}
    write_json_atomic(dest,aggregate,protected+[tracepath])
    assert before=={'data':digest(args.csv),'reference':digest(args.reference),'first_result':digest(args.first_result)}
    print(json.dumps({'output':dest.name,'reference_matched':True,'rows':len(candles),'segments':len(segments),'causality_checks':causal,'compression_funnel':funnel,'decisions':{f:v['decision'] for f,v in out.items()}},indent=2))
    return aggregate

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('csv','reference','first-result','policy','private-dir','out','policy-commit'):p.add_argument('--'+key,required=True)
    run(p.parse_args())
