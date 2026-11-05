"""Offline-only bridge to the existing experiment engine, with exact result reuse."""
import hashlib,json,platform,sys
from pathlib import Path
from dataclasses import asdict
from registry import digest

ENGINE=Path('C:/Users/Pixel/Documents/Amin-MT5-0.4.1/amin-mt5/src')
COST_KEYS={'spread','slippage','commission_per_lot','contract','volume','swap_long_per_lot','swap_short_per_lot'}

def existing_engine():
    sys.path.insert(0,str(ENGINE)) if str(ENGINE) not in sys.path else None
    from amin_mt5.experiments import run_experiment
    from amin_mt5.research import Costs
    return run_experiment,Costs

def engine_fingerprint():
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ENGINE/'amin_mt5').glob('*.py'))}
    sources['bridge']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return digest(sources)

def replay_registered(bank,bars,dataset_id,order,cost_inputs):
    """Attach the execution-scenario extension to the same ledger, without trading runtime."""
    from execution_scenarios import replay
    local=Path(__file__).resolve().parent
    source_hash=digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),local/'execution_scenarios.py',local/'carry_costs.py',local/'comparison.py',local/'registry.py',local/'vendor/research_ledger.py')})
    spec=dict(code_sha256=source_hash,datasets={dataset_id:digest(bars)},settings={'frozen_order':order,'kind':'EXECUTION_FIXTURE'},
        costs=cost_inputs,protocol_sha256=digest({'intrabar':'stop-first','cost_basis':'ASSUMPTION','strategy_selection':False}),
        environment={'python':platform.python_version()},metrics_version='execution-scenarios-v1',
        split={'start':bars[0]['time'],'end':bars[-1]['time']+900,'selection':'NONE_FIXED_ORDER'},seed=0)
    reserved=bank.start(spec)
    if reserved['action']!='EXECUTE':return reserved
    try:
        report=replay(bars,order,**cost_inputs)
        bank.finish_run(reserved['id'],report,True)
        return {'action':'EXECUTED','id':reserved['id'],'result':report}
    except Exception as exc:
        bank.finish_run(reserved['id'],{'error_type':type(exc).__name__},False)
        raise

def execute(bank,bars,dataset_id,costs,protocol,*,scope):
    if scope not in ('SYNTHETIC_DIAGNOSTIC','HYPOTHETICAL_COST_RESEARCH'):raise ValueError('RESEARCH_SCOPE_REQUIRED')
    if set(costs)!=COST_KEYS or any(v is None for v in costs.values()):raise ValueError('ALL_COSTS_EXPLICIT_REQUIRED')
    if costs['contract']!=100:raise ValueError('XAUUSD_ST_CONTRACT_100_REQUIRED')
    if protocol.get('cost_basis')!='HYPOTHETICAL_EXPLICIT' or protocol.get('variable_spread') is not False:raise ValueError('UNSUPPORTED_HISTORICAL_COST_MODEL')
    if any(not b.get('final') or b.get('time_basis')=='broker-server' for b in bars):raise ValueError('UNCONFIRMED_TIME_OR_CLOSURE')
    if not bars or any(b.get('observed_at',0)<b['time']+900 for b in bars):raise ValueError('AVAILABILITY_BEFORE_CLOSE')
    run,Costs=existing_engine();checked=Costs(**costs).validate()
    spec=dict(code_sha256=engine_fingerprint(),datasets={dataset_id:digest(bars)},settings={'scope':scope,'variants':'existing-six','engine':'amin_mt5.experiments.run_experiment'},
        costs=asdict(checked),protocol_sha256=digest(protocol),environment={'python':platform.python_version(),'platform':platform.platform()},
        metrics_version='existing-engine-plus-bridge-v1',split={'start':bars[0]['time'],'end_exclusive':bars[-1]['time']+900,'n':len(bars),'train':.5,'validation':.25,'holdout':.25,'embargo_bars':8},seed=581)
    reservation=bank.start(spec)
    if reservation['action']!='EXECUTE':return reservation
    try:
        report=run(bars,checked)
        report.update(scope=scope,cost_basis='HYPOTHETICAL_EXPLICIT',market_profitability_verified=False,
            demo_review_eligible=False,promotion_eligible=False,live_promotion=False,
            status='OFFLINE_DIAGNOSTIC_ONLY',intrabar_path='UNKNOWN_STOP_FIRST_CONVENTION',
            historical_swap_verified=False,variable_spread_supported=False,
            holdout_freshness='NOT_CERTIFIED_BY_THIS_BRIDGE',registry_run_id=reservation['id'])
        bank.finish_run(reservation['id'],report,True)
        return {'action':'EXECUTED','id':reservation['id'],'result':report}
    except Exception as exc:
        bank.finish_run(reservation['id'],{'error_type':type(exc).__name__,'scope':scope},False)
        raise

def evaluate_strategies(bank,bars,dataset_id,contexts,protocol):
    """Run the research revision of the actual selector through scenario execution.
    Legacy execute remains reproducible, but cannot confer selection approval.
    """
    existing_engine()
    from research_engine.experiments import run_experiment as scenario_runner
    from scenario_segment import evaluate_segment
    local=Path(__file__).resolve().parent
    files=[local/'engine_bridge.py',local/'execution_scenarios.py',local/'carry_costs.py',local/'scenario_segment.py',local/'research_engine/experiments.py',local/'registry.py',local/'comparison.py',local/'evidence_gates.py',local/'research_protocol.py',local/'holdout_guard.py',local/'vendor/research_ledger.py']
    code=digest({'engine':engine_fingerprint(),'research':{str(p.relative_to(local)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
    from amin_mt5.strategy import candidates
    spec=dict(code_sha256=code,datasets={dataset_id:digest(bars)},settings={'strategies':[asdict(c) for c in candidates()], 'scope':'SYNTHETIC_DIAGNOSTIC'},costs=contexts,
        protocol_sha256=digest(protocol),environment={'python':platform.python_version()},metrics_version='selector-scenarios-v1',
        split={'n':len(bars),'train':.5,'validation':.25,'holdout':.25,'embargo':8,'time_interpretation_hash':digest(protocol.get('time_interpretation'))},seed=581)
    preregistered=protocol.get('preregistered')
    before_holdout=None
    if preregistered is not None:
        from research_protocol import freeze,reserve_trial,expose_holdout
        name=preregistered['id'];body=preregistered['body']
        expected_split={'train':[44,len(bars)//2],'validation':[len(bars)//2+8,len(bars)*3//4],'holdout':[len(bars)*3//4+8,len(bars)]}
        expected_holdout=digest({'dataset':digest(bars),'range':expected_split['holdout']})
        if body['split']!=expected_split or body['holdout_fingerprint']!=expected_holdout:raise ValueError('PROTOCOL_DATA_SPLIT_MISMATCH')
        freeze(bank,name,body);reserve_trial(bank,name,spec)
        def before_holdout():
            from holdout_guard import seal
            from registry import identity
            seal(identity(spec),bars[0]['time'],bars[-1]['time']+900,
                 bars[expected_split['holdout'][0]]['time'],bars[-1]['time']+900)
            expose_holdout(bank,name)
    reservation=bank.start(spec)
    if reservation['action']!='EXECUTE':return reservation
    try:
        # Only synthetic diagnostics are authorized on this entry point until year gates clear.
        if protocol.get('scope')!='SYNTHETIC_DIAGNOSTIC' or protocol.get('time_interpretation')!='SYNTHETIC_UTC':raise ValueError('REAL_YEAR_GATE_BLOCKED')
        if protocol.get('news') not in (None,[]):raise ValueError('NEWS_NOT_SUPPORTED_USE_POINT_IN_TIME_GATE')
        previous=None
        for b in bars:
            t=b['time']
            if type(t) is not int or t%900 or (previous is not None and t-previous!=900):raise ValueError('TIME_ORDER_OR_GAP')
            if b.get('time_basis')!='synthetic-UTC' or not b.get('final') or b.get('observed_at',0)<t+900:raise ValueError('TIME_OR_CLOSURE_UNCONFIRMED')
            if b.get('available')!=b['observed_at']:raise ValueError('AVAILABILITY_MISMATCH')
            from execution_scenarios import number
            o,h,l,c=(number(b[k]) for k in ('open','high','low','close'))
            if min(o,h,l,c)<=0 or not l<=min(o,c)<=max(o,c)<=h:raise ValueError('OHLC')
            previous=t
        if set(contexts)!= {'base','stress'}:raise ValueError('SCENARIOS_REQUIRED')
        for ctx in contexts.values():
            if ctx.get('cost_basis')!='ASSUMPTION':raise ValueError('COST_EVIDENCE_NOT_CERTIFIED')
            if ctx.get('commission') is None or ctx.get('slippage') is None:raise ValueError('COST_UNKNOWN')
            if float(ctx['commission'])<0 or float(ctx['slippage'])<0:raise ValueError('NEGATIVE_COST')
        if preregistered is not None:
            from holdout_guard import check
            check(bars[0]['time'],bars[-1]['time']+900)
        report=scenario_runner(bars,contexts,evaluate=evaluate_segment,before_holdout=before_holdout)
        report.update(registry_run_id=reservation['id'],dependency_spec=spec)
        bank.finish_run(reservation['id'],report,True)
        return {'action':'EXECUTED','id':reservation['id'],'result':report}
    except Exception as exc:
        bank.finish_run(reservation['id'],{'error_type':type(exc).__name__,'reason':str(exc),'profitability_verified':False},False)
        raise
