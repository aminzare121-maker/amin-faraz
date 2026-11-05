"""Independent calendar/sentiment assurance, never a new directional model."""
from .calendar_policy import assess,decision,policy_version
from .forecast_evaluation import evaluate_records,HORIZONS


def evaluate(report,paired,now_ms,source_audits):
    rows=[]
    def add(key,status,reason,metrics,needed):
        rows.append({'id':key,'status':status,'reason':reason,'metrics':metrics,
            'required_next_evidence':needed,'can_authorize_orders':False})
    usable=sum(x.get('raw_hash_verified') is True and x.get('fresh_at_evaluation') is True for x in source_audits)
    add('calendar_sources','pass' if usable>=2 else 'blocked','SOURCE_TIME_AND_RAW_CONTENT_BINDING',
        {'sources_checked':len(source_audits),'fresh_hash_bound_sources':usable},
        'At least two appropriate primary sources, exact publication/availability times and immutable content.')
    assessments={side:assess(report,now_ms,side) for side in ('buy','sell')}
    candidate=next((side for side,a in assessments.items() if a['allowed']),None)
    add('calendar_scenario','pass' if candidate else 'waiting',
        assessments[candidate]['reason'] if candidate else assessments['buy']['reason'],
        {'supported_directions':sum(a['allowed'] for a in assessments.values())},
        'Typed source-linked short/long scenarios with explicit uncertainty; no buy/sell inferred from an event title alone.')
    # Empty verified records honestly express absence of exported registry evidence.
    evaluation=evaluate_records([],now_ms,policy_version(),horizon_ms=HORIZONS[0])
    add('calendar_forward_validation','waiting','VERIFIED_FORWARD_REGISTRY_NOT_EXPORTED',
        {'independent_samples':evaluation['independent_sample_count'],'measured_accuracy':evaluation['accuracy'],
            'verified_incremental_return':None},
        'Actual pre-outcome frozen predictions, independent target-time quotes/costs and verified registry provenance; summaries are not certificates.')
    issued=paired.get('observed_ms') if isinstance(paired,dict) else None
    fresh=type(issued) is int and 0<=now_ms-issued<=15000
    count=paired.get('settled_pairs') if isinstance(paired,dict) else None
    add('calendar_paired_measurement','waiting','PAIRED_RESEARCH_IS_NOT_ACCOUNT_PROFIT',
        {'summary_fresh':fresh,'reported_settled_pairs':count if type(count) is int and count>=0 else None,
            'broker_net_profit_verified':False},
        'Matched price-only versus sentiment-selected opportunities with coverage, missed outcomes and full execution costs.')
    gate=decision(report,None,now_ms,candidate or 'none')
    add('calendar_execution_readiness','blocked',gate['reason'],{'order_authorization':False},
        'Exact model/source cohort validation plus fresh native price candidate, news, account risk and mandate. Calendar alone cannot authorize.')
    return {'observed_ms':now_ms,'scope':'Amin calendar sentiment only; no changes to other strategy methods',
        'stages':rows,'scenario_assessments':assessments,'forward_validation':evaluation,
        'source_audits':source_audits,'execution_readiness':False,'directional_model_added':False,
        'orders_sent':0,'active_engine_changed':False,'learning_feedback_enabled':False,
        'limitations':['Bank holiday/news timing is distinct from directional sentiment.',
            'Source availability is not forecast accuracy or deployable profit.',
            'No trusted registry is synthesized from imported JSON eligibility flags.']}
