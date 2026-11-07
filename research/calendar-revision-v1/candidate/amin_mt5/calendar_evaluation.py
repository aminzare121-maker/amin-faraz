"""Frozen conditional forecasts and explicit post-outcome review, not auto-learning."""
from copy import deepcopy
from .calendar_intelligence import digest

def freeze(report,target,horizon,due_ms):
    if horizon not in ('short','medium','long') or type(due_ms) is not int or due_ms<=report['asof_ms']:raise ValueError('HORIZON')
    direction=report['nodes'].get(target)
    if direction not in ('UP','DOWN','FLAT'):raise ValueError('UNRESOLVED_FORECAST')
    selected=[s for s in report['scenarios'] if s['target']==target and s['horizon']==horizon and s['status']=='CONDITIONAL_SUPPORTED']
    if not selected:raise ValueError('TARGET_HORIZON_NOT_SUPPORTED')
    result={'issued_ms':report['asof_ms'],'due_ms':due_ms,'target':target,'horizon':horizon,'direction':direction,
            'model_version':report['model_version'],'analysis_id':report['analysis_id'],'regime':report['regime'],
            'ledger_head':report['ledger_head'],'conditions':deepcopy(selected),'probability':None}
    result['forecast_id']=digest(result);return result

def review(forecast,outcome,now_ms,error_class='UNDETERMINED'):
    if digest({k:v for k,v in forecast.items() if k!='forecast_id'})!=forecast['forecast_id']:raise ValueError('FROZEN_FORECAST_CHANGED')
    if error_class not in ('SOURCE','PROCESSING','INFERENCE','UNDETERMINED'):raise ValueError('ERROR_CLASS')
    if type(now_ms) is not int or now_ms<forecast['due_ms']:raise ValueError('OUTCOME_NOT_DUE')
    if outcome.get('target')!=forecast['target'] or outcome.get('at_ms')!=forecast['due_ms'] or outcome.get('observed_ms',now_ms+1)>now_ms or outcome.get('observed_ms',0)<forecast['due_ms']:raise ValueError('OUTCOME_ALIGNMENT')
    if outcome.get('direction') not in ('UP','DOWN','FLAT') or not outcome.get('evidence_id'):raise ValueError('OUTCOME_EVIDENCE')
    return {'forecast_id':forecast['forecast_id'],'horizon':forecast['horizon'],
            'match':forecast['direction']==outcome['direction'],'outcome':deepcopy(outcome),'error_class':error_class,
            'error_class_method':'EXPLICIT_REVIEWER_LABEL_NOT_AUTOMATIC_CAUSAL_DIAGNOSIS',
            'calibrated_accuracy':None,'automatic_model_change':False,'trade_authorized':False}
