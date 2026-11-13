"""Independent local CLI. No broker, network, old engine, subprocess or orders."""
import argparse
from dataclasses import asdict,is_dataclass
from decimal import Decimal
import json
from pathlib import Path
from entry_engine import Engine,Fact,Observation
from examples import demo_document
from capital import Instrument,Costs,BoxPlan
from trade_machine import TradeMachine,execution_event

def money(value):
    if type(value) not in (str,int,Decimal):raise ValueError('Explicit exact decimal required')
    result=Decimal(value)
    if not result.is_finite():raise ValueError('Nonfinite decimal rejected')
    return result

def json_value(value):
    if isinstance(value,Decimal):return str(value)
    if is_dataclass(value):return asdict(value)
    raise TypeError('Unsupported result object')

def run_paper_trade(engine,case,observation):
    t=case['paper_trade'];i=t['instrument'];c=t['costs'];b=t['box']
    instrument=Instrument(money(i['money_per_price_unit_per_lot']),money(i['min_lot']),money(i['lot_step']))
    costs=Costs(money(c['round_trip_fee_per_lot']),money(c['adverse_price_allowance']))
    box=BoxPlan(b['box_id'],money(b['risk_budget']),b['target_definition'],tuple(b['management_choices']),b['declared_before_box'])
    trade=TradeMachine(engine,box,instrument,costs)
    initial=trade.prepare(case['rule_id'],observation,money(t['entry_price']),money(t['initial_stop']),
                          money(t['target_price']),money(t['aggregate_risk_remaining']),
                          None if t.get('fixed_lots') is None else money(t['fixed_lots']))
    if initial['status']=='PAPER_ENTRY_INTENT':
        last_available=observation.at
        for event in t['events']:
            available=event['known_at']
            if type(available) is not int or available<last_available:
                raise ValueError('annotated events require ascending explicit availability')
            execution_event(trade,event,available)
            last_available=available
    return {'final_state':trade.state,'trace':trade.trace,'orders_sent':0,'broker_connected':False}

def run_document(document):
    if document.get('mode')!='ANNOTATED_OFFLINE':raise ValueError('Only ANNOTATED_OFFLINE mode exists')
    # A batch must not reach rule construction or any evaluation when it
    # cannot reserve aggregate exposure across multiple paper trades.
    if sum('paper_trade' in case for case in document['cases']) > 1:
        raise ValueError('MULTI_TRADE_AGGREGATE_RISK_NOT_RESERVED: account-wide reservation required before multi-trade replay')
    # An empty batch has no entry decision to make and requires no rule plan.
    # Never manufacture a plan fingerprint for a plan that was not validated.
    if not document['cases'] and not document['allowed_rules']:
        return {'mode':'ANNOTATED_OFFLINE','plan_fingerprint':None,
          'synthetic_only':document.get('synthetic_only') is True,
          'decisions':[],'paper_trades':[],'broker_connected':False,
          'orders_sent':0,'raw_chart_classifier_implemented':False,
          'profitability_tested':False,'existing_engine_connected':False}
    engine=Engine(document['plan_id'],tuple(document['allowed_rules']))
    # Validate the entire case identity mapping before evaluating any case.
    # This prevents partial decision/paper-trade processing on an invalid batch.
    case_ids=[];seen_case_ids=set()
    for case_index,case in enumerate(document['cases']):
        if document.get('synthetic_only') is not True and 'case_id' not in case:
            raise ValueError('Non-synthetic case requires explicit case_id for source replay traceability')
        case_id=case.get('case_id',f'case-{case_index:04d}')
        if not isinstance(case_id,str) or not case_id.strip():
            raise ValueError('Each case requires a nonempty case_id when supplied')
        # Case identity must be canonical: whitespace variants can otherwise
        # attach different decisions to the same source example in a replay.
        if case_id != case_id.strip():
            raise ValueError('case_id must not contain surrounding whitespace')
        if case_id in seen_case_ids:
            raise ValueError('Duplicate case_id: '+case_id)
        seen_case_ids.add(case_id)
        case_ids.append(case_id)
    # A single annotated batch is not an account risk ledger. Fail closed rather
    # than treating each caller-supplied aggregate_risk_remaining as a shared reserve.
    # Independent one-trade replays retain their historical behavior.
    if sum('paper_trade' in case for case in document['cases']) > 1:
        raise ValueError('MULTI_TRADE_AGGREGATE_RISK_NOT_RESERVED: account-wide reservation required before multi-trade replay')
    rows=[];paper=[]
    for case_index,case in enumerate(document['cases']):
        case_id=case_ids[case_index]
        facts={k:Fact(v['value'],v['known_at'],v['source']) for k,v in case['facts'].items()}
        observation=Observation(case['side'],case['at'],facts)
        rows.append({'case_id':case_id,'case_index':case_index,**asdict(engine.evaluate(case['rule_id'],observation))})
        if 'paper_trade' in case:paper.append({'case_id':case_id,'case_index':case_index,'rule_id':case['rule_id'],**run_paper_trade(engine,case,observation)})
    return {'mode':'ANNOTATED_OFFLINE','plan_fingerprint':engine.fingerprint,
      'synthetic_only':document.get('synthetic_only') is True,'decisions':rows,'paper_trades':paper,
      'broker_connected':False,'orders_sent':0,'raw_chart_classifier_implemented':False,
      'profitability_tested':False,'existing_engine_connected':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--demo',action='store_true');source.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.input and args.output and args.input.resolve()==args.output.resolve():
        parser.error('Output must not overwrite input')
    document=demo_document() if args.demo else json.loads(args.input.read_text(encoding='utf-8-sig'),parse_float=Decimal)
    result=run_document(document)
    text=json.dumps(result,ensure_ascii=False,indent=2,default=json_value)+'\n'
    if args.output:
        if args.input and args.output.exists() and args.input.samefile(args.output):parser.error('Output aliases input')
        args.output.write_text(text,encoding='utf8')
    print(json.dumps({'decisions':len(result['decisions']),'eligible':sum(d['status']=='ELIGIBLE' for d in result['decisions']),
      'mode':result['mode'],'broker_connected':False,'orders_sent':0},ensure_ascii=False))
    return result

if __name__=='__main__':main()
