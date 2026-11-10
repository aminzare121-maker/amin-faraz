"""Executable Artin 13-route + original Technical/FXM teacher PDF paper trade motor.

A real event-driven lifecycle, not a static gate report. No order API imports,
no broker login, no automatic annotation of teacher signals from bare OHLC.
Teacher/market facts must be pre-observed and causally source-tagged. A paper
fill is a modelled fill from a timestamped BID/ASK quote, never broker proof.

Sources: Technical(1).pdf pp.13-17; FXM.pdf pp.2-7; pinned Artin 13
route motor in core/. Existing code is loaded unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from core.entry_engine import Engine, Observation, Fact, RULE_IDS
from core.capital import Instrument, Costs
from fxm_teacher_policy import AccountRisk, dec, day_trade_permission
from artin_teacher_sl_tp_motor import build_plan, PaperPosition, SingleTargetPaperPosition

SCHEMA = 'artin_unified_paper_events_v1'
PDF_HASHES = {'FXM.pdf':'504930d6b148b008f134a92e7445e870b7e3fc54478db0956f82f695c23a7af1',
              'Technical(1).pdf':'f50f66139fa96c8083e936f368160c3b77667302174e3e1c6084c8bbd6a1a909'}
ZERO = '0' * 64

class MotorError(ValueError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False, default=str).encode('utf-8')


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def require_source(event, field='source'):
    value = event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MotorError('SOURCE_PROVENANCE_REQUIRED:' + field)
    return value


def money(value, name, allow_zero=False):
    try:
        return dec(value, name, allow_zero=allow_zero)
    except (ValueError, TypeError) as e:
        raise MotorError('BAD_EXACT_PRICE_OR_MONEY:' + name) from e


def quote_fields(event):
    bid = money(event['bid'], 'bid'); ask = money(event['ask'], 'ask')
    if bid > ask:
        raise MotorError('BID_EXCEEDS_ASK')
    return bid, ask


def teacher_fact_map(event, at):
    raw = event.get('facts')
    if not isinstance(raw, dict):
        raise MotorError('SOURCE_TAGGED_TEACHER_FACTS_REQUIRED')
    converted = {}
    for name, x in raw.items():
        if not isinstance(x, dict) or set(x) != {'value', 'known_at', 'source'}:
            raise MotorError('INVALID_SOURCED_FACT:' + name)
        require_source(x)
        if type(x['known_at']) is not int or x['known_at'] > at or x['known_at'] < 0:
            raise MotorError('LOOKAHEAD_OR_UNTIMED_FACT:' + name)
        val = x['value']
        if type(val) is float:
            raise MotorError('BINARY_FLOAT_NOT_ALLOWED:' + name)
        converted[name] = Fact(val, x['known_at'], x['source'])
    return converted


def check_core_integrity(core_dir):
    """Refuse a modified pinned strategy core; no silent invented route logic."""
    root = Path(core_dir)
    manifest = root/'LEGACY_SHA_MANIFEST.json'
    if not manifest.is_file():
        raise MotorError('PINNED_CORE_MANIFEST_MISSING')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('source_commit') != 'b48fb06f8b2b0d134292025f5b27fc670ad2a293':
        raise MotorError('UNEXPECTED_TEACHER_CORE_COMMIT')
    if not isinstance(data.get('files_sha256'), dict) or not data['files_sha256']:
        raise MotorError('INVALID_TEACHER_CORE_MANIFEST')
    for name, fingerprint in data['files_sha256'].items():
        p = root/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != fingerprint:
            raise MotorError('CHANGED_TEACHER_CORE:' + name)
    return data['source_commit']


@dataclass
class Active:
    plan: dict
    position: Any
    opened_at: int
    entry_quote_source: str
    open_price: Decimal


def inspect_pdf_sources(folder):
    result={}
    for filename,expected in PDF_HASHES.items():
        path=Path(folder)/filename
        if path.is_file():
            observed=hashlib.sha256(path.read_bytes()).hexdigest()
            if observed != expected:raise MotorError('TEACHER_PDF_CHANGED:'+filename)
            result[filename]={'present':True,'sha256':observed,'hash_matched_original_upload':True}
        else:
            result[filename]={'present':False,'expected_sha256':expected,
                              'hash_matched_original_upload':False}
    return result


def run_document(doc, *, core_dir='core'):
    """Run supplied source events in order; append verifiable chain of paper events."""
    if not isinstance(doc, dict) or doc.get('schema') != SCHEMA:
        raise MotorError('WRONG_EVENT_DOCUMENT_SCHEMA')
    core_commit = check_core_integrity(core_dir)
    pdf_source_check=inspect_pdf_sources(Path(__file__).parent)
    if doc.get('mode') not in ('PAPER_SOURCED', 'SYNTHETIC_TEST'):
        raise MotorError('NO_BROKER_ORDER_MODE_SUPPORTED')
    cfg = doc.get('account')
    if not isinstance(cfg, dict):
        raise MotorError('ACCOUNT_CONFIGURATION_REQUIRED')
    account = AccountRisk(money(cfg['balance'],'balance'),
                          money(cfg['reference_balance'],'reference_balance'),
                          money(cfg['risk_pct'],'risk_pct'))
    raw_contract = doc.get('contract')
    if not isinstance(raw_contract, dict):
        raise MotorError('BROKER_CONTRACT_REQUIRED')
    require_source(raw_contract)
    instrument = Instrument(money(raw_contract['money_per_price_unit_per_lot'],'contract_value'),
                            money(raw_contract['min_lot'],'min_lot'),
                            money(raw_contract['lot_step'],'lot_step'))
    raw_costs = doc.get('costs')
    if not isinstance(raw_costs, dict):
        raise MotorError('EXPLICIT_COST_MODEL_REQUIRED')
    require_source(raw_costs)
    costs = Costs(money(raw_costs['round_trip_fee_per_lot'],'fee',allow_zero=True),
                  money(raw_costs['adverse_price_allowance'],'slippage',allow_zero=True))
    engine = Engine('ARTIN_ORIGINAL_13_TEACHER_PATHS', tuple(RULE_IDS))
    events = doc.get('events')
    if not isinstance(events, list) or not events:
        raise MotorError('NONEMPTY_EVENT_STREAM_REQUIRED')
    clock = -1; seen_ids = set(); active = None; staged = None; outcomes = []
    current_day = None; day_source = None; trace = []; tip = ZERO; balance = account.balance
    counts = {'SETUP':0,'PLANNED':0,'FILL':0,'OPENED':0,'QUOTE':0,'EXIT_FILL':0,
              'CLOSED':0,'BLOCKED':0,'STOP_MOVES':0}

    closed_days = set()

    def log(event, status, detail):
        nonlocal tip
        payload={'index':len(trace)+1,'id':event['id'],'at':event['at'],
                 'kind':event['kind'],'status':status,'detail':detail,'prev_sha256':tip}
        tip = sha(payload)
        trace.append({**payload,'sha256':tip})

    for event in events:
        if not isinstance(event, dict):
            raise MotorError('EVENT_OBJECT_REQUIRED')
        ident = event.get('id'); at=event.get('at'); kind=event.get('kind')
        if not isinstance(ident,str) or not ident.strip() or ident in seen_ids:
            raise MotorError('DUPLICATE_OR_MISSING_EVENT_ID')
        if type(at) is not int or at < clock:
            raise MotorError('NONMONOTONIC_EVENT_TIME')
        if kind not in ('SETUP','FILL','QUOTE','EXIT_FILL'):
            raise MotorError('UNKNOWN_EVENT_KIND')
        require_source(event)
        if doc['mode'] == 'PAPER_SOURCED':
            def _synthetic(value):
                if isinstance(value, dict):
                    return any((k=='source' and isinstance(v,str) and 'synthetic' in v.lower()) or _synthetic(v)
                               for k,v in value.items())
                if isinstance(value, list):return any(_synthetic(v) for v in value)
                return False
            if _synthetic(event) or 'synthetic' in raw_contract['source'].lower() or 'synthetic' in raw_costs['source'].lower():
                raise MotorError('SYNTHETIC_EVIDENCE_IN_REAL_EVENT_STREAM')
        seen_ids.add(ident); clock=at;counts[kind]+=1

        if kind == 'SETUP':
            if staged or active:
                counts['BLOCKED']+=1
                log(event,'BLOCKED_EXISTING_POSITION_OR_STAGED_PLAN',{})
                continue
            side=event.get('side');route=event.get('route')
            if side not in ('BUY','SELL') or route not in RULE_IDS:
                counts['BLOCKED']+=1;log(event,'BLOCKED_INVALID_ROUTE_OR_SIDE',{});continue
            # A session/day name must be provided by the source. We do not
            # assume raw broker timestamps are UTC or invent a day boundary.
            day=event.get('trading_day')
            if not isinstance(day,str) or not day.strip():
                counts['BLOCKED']+=1;log(event,'BLOCKED_SOURCE_DAY_MISSING',{});continue
            if current_day != day:
                if day in closed_days:
                    raise MotorError('TRADING_DAY_ROLLBACK')
                if current_day is not None:
                    closed_days.add(current_day)
                outcomes=[];current_day=day;day_source=event['source']
            gate=day_trade_permission(outcomes)
            if gate['status'] != 'PAPER_DAY_SEQUENCE_CONTINUE':
                counts['BLOCKED']+=1;log(event,'BLOCKED_FXM_DAY_SEQUENCE',gate);continue
            if balance<=0:
                counts['BLOCKED']+=1;log(event,'BLOCKED_NONPOSITIVE_PAPER_EQUITY',{});continue
            rgate=AccountRisk(balance,account.reference_balance,account.risk_pct).assess()
            if rgate['status'] != 'RISK_BUDGET_AVAILABLE':
                counts['BLOCKED']+=1;log(event,'BLOCKED_FXM_ACCOUNT_RISK',rgate);continue
            observed=Observation(side,at,teacher_fact_map(event,at))
            d=engine.evaluate(route,observed)
            if d.status!='ELIGIBLE':
                counts['BLOCKED']+=1
                log(event,'BLOCKED_PINNED_13_ROUTE',{'route':route,'status':d.status,
                    'reasons':list(d.reasons),'fingerprint':d.input_fingerprint})
                continue
            chart=event.get('technical_chart')
            # Source checks are also independently applied in build_plan().
            plan=build_plan(route=route,side=side,decision_at=at,
                 chart_evidence=chart,
                 account=AccountRisk(balance,account.reference_balance,account.risk_pct),
                 instrument=instrument,costs=costs,
                 target_mode=event.get('target_mode'),
                 target_mode_source=event.get('target_mode_source'),
                 winrate=event.get('winrate'),
                 winrate_evidence=event.get('winrate_evidence'),
                 teacher_core_eligible=True)
            if plan['status'] != 'PAPER_TEACHER_PDF_TRADE_PLAN':
                counts['BLOCKED']+=1
                log(event,'BLOCKED_TEACHER_PDF_OR_FXM',{'reason':plan['status'],
                         'details':{k:v for k,v in plan.items() if k!='position'}})
                continue
            staged=plan;counts['PLANNED']+=1
            log(event,'PAPER_PLAN_WAITING_FOR_PRICE_ALIGNED_FILL',
                {k:v for k,v in plan.items() if k!='position'})
            continue

        if kind == 'FILL':
            if staged is None or active is not None:
                counts['BLOCKED']+=1;log(event,'BLOCKED_FILL_WITHOUT_PLAN',{});continue
            bid,ask=quote_fields(event)
            side=staged['side'];observed=ask if side=='BUY' else bid
            intended=money(staged['entry'],'entry')
            if observed!=intended:
                counts['BLOCKED']+=1
                log(event,'PAPER_FILL_PRICE_DIFFERS_REPLAN_REQUIRED',{
                    'planned_entry':str(intended),'observed':str(observed)})
                staged=None
                continue
            active=Active(staged,staged['position'],at,event['source'],observed)
            staged=None;counts['OPENED']+=1
            log(event,'PAPER_POSITION_OPENED_ASSUMED_QUOTE_FILL',{
                'side':side,'entry':str(observed),'lot':active.plan['lots'],
                'source_quote':event['source'],'real_broker_fill':False})
            continue

        if kind=='QUOTE':
            if active is None:
                log(event,'QUOTE_NO_PAPER_POSITION',{});continue
            bid,ask=quote_fields(event)
            new_position, decision=active.position.observe_quote(str(bid),str(ask),at)
            if decision['status'] in ('PAPER_MOVE_STOP_TO_TP1','PAPER_MOVE_STOP_TO_ENTRY'):
                counts['STOP_MOVES']+=1
            active.position=new_position
            log(event,decision['status'],{k:str(v) for k,v in decision.items()})
            continue

        if kind=='EXIT_FILL':
            if active is None or active.position.pending_exit is None:
                counts['BLOCKED']+=1;log(event,'BLOCKED_EXIT_WITHOUT_TRIGGER',{});continue
            bid,ask=quote_fields(event)
            exit_price=bid if active.plan['side']=='BUY' else ask
            sign=Decimal(1) if active.plan['side']=='BUY' else Decimal(-1)
            gross=sign*(exit_price-active.open_price)*money(active.plan['lots'],'lots') * instrument.money_per_price_unit_per_lot
            fee=costs.round_trip_fee_per_lot * money(active.plan['lots'],'lots')
            net=gross-fee;balance += net
            if balance <= 0:
                # A negative model equity is a stop state, not an allowed new trade.
                balance=Decimal(0)
            flag = active.position.pending_exit
            # FXM day sequence: p5 only talks about recorded TP/SL, never
            # translates a break-even result into an invented loss or win.
            if net>0:outcomes.append('TP')
            elif net<0:outcomes.append('SL')
            else:outcomes.append('BE')  # next setup -> REVIEW, not force TP/SL
            counts['CLOSED']+=1
            log(event,'PAPER_CLOSED_FROM_EXPLICIT_EXIT_QUOTE',{
                'exit_reason':flag,'exit_quote':str(exit_price),
                'model_gross_pnl':str(gross),'model_fee':str(fee),
                'model_net_pnl':str(net),'balance_after':str(balance),
                'actual_broker_fill':False,'day_sequence_outcome':outcomes[-1],
                'no_slippage_or_execution_guarantee':True})
            active=None

    return {'schema':'artin_unified_paper_execution_v1',
            'source_mode':doc['mode'],'pinned_teacher_core':core_commit,
            'source_documents':['Technical(1).pdf#pages=13-17','FXM.pdf#pages=2-7'],
            'original_teacher_pdf_integrity':pdf_source_check,
            'input_sha256':sha(doc),'journal_sha256':tip,
            'events_processed':len(events),'counts':counts,
            'paper_balance_initial':str(account.balance),'paper_balance_final':str(balance),
            'active_paper_position':active is not None,
            'staged_entry_waiting_for_paper_quote':staged is not None,
            'teacher_video_semantic_verification':False,
            'source_annotations_independently_verified':False,
            'broker_order_api_present':False,'orders_sent':0,
            'real_broker_profit':None,'strategy_profitability_verified':False,
            'trace':trace}


def verify_journal(result):
    """Verify full execution chain, not just its final receipt."""
    tip=ZERO
    for i,item in enumerate(result['trace'],1):
        if item['index']!=i or item['prev_sha256']!=tip:return False
        body={k:v for k,v in item.items() if k!='sha256'}
        if sha(body)!=item['sha256']:return False
        tip=item['sha256']
    return tip==result['journal_sha256']


def main():
    p=argparse.ArgumentParser(description='Teacher-PDF sourced Artin 13-route EVENT-DRIVEN paper motor; no orders')
    p.add_argument('--events',type=Path,required=True)
    p.add_argument('--pinned-core',type=Path,default=Path(__file__).parent/'core')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    doc=json.loads(a.events.read_text(encoding='utf-8'))
    result=run_document(doc,core_dir=a.pinned_core)
    if not verify_journal(result):raise MotorError('INVALID_JOURNAL_CHAIN')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as fh:
        json.dump(result,fh,ensure_ascii=False,indent=2)
        fh.write('\n')
    print(json.dumps({k:result[k] for k in ('events_processed','counts','paper_balance_final',
          'teacher_video_semantic_verification','orders_sent')},ensure_ascii=False))

if __name__=='__main__':main()