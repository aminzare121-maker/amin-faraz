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
    source_hash=digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),local/'execution_scenarios.py',local/'comparison.py',local/'registry.py')})
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
