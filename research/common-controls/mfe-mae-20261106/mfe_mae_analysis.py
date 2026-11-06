"""Existing-entry OHLC excursion diagnostics only. Standard library, no engine.
No signal search, alternative-strategy simulation, terminal or network calls.
"""
import argparse,collections,csv,hashlib,json
from decimal import Decimal as D
from datetime import datetime,timedelta
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def dt(t):return datetime(1970,1,1)+timedelta(seconds=t)
def quantiles(xs):
    a=sorted(xs)
    if not a:return dict(n=0,q25=None,median=None,q75=None,mean=None,min=None,max=None)
    def q(n,d):
        p=D(len(a)-1)*n/d;i=int(p);f=p-i
        return str(a[i]+(a[min(i+1,len(a)-1)]-a[i])*f)
    return dict(n=len(a),q25=q(1,4),median=q(1,2),q75=q(3,4),mean=str(sum(a,D(0))/len(a)),min=str(a[0]),max=str(a[-1]))

def net_at(quote,tr,cost):
    direction=D(1) if tr['side']=='buy' else D(-1)
    side_quote=quote+(D(cost['spread']) if tr['side']=='sell' else D(0))
    exit_fill=side_quote-direction*D(cost['slippage'])
    return direction*(exit_fill-D(tr['entry']))*100*D(tr['lots'])-D(cost['commission_roundtrip_per_lot'])*D(tr['lots'])

def excursion(bars,tr,cost,known_net=None):
    # Both side-specific extremes; no claim about their within-bar order.
    vals=[net_at(b[k],tr,cost) for b in bars for k in ('low','high')]
    if known_net is not None:vals.append(D(known_net))
    return max([D(0)]+vals),max([D(0)]+[-v for v in vals])

def first_touch(bars,tr,cost):
    stop=D(tr['initial_stop']);target=D(tr['target'])
    for b in bars:
        shift=D(cost['spread']) if tr['side']=='sell' else D(0)
        o,h,l=(b[k]+shift for k in ('open','high','low'))
        hs=(o<=stop if tr['side']=='buy' else o>=stop)
        ht=(o>=target if tr['side']=='buy' else o<=target)
        if hs:return 'STOP_OPEN'
        if ht:return 'TARGET_OPEN'
        hs=(l<=stop if tr['side']=='buy' else h>=stop)
        ht=(h>=target if tr['side']=='buy' else l<=target)
        if hs and ht:return 'AMBIGUOUS'
        if hs:return 'STOP'
        if ht:return 'TARGET'
    return 'NO_TOUCH_IN_12'

def window(bars,start,n):
    seq=[bars.get(start+i*900) for i in range(n)]
    if any(b is None for b in seq):return None,'INCOMPLETE_OR_GAP'
    if start//86400!=(start+n*900)//86400:return None,'RAW_DAY_BOUNDARY'
    return seq,'ELIGIBLE'

def summarize(rows):
    out=dict(entries=len(rows),source_resolved=sum(r['source_resolved'] for r in rows),
        source_unresolved=sum(not r['source_resolved'] for r in rows),
        forward_eligibility=dict(collections.Counter(r['forward_status'] for r in rows)),
        source_reasons=dict(collections.Counter(r['source_reason'] for r in rows)))
    active=[r for r in rows if r['forward_status']=='ELIGIBLE']
    life=[r for r in rows if r['lifetime_status']=='BOUNDED_SCENARIO_EXCURSION']
    out['full12_first_touch']=dict(collections.Counter(r['first_touch'] for r in active))
    out['full12_unresolved_source_count']=sum(not r['source_resolved'] for r in active)
    for f in ('initial_risk_usd','nominal_target_R'):
        out[f]=quantiles([r[f] for r in rows])
    out['target_below_1R_count']=sum(r['nominal_target_R']<1 for r in rows)
    out['target_at_most_half_R_count']=sum(r['nominal_target_R']<=D('.5') for r in rows)
    for f in ('mfe12_usd','mae12_usd','mfe12_R','mae12_R'):
        out[f]=quantiles([r[f] for r in active])
    out['full12_mfe_at_least_1R']=sum(r['mfe12_R']>=1 for r in active)
    out['full12_mae_at_least_1R']=sum(r['mae12_R']>=1 for r in active)
    out['full12_both_excursions_ge_1R']=sum(r['mfe12_R']>=1 and r['mae12_R']>=1 for r in active)
    out['lifetime_bounds_count']=len(life)
    for f in ('life_mfe_lower_R','life_mfe_upper_R','life_mae_lower_R','life_mae_upper_R'):
        out[f]=quantiles([r[f] for r in life])
    out['lifetime_excluded']=dict(collections.Counter(r['lifetime_status'] for r in rows if r['lifetime_status']!='BOUNDED_SCENARIO_EXCURSION'))
    return out

def analyze(raw_dir,source,trace_dir,prior_dir,new_dir,protocol,out,private_out):
    config=json.loads(protocol.read_text())
    summary=json.loads((source/'ff-session-replay-summary.json').read_text())
    policy=json.loads((source/'ff-session-replay-policy.json').read_text())
    selection=json.loads((source/'ff-session-replay-selection.json').read_text())
    if digest(policy)!=summary['policy_sha256'] or digest(selection)!=summary['selection_sha256']:raise ValueError('POLICY_SELECTION')
    if digest(dict(policy=policy,selection=selection,code=summary['code_hashes'],manifest=summary['source_manifest_sha256']))!=summary['identity']:
        raise ValueError('SOURCE_RUN_IDENTITY')
    trace_path=trace_dir/(summary['identity']+'.json')
    envelope=json.loads(trace_path.read_text());runs=envelope['result']
    if digest(runs)!=envelope['result_sha256'] or envelope['identity']!=summary['identity']:raise ValueError('TRACE_IDENTITY')
    manifest=json.loads((raw_dir/'manifest.json').read_text())
    if sha(raw_dir/'manifest.json')!=summary['source_manifest_sha256']:raise ValueError('RAW_MANIFEST')
    bars={};verified=[]
    for item in manifest['chunks'].values():
        if item['kind']!='M15':continue
        for field in ('raw','csv'):
            if sha(raw_dir/item[field])!=item[field+'_sha256']:raise ValueError('RAW_CHUNK_HASH')
        p=raw_dir/item['csv'];verified.append(item['csv_sha256'])
        for row in csv.DictReader(p.open(encoding='utf-8-sig',newline='')):
            t=int(row['time']);b={k:D(row[k]) for k in ('open','high','low','close')}
            if any(not v.is_finite() or v<=0 for v in b.values()) or not b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']:raise ValueError('OHLC')
            if t%900 or int(row['tick_volume'])<=0 or int(row['spread'])<0:raise ValueError('BAR_VALIDITY')
            if t in bars and bars[t]!=b:raise ValueError('DUPLICATE_CONFLICT')
            bars[t]=b
    times=sorted(bars);parts=[];part=[]
    for t in times:
        if part and t-part[-1]!=900:parts.append(part);part=[]
        part.append(t)
    if part:parts.append(part)
    if len(parts)!=len(selection):raise ValueError('SEGMENTS')
    for p,s in zip(parts,selection):
        if (p[0],p[-1],len(p))!=(s['first_raw'],s['last_raw'],s['bars']):raise ValueError('SELECTION_BOUNDARY')
    newpath=new_dir/'M15.csv';newrows=list(csv.DictReader(newpath.open(encoding='utf-8-sig')))
    oldprior=json.loads((prior_dir/'receipt.json').read_text())
    oldprior_unique=set()
    for p in prior_dir.glob('M15-*.csv'):
        oldprior_unique.update(r['time'] for r in csv.DictReader(p.open(encoding='utf-8-sig')))
    monthly=collections.Counter(dt(t).strftime('%Y-%m') for t in times)
    calendar_slots=(times[-1]-times[0])//900+1
    inventory=dict(original_m15=len(bars),old_span_raw=[dt(times[0]).isoformat(),dt(times[-1]).isoformat()],
        monthly_bar_counts=dict(sorted(monthly.items())),calendar_slots_in_span=calendar_slots,
        absent_calendar_slots=calendar_slots-len(bars),gaps=len(parts)-1,contiguous_parts=len(parts),
        segment_bar_lengths=quantiles([D(len(p)) for p in parts]),verified_original_m15_chunk_pairs=len(verified),
        new_export_m15=len(newrows),new_export_csv_sha256=sha(newpath),new_export_mixed_into_trace=False,
        prior_year_unique_m15=len(oldprior_unique),prior_year_requests=oldprior['query_count'],
        prior_year_status='SPARSE_BOUNDARY_SAMPLES_NOT_FULL_PERIOD',
        price_side='BID_SUPPORTED_BY_CURRENT_CHART_MODE_AND_PRIOR_SAME_FEED_OHLC_CHECKS',
        historical_utc_dst='UNVERIFIED',historical_session_calendar='UNVERIFIED_NOT_INFERRED_FROM_GAPS',
        historical_bidask_cost_swap='INSUFFICIENT',study_eligibility='EXPLORATORY_IN_SAMPLE_ONLY',
        fresh_holdout='NO_FRESH_HOLDOUT',financial_approval=False)
    records=[];touch_mismatch=0
    reason_map={'STOP':'STOP','STOP_OPEN_GAP':'STOP','TARGET':'TARGET','TARGET_AT_OPEN_CAPPED':'TARGET',
                'MAX_HOLD_CLOSE_ASSUMED':'NO_TOUCH_IN_12','AMBIGUOUS_SL_TP':'AMBIGUOUS','UNRESOLVED_BOUNDARY':None}
    for run in runs:
        if run['result'] is None:continue
        for i,tr in enumerate(run['result']['rows']):
            if tr['stop_adjustments'] or tr['target'] is None:raise ValueError('NOT_FF_FIXED')
            cost=policy['costs'][run['cost']];entry=tr['entry_time']
            risk=abs(D(tr['entry'])-D(tr['initial_stop']))*100*D(tr['lots'])
            if risk<=0:raise ValueError('ZERO_RISK')
            rec=dict(candidate=run['candidate'],cost=run['cost'],segment=run['segment'],entry_index=i,
                entry_raw=dt(entry).isoformat(),month_raw=dt(entry).strftime('%Y-%m'),
                quarter_raw=f"{dt(entry).year}-Q{(dt(entry).month-1)//3+1}",
                source_resolved=tr['net_scenario_usd'] is not None,source_reason=tr['reason'],
                initial_risk_usd=risk,nominal_target_R=abs(D(tr['target'])-D(tr['entry']))*100*D(tr['lots'])/risk)
            seq,status=window(bars,entry,config['future_window_bars']);rec['forward_status']=status
            if seq is not None:
                mfe,mae=excursion(seq,tr,cost);touch=first_touch(seq,tr,cost)
                rec.update(mfe12_usd=mfe,mae12_usd=mae,mfe12_R=mfe/risk,mae12_R=mae/risk,first_touch=touch)
                normalized=touch.replace('_OPEN','')
                expected=reason_map[tr['price_exit_reason']]
                if normalized!=expected:touch_mismatch+=1
            rec['lifetime_status']='UNRESOLVED_NOT_EXACT_EXCURSION'
            if rec['source_resolved']:
                n=(tr['exit_time']-entry)//900
                life,lstat=window(bars,entry,n)
                if life is not None:
                    lower=excursion(life[:-1],tr,cost,tr['net_scenario_usd'])
                    upper=excursion(life,tr,cost,tr['net_scenario_usd'])
                    if any(a>b for a,b in zip(lower,upper)):raise ValueError('EXCURSION_BOUNDS')
                    rec.update(lifetime_status='BOUNDED_SCENARIO_EXCURSION',
                        life_mfe_lower_R=lower[0]/risk,life_mfe_upper_R=upper[0]/risk,
                        life_mae_lower_R=lower[1]/risk,life_mae_upper_R=upper[1]/risk)
                else:rec['lifetime_status']=lstat
            records.append(rec)
    if touch_mismatch:raise ValueError('FIRST_TOUCH_TRACE_MISMATCH_'+str(touch_mismatch))
    total_entries=sum(x['result']['positions'] for x in runs if x['result'] is not None)
    if len(records)!=total_entries:raise ValueError('ENTRY_INVENTORY')
    by=collections.defaultdict(list)
    for r in records:
        for period in ('ALL',r['month_raw'],r['quarter_raw']):by[(r['candidate'],r['cost'],period)].append(r)
    aggregates=[dict(candidate=c,cost=k,period_raw=p,**summarize(rs)) for (c,k,p),rs in sorted(by.items())]
    result=dict(schema=1,scope=config['scope'],inventory=inventory,entries_from_trace=len(records),
        unique_entry_events_across_costs=len({(r['candidate'],r['segment'],r['entry_raw']) for r in records}),
        first_touch_trace_mismatches=touch_mismatch,metrics=aggregates,
        time_basis=config['time_basis'],trade_lifetime_interpretation=config['trade_lifetime'],
        forward_window_interpretation=config['fixed_window'],unresolved_pnl='NOT_BOUNDED',
        fresh_holdout='NO_FRESH_HOLDOUT',all_six_FF_remain_STOP=True,new_strategy_tested=False,
        engine_replay_executed=False,orders=0,financial_approval=False)
    out.mkdir(parents=True,exist_ok=True);private_out.mkdir(parents=True,exist_ok=True)
    detail=private_out/'entry-excursions-PRIVATE.json'
    detail.write_text(json.dumps(records,default=str,separators=(',',':')),encoding='utf-8')
    (out/'mfe-mae-results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    compact=dict(result,metrics=[r for r in aggregates if r['period_raw']=='ALL'])
    (out/'mfe-mae-summary.json').write_text(json.dumps(compact,indent=2,ensure_ascii=False),encoding='utf-8')
    columns=['candidate','cost','period_raw','entries','resolved','unresolved','full12_n','incomplete_or_gap','raw_day_boundary',
        'target_R_q25','target_R_median','target_R_q75','target_below1R',
        'MFE12_R_q25','MFE12_R_median','MFE12_R_q75','MAE12_R_q25','MAE12_R_median','MAE12_R_q75',
        'first_stop','first_target','ambiguous','no_touch',
        'lifetime_n','life_MFE_lower_median_R','life_MFE_upper_median_R','life_MAE_lower_median_R','life_MAE_upper_median_R']
    period_rows=[]
    for r in aggregates:
        if r['period_raw']=='ALL':continue
        touch=r['full12_first_touch'];eligible=r['forward_eligibility']
        period_rows.append([r['candidate'],r['cost'],r['period_raw'],r['entries'],r['source_resolved'],r['source_unresolved'],
            eligible.get('ELIGIBLE',0),eligible.get('INCOMPLETE_OR_GAP',0),eligible.get('RAW_DAY_BOUNDARY',0),
            r['nominal_target_R']['q25'],r['nominal_target_R']['median'],r['nominal_target_R']['q75'],r['target_below_1R_count'],
            r['mfe12_R']['q25'],r['mfe12_R']['median'],r['mfe12_R']['q75'],r['mae12_R']['q25'],r['mae12_R']['median'],r['mae12_R']['q75'],
            touch.get('STOP',0)+touch.get('STOP_OPEN',0),touch.get('TARGET',0)+touch.get('TARGET_OPEN',0),
            touch.get('AMBIGUOUS',0),touch.get('NO_TOUCH_IN_12',0),r['lifetime_bounds_count'],
            r['life_mfe_lower_R']['median'],r['life_mfe_upper_R']['median'],r['life_mae_lower_R']['median'],r['life_mae_upper_R']['median']])
    (out/'mfe-mae-periods.json').write_text(json.dumps(dict(columns=columns,rows=period_rows),separators=(',',':')),encoding='utf-8')
    receipt=dict(code_sha256=sha(Path(__file__)),protocol_sha256=sha(protocol),
        future_test_protocol_sha256=sha(protocol.parent/'hypotheses-and-future-test-protocol.json'),
        manifest_sha256=sha(raw_dir/'manifest.json'),source_trace_sha256=sha(trace_path),
        source_trace_content_digest=envelope['result_sha256'],source_summary_sha256=sha(source/'ff-session-replay-summary.json'),
        selection_sha256=sha(source/'ff-session-replay-selection.json'),policy_sha256=sha(source/'ff-session-replay-policy.json'),
        prior_year_receipt_sha256=sha(prior_dir/'receipt.json'),private_entry_metrics_sha256=sha(detail),
        output_sha256=sha(out/'mfe-mae-results.json'),raw_uploaded=False,MT5_execution=False,
        public_outputs={n:sha(out/n) for n in ('mfe-mae-summary.json','mfe-mae-periods.json')},
        original_m15_hash_pairs_verified=len(verified),first_touch_trace_mismatches=touch_mismatch,
        new_strategy_tested=False,engine_replay_executed=False)
    (out/'mfe-mae-execution-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(dict(entries=len(records),inventory=inventory,all=[r for r in aggregates if r['period_raw']=='ALL']),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('raw-dir','source','trace-dir','prior-dir','new-dir','protocol','out','private-out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();analyze(a.raw_dir,a.source,a.trace_dir,a.prior_dir,a.new_dir,a.protocol,a.out,a.private_out)
