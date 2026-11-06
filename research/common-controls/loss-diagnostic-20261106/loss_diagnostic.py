"""Aggregate existing FF artifacts only. No strategy/engine/network imports.
Private fills remain in memory. Output contains counts, scenario PnL and hashes.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from datetime import datetime,timedelta
from decimal import Decimal as D
from pathlib import Path

ZERO=D(0)
UM='UNMEASURABLE'
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def label(t):return datetime(1970,1,1)+timedelta(seconds=int(t))
def amount(v):
    x=D(str(v))
    if not x.is_finite():raise ValueError('NONFINITE')
    return x
def total(v):return sum(v,ZERO)
def ratio(a,b):return str(D(a)/D(b)) if b else UM
def distribution(values):
    v=sorted(values)
    if not v:return {'count':0,'min':UM,'q25':UM,'median':UM,'q75':UM,'max':UM,'mean':UM}
    def q(n,d):
        pos=D(len(v)-1)*D(n)/D(d);i=int(pos);f=pos-i
        return str(v[i]+(v[min(i+1,len(v)-1)]-v[i])*f)
    return dict(count=len(v),min=str(v[0]),q25=q(1,4),median=q(1,2),q75=q(3,4),max=str(v[-1]),mean=str(total(v)/len(v)))
def dd(values):
    equity=peak=drawdown=ZERO
    for v in values:
        equity+=v;peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
    return drawdown
def group_stats(trades):
    vals=[amount(t['net_scenario_usd']) for t in trades if t['net_scenario_usd'] is not None]
    wins=[v for v in vals if v>0];losses=[v for v in vals if v<0]
    return dict(positions=len(trades),resolved=len(vals),unresolved=len(trades)-len(vals),
                known_partial_net=str(total(vals)),full_net=None if len(vals)!=len(trades) else str(total(vals)),
                wins=len(wins),losses=len(losses),breakeven=len(vals)-len(wins)-len(losses),
                win_rate_resolved=ratio(len(wins),len(vals)),
                win_loss_count_ratio=ratio(len(wins),len(losses)),
                positive_net_sum=str(total(wins)),negative_net_sum=str(total(losses)),
                mean_win=str(total(wins)/len(wins)) if wins else UM,
                mean_loss_magnitude=str(-total(losses)/len(losses)) if losses else UM,
                profit_factor=ratio(total(wins),-total(losses)),
                closed_pnl_distribution=distribution(vals),
                reasons=dict(collections.Counter(t['reason'] for t in trades)),
                resolved_exit_reasons=dict(collections.Counter(t['reason'] for t in trades if t['net_scenario_usd'] is not None)),
                unresolved_reasons=dict(collections.Counter(t['reason'] for t in trades if t['net_scenario_usd'] is None)))
def decision(metrics):
    if len(metrics)!=2:return 'RESEARCH_ONLY'
    measured=all(m['profit_factor']!=UM for m in metrics)
    if measured and all(amount(m['known_partial_net'])<0 and amount(m['fully_resolved_segment_net'])<0 and amount(m['profit_factor'])<1 for m in metrics):
        return 'STOP'
    if measured and all(amount(m['known_partial_net'])>0 and amount(m['fully_resolved_segment_net'])>0 and amount(m['profit_factor'])>1 and m['unresolved']==0 for m in metrics):
        return 'CANDIDATE_FOR_FRESH_TEST'
    return 'RESEARCH_ONLY'

def diagnose(source,trace_dir,protocol_path,out):
    protocol=json.loads(protocol_path.read_text(encoding='utf-8'))
    summary=json.loads((source/'ff-session-replay-summary.json').read_text())
    table=json.loads((source/'ff-session-results-table.json').read_text())
    policy=json.loads((source/'ff-session-replay-policy.json').read_text())
    selection=json.loads((source/'ff-session-replay-selection.json').read_text())
    bysegment=json.loads((source/'ff-session-replay-by-segment.json').read_text())
    trace_path=trace_dir/(summary['identity']+'.json')
    envelope=json.loads(trace_path.read_text())
    full=envelope['result']
    if envelope['identity']!=summary['identity'] or digest(full)!=envelope['result_sha256']:raise ValueError('TRACE_HASH')
    legacy_table_byte_link=sha(source/'ff-session-replay-summary.json')==table['original_summary_sha256']
    # Preserve stale legacy hashes; reconcile actual content independently below.
    if digest(policy)!=summary['policy_sha256'] or digest(selection)!=summary['selection_sha256']:raise ValueError('POLICY_SELECTION_HASH')
    if policy['mode']!='FF' or policy['fit'] or policy['fresh_holdout']:raise ValueError('UNEXPECTED_POLICY')
    if digest(dict(policy=policy,selection=selection,code=summary['code_hashes'],manifest=summary['source_manifest_sha256']))!=summary['identity']:
        raise ValueError('RUN_IDENTITY')
    # Bind the recorded run's code, without importing or running its engine.
    engine_files={}
    for name,expected in summary['code_hashes'].items():
        if '/' in name:continue
        engine_files[name]=sha(source/name)==expected
    if not all(engine_files.values()):raise ValueError('RECORDED_CODE_CHANGED')
    index={(r['candidate'],r['cost'],r['segment']):r for r in full}
    if len(index)!=len(full):raise ValueError('DUPLICATE_RUN_CELL')
    ti={(r['candidate'],r['cost'],r['segment']):r for r in (dict(zip(table['columns'],row)) for row in table['rows'])}
    bi={(r['candidate'],r['cost'],r['segment']):r for r in bysegment}
    if index.keys()!=ti.keys() or index.keys()!=bi.keys():raise ValueError('CELL_INVENTORY')
    total_resolved=total_unknown=eligible=skipped=0
    for key,row in index.items():
        r=row['result'];t=ti[key];b=bi[key]
        if r is None:
            if t['status']!='INSUFFICIENT_WARMUP':raise ValueError('SKIP_STATUS')
            skipped+=1;continue
        eligible+=1
        if digest(r)!=b['trace_sha256']:raise ValueError('SEGMENT_TRACE_HASH')
        for f,original in [('positions','positions'),('resolved','resolved'),('unresolved','unresolved'),('signals',None)]:
            expected=r['signal_counts']['signals'] if original is None else r[original]
            if t[f]!=expected or b[f]!=expected:raise ValueError('CELL_COUNT')
        vals=[]
        for tr in r['rows']:
            if tr['net_scenario_usd'] is not None:
                if tr['gross_scenario_usd'] is None or tr['exit'] is None:raise ValueError('RESOLVED_FIELDS')
                # Independent cash identity using recorded fills only.
                direction=1 if tr['side']=='buy' else -1
                gross=D(direction)*(amount(tr['exit'])-amount(tr['entry']))*100*amount(tr['lots'])
                fee=amount(policy['costs'][row['cost']]['commission_roundtrip_per_lot'])*amount(tr['lots'])
                if gross!=amount(tr['gross_scenario_usd']) or gross-fee!=amount(tr['net_scenario_usd']):raise ValueError('CASH_IDENTITY')
                vals.append(amount(tr['net_scenario_usd']));total_resolved+=1
            else:
                if tr['gross_scenario_usd'] is not None or tr['exit'] is not None:raise ValueError('UNKNOWN_INVENTED_EXIT')
                total_unknown+=1
        if len(vals)!=r['resolved'] or len(r['rows'])-len(vals)!=r['unresolved']:raise ValueError('ROW_COUNTS')
        expected_full=None if r['unresolved'] else str(total(vals))
        if (t['net_complete'] is None)!=(expected_full is None):raise ValueError('NET_NULL')
        if expected_full is not None and amount(t['net_complete'])!=amount(expected_full):raise ValueError('NET_COMPLETE')
        if amount(t['known_partial'])!=total(vals) or amount(r['known_partial_net_usd'])!=total(vals):raise ValueError('NET_PARTIAL')
        if t['wins']!=sum(v>0 for v in vals) or t['losses']!=sum(v<0 for v in vals) or t['no_signal']!=(r['positions']==0):raise ValueError('TABLE_DISTRIBUTION')
        if not r['unresolved'] and (amount(t['closed_dd'])!=dd(vals) or amount(r['scenario_max_drawdown_usd'])!=dd(vals)):raise ValueError('DD_RECONCILE')
    selections={r['id']:r for r in selection}
    gaps=json.loads((source/'gap-classifications-v4.json').read_text())
    unusual=[g for g in gaps if g['pattern']=='OTHER']
    neighbor_evidence=json.loads((source/'all-gap-neighbor-evidence-v1.json').read_text())
    holiday_ids={g['gap_id'] for g in neighbor_evidence['rows'] if g['slot_parent_candidate']=='HOLIDAY_EARLY_CLOSE_CANDIDATE'}
    holidays=[g for g in gaps if g['id'] in holiday_ids]
    all_metrics=[];comparison=[]
    for candidate in sorted({r['candidate'] for r in full}):
        for cost in policy['costs']:
            runs=[r for r in full if r['candidate']==candidate and r['cost']==cost]
            active=[r for r in runs if r['result'] is not None]
            trades=[tr for r in active for tr in r['result']['rows']]
            metrics=dict(candidate=candidate,cost=cost,**group_stats(trades))
            stable=[r for r in active if r['result']['unresolved']==0]
            uncertain=[r for r in active if r['result']['unresolved']>0]
            vals_by_run=lambda rows:[amount(tr['net_scenario_usd']) for r in rows for tr in r['result']['rows'] if tr['net_scenario_usd'] is not None]
            metrics.update(eligible_segments=len(active),skipped_segments=len(runs)-len(active),
                zero_position_segments=sum(not r['result']['rows'] for r in active),
                fully_resolved_segments=len(stable),unresolved_segments=len(uncertain),
                fully_resolved_segment_net=str(total(vals_by_run(stable))),
                resolved_prefix_in_unresolved_segments_net=str(total(vals_by_run(uncertain))),
                fully_resolved_segment_closed_positions=len(vals_by_run(stable)),
                unresolved_segment_closed_positions=len(vals_by_run(uncertain)),
                unresolved_share=ratio(metrics['unresolved'],metrics['positions']),
                worst_closed_dd_fully_resolved_segment=str(max((dd([amount(tr['net_scenario_usd']) for tr in r['result']['rows']]) for r in stable),default=ZERO)),
                worst_observed_closed_prefix_dd=str(max((dd([amount(tr['net_scenario_usd']) for tr in r['result']['rows'] if tr['net_scenario_usd'] is not None]) for r in active),default=ZERO)),
                continuous_annual_net=None,continuous_annual_dd=UM,
                unresolved_pnl_bound='NOT_BOUNDED' if metrics['unresolved'] else 'NOT_APPLICABLE',
                spread_cash_component=UM,slippage_cash_component=UM,actual_historical_cost=UM,
                recorded_gross_embeds_spread_slippage=str(total(amount(t['gross_scenario_usd']) for t in trades if t['gross_scenario_usd'] is not None)),
                commission_from_trace_difference=str(total(amount(t['gross_scenario_usd'])-amount(t['net_scenario_usd']) for t in trades if t['net_scenario_usd'] is not None)),
                cost_assumptions=policy['costs'][cost],
                missing_signal_conditions=['ATR','ADX','volatility_regime','signal_strength','historical_session_certification'])
            original=next(r for r in summary['rows'] if r['candidate']==candidate and r['cost']==cost and r['month_raw']=='ALL')
            for new,old in [('positions','positions'),('resolved','resolved'),('unresolved','unresolved'),('wins','wins'),('losses','losses'),
                            ('zero_position_segments','no_signal_segments'),('fully_resolved_segments','fully_resolved_segments')]:
                if metrics[new]!=original[old]:raise ValueError('SUMMARY_COUNTS')
            for new,old in [('known_partial_net','sum_known_partial_net'),('fully_resolved_segment_net','sum_net_fully_resolved_segments')]:
                if amount(metrics[new])!=amount(original[old]):raise ValueError('SUMMARY_NET')
            cohorts=collections.defaultdict(list)
            unresolved_profiles=collections.defaultdict(list)
            for r in active:
                s=selections[r['segment']]
                for tr in r['result']['rows']:
                    dt=label(tr['entry_time'])
                    prev_exists=s['id']>1;next_exists=s['id']<len(selection)
                    near_prev=prev_exists and tr['entry_time']-s['first_raw']<=protocol['proximity']['near_gap_minutes']*60
                    near_next=next_exists and s['last_raw']+900-tr['entry_time']<=protocol['proximity']['near_gap_minutes']*60
                    near_other=any(min(abs(tr['entry_time']-g['start_raw_epoch']),abs(tr['entry_time']-g['end_raw_epoch_exclusive']))<=protocol['proximity']['holiday_candidate_neighborhood_hours']*3600 for g in unusual)
                    near_holiday=any(min(abs(tr['entry_time']-g['start_raw_epoch']),abs(tr['entry_time']-g['end_raw_epoch_exclusive']))<=protocol['proximity']['holiday_candidate_neighborhood_hours']*3600 for g in holidays)
                    signal=tr.get('signal_candidate') or {}
                    for dim,key in [('month',dt.strftime('%Y-%m')),('day',dt.strftime('%Y-%m-%d')),
                                    ('weekday',dt.strftime('%A')),('hour',str(dt.hour)),('side',tr['side']),
                                    ('near_next_gap_60m',str(near_next)),('near_previous_gap_60m',str(near_prev)),
                                    ('near_unusual_gap_24h_candidate_only',str(near_other)),
                                    ('near_holiday_candidate_gap_24h',str(near_holiday)),
                                    ('family',str(signal.get('family',UM))),('lookback',str(signal.get('lookback',UM)))]:
                        cohorts[(dim,key)].append(tr)
                    if tr['net_scenario_usd'] is None:
                        unresolved_profiles['observed_minutes'].append(D(tr['exit_time']-tr['entry_time'])/60)
                        unresolved_profiles['entry_minutes_until_segment_observed_end'].append(D(s['last_raw']+900-tr['entry_time'])/60)
                        unresolved_profiles['initial_risk_scenario_usd'].append(abs(amount(tr['entry'])-amount(tr['initial_stop']))*100*amount(tr['lots']))
            metrics['unresolved_profiles']={k:distribution(v) for k,v in unresolved_profiles.items()}
            metrics['initial_risk_from_recorded_fills_usd']=distribution([abs(amount(t['entry'])-amount(t['initial_stop']))*100*amount(t['lots']) for t in trades])
            metrics['resolved_observed_holding_minutes']=distribution([D(t['exit_time']-t['entry_time'])/60 for t in trades if t['net_scenario_usd'] is not None])
            for t in trades:
                cohorts[('exit_reason',t['reason'])].append(t)
                cohorts[('recorded_price_exit_reason',t['price_exit_reason'])].append(t)
                cohorts[('stop_multiple',str((t.get('signal_candidate') or {}).get('stop_multiple',UM)))].append(t)
            metrics['unresolved_recorded_price_exit_reasons']=dict(collections.Counter(t['price_exit_reason'] for t in trades if t['net_scenario_usd'] is None))
            metrics['grouped_descriptive']=[dict(dimension=d,label=k,**group_stats(ts)) for (d,k),ts in sorted(cohorts.items())]
            metrics['monthly_positive_known_partial']=sum(amount(g['known_partial_net'])>0 for g in metrics['grouped_descriptive'] if g['dimension']=='month')
            metrics['monthly_negative_known_partial']=sum(amount(g['known_partial_net'])<0 for g in metrics['grouped_descriptive'] if g['dimension']=='month')
            metrics['entry_count']=metrics['positions']
            metrics['resolved_exit_count']=metrics['resolved']
            metrics['signals_callback_count']=sum(r['result']['signal_counts']['signals'] for r in active)
            all_metrics.append(metrics)
        # Match observations by recorded entry, not by ordinal trade number.
        streams={}
        for cost in policy['costs']:
            streams[cost]={(r['segment'],t['side'],t['entry_time']):t for r in full if r['candidate']==candidate and r['cost']==cost and r['result'] is not None for t in r['result']['rows']}
        a,b=streams['base'],streams['envelope'];both=a.keys()&b.keys()
        common_closed=[k for k in both if a[k]['net_scenario_usd'] is not None and b[k]['net_scenario_usd'] is not None]
        transitions=collections.Counter(('RESOLVED' if a[k]['net_scenario_usd'] is not None else 'UNRESOLVED')+'->'+('RESOLVED' if b[k]['net_scenario_usd'] is not None else 'UNRESOLVED') for k in both)
        comparison.append(dict(candidate=candidate,entry_matched=len(both),base_only=len(a.keys()-b.keys()),envelope_only=len(b.keys()-a.keys()),
            status_transitions=dict(transitions),both_resolved=len(common_closed),
            paired_net_delta_envelope_minus_base=str(total(amount(b[k]['net_scenario_usd'])-amount(a[k]['net_scenario_usd']) for k in common_closed)),
            paired_exit_time_changed=sum(a[k]['exit_time']!=b[k]['exit_time'] for k in both),
            paired_price_exit_reason_changed=sum(a[k]['price_exit_reason']!=b[k]['price_exit_reason'] for k in both),
            interpretation='SCENARIO_SENSITIVITY_NOT_PURE_COST_CAUSAL_EFFECT'))
    decisions=[dict(candidate=c,decision=decision([m for m in all_metrics if m['candidate']==c]),
                    market_approved=False,fresh_holdout='NO_FRESH_HOLDOUT') for c in sorted({m['candidate'] for m in all_metrics})]
    evidence=dict(schema=1,source_identity=summary['identity'],protocol_sha256=sha(protocol_path),
        legacy_table_original_summary_byte_hash_verified=legacy_table_byte_link,
        legacy_table_original_summary_claimed_hash=table['original_summary_sha256'],
        table_numerically_reconciled_with_trace=True,
        hashes={p.name:sha(p) for p in [source/'ff-session-replay-summary.json',source/'ff-session-results-table.json',
            source/'ff-session-replay-by-segment.json',source/'ff-session-replay-policy.json',source/'ff-session-replay-selection.json',
            source/'gap-classifications-v4.json',source/'all-gap-neighbor-evidence-v1.json',trace_path]},
        trace_content_digest=envelope['result_sha256'],recorded_engine_code_hash_checks=engine_files,
        checked_resolved_cash_identities=total_resolved,checked_unresolved_no_invented_exit=total_unknown,
        eligible_cells=eligible,skipped_cells=skipped,annual_replay_executed=False,
        decisions=decisions,approved_methods=0,scope='EXPLORATORY_ACCOUNTING_ATTRIBUTION_NOT_MARKET_CAUSAL_IDENTIFICATION',
        metrics=all_metrics,cost_comparisons=comparison,
        warnings=['Two scenarios are not independent trades; never sum them as a larger sample.',
                  'UNKNOWN exit_time is observation endpoint, not execution.',
                  'Closed gross already includes spread/slippage; separate cash components not recorded.',
                  'Full-year equity/net/DD and unresolved bounds cannot be inferred from independent flat-reset segments.',
                  'Raw hour/day labels only; unusual gap neighborhoods are candidates, not official closure evidence.',
                  'No holdout fit or parameter change. M5 recovery closed at zero.'])
    out.mkdir(parents=True,exist_ok=True)
    p=out/'loss-diagnostic-results.json'
    p.write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding='utf-8')
    compact=dict(evidence)
    compact['metrics']=[{k:v for k,v in m.items() if k!='grouped_descriptive'} for m in all_metrics]
    (out/'loss-diagnostic-summary.json').write_text(json.dumps(compact,indent=2,ensure_ascii=False),encoding='utf-8')
    columns=['candidate','cost','dimension','raw_label','positions','resolved','unresolved','known_partial_net','wins','losses']
    grouped=[]
    daily=[]
    for m in all_metrics:
        for g in m['grouped_descriptive']:
            row=[m['candidate'],m['cost'],g['dimension'],g['label'],g['positions'],g['resolved'],g['unresolved'],g['known_partial_net'],g['wins'],g['losses']]
            (daily if g['dimension']=='day' else grouped).append(row)
    for name,rows in [('raw-time-cohorts.json',grouped),('daily-cohorts.json',daily)]:
        (out/name).write_text(json.dumps(dict(columns=columns,rows=rows),separators=(',',':'),ensure_ascii=False),encoding='utf-8')
    receipt=dict(output_sha256=sha(p),code_sha256=sha(Path(__file__)),protocol_sha256=sha(protocol_path),
                 output_artifacts={name:sha(out/name) for name in ('loss-diagnostic-summary.json','raw-time-cohorts.json','daily-cohorts.json')},
                 input_hashes=evidence['hashes'],checks=dict(resolved=total_resolved,unresolved=total_unknown,all_passed=True),
                 legacy_table_byte_link_verified=legacy_table_byte_link,
                 annual_replay_executed=False,orders=0,mt5_execution=False)
    (out/'diagnostic-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('metrics','cost_comparisons','hashes','recorded_engine_code_hash_checks')},indent=2))
    print(json.dumps([{k:v for k,v in m.items() if k not in ('grouped_descriptive','unresolved_profiles')} for m in all_metrics],indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('source','trace-dir','protocol','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();diagnose(a.source,a.trace_dir,a.protocol,a.out)
