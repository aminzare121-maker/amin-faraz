"""Build sanitized data inventory and a second non-overlapping comparison from existing files."""
import csv,hashlib,io,json
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from real_overlap import aggregate,metrics
from offline_evidence import load_existing,PRIVATE
from data_validity import gate
from registry import Registry,digest
ROOT=Path(__file__).resolve().parent
def dump(name,data):(ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
def inventory():
    private=ROOT.parent/'PRIVATE_DUKASCOPY_SAMPLE'
    sources=[('EplanetDemo','M15',PRIVATE/'manifest.json',23643,'BID'),('EplanetDemo','TICK',PRIVATE/'boundary-repair/receipt.json',7946,'BID_ASK')]
    for sha,n,side in [('7866d3a24764d049023e0934e81655c01b329c1df63b5ad7c4aa1aaf2e002484',1380,'BID'),('fb27741a462c4392c847700c174ffcb0603db55845caa588442fc15734e802ad',1380,'ASK'),('817d3f1059740b2339c4c7b6cc4ccb109be74c1c8b4eb6122e6276ceaf648960',683,'BID')]:sources.append(('Dukascopy','M1',private/(sha+'.csv'),n,side))
    envelopes=[];bank=Registry(ROOT/'local-research.sqlite')
    for source,kind,path,count,side in sources:
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        e=dict(schema='faraz-data-v1',source=source,version='2026-11-05-existing',raw_sha256=sha,kind=kind,rows=count,
            hash_scope='manifest_or_repair_receipt_with_child_file_hashes' if source=='EplanetDemo' else 'original_csv_bytes',
            price_side={'value':side,'status':'CONDITIONAL','reason':'Prior source/quote evidence; not a new whole-year certification'},
            time={'value':'BROKER_SERVER' if source=='EplanetDemo' else 'UTC','status':'UNKNOWN' if source=='EplanetDemo' else 'CONDITIONAL'},
            candle_completeness={'status':'CONDITIONAL','reason':'Observed rows checked previously; scheduled coverage not certified'},
            session={'status':'UNKNOWN'},bid_ask={'status':'CONDITIONAL' if kind=='TICK' else 'UNKNOWN'},
            provenance={'status':'CONDITIONAL','reason':'Private research scope only; original sources preserved'},evidence={})
        gates={p:gate(e,p) for p in ('raw_inventory','price_comparison','strategy_research')}
        bank.artifact('market-contract:'+digest(e),sha,{'contract':e,'gates':gates},valid=False)
        envelopes.append({'contract':e,'gates':gates})
    dump('data-validity-inventory.json',envelopes);return envelopes

def second_comparison():
    private=ROOT.parent/'PRIVATE_DUKASCOPY_SAMPLE'
    sha='817d3f1059740b2339c4c7b6cc4ccb109be74c1c8b4eb6122e6276ceaf648960'
    raw=(private/(sha+'.csv')).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('RAW_HASH')
    clock=json.loads((ROOT/'terminal-clock-sanitized.json').read_text())
    if clock['chart_mode']!=clock['chart_mode_bid_constant'] or not 7190<clock['quote_minus_wall_seconds']<7205:raise ValueError('CLOCK_SIDE')
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    start=int(datetime(2026,11,5,tzinfo=timezone.utc).timestamp());end=start+9*3600
    subset=[r for r in rows if start<=int(datetime.fromisoformat(r['Etc/UTC']).timestamp())<end]
    right,excluded=aggregate(subset,start,end,int(clock['utc_wall_before']))
    source,_=load_existing()
    left=[{**{k:r[k] for k in ('open','high','low','close')},'time':int(r['time'])-7200} for r in source if start<=int(r['time'])-7200<end]
    a={r['time']:r for r in left};b={r['time']:r for r in right};common=sorted(a.keys()&b.keys())
    diffs=[dict(time=t,**{k:str(Decimal(a[t][k])-Decimal(b[t][k])) for k in ('open','high','low','close')}) for t in common]
    out=dict(period_start='2026-11-05T00:00:00Z',period_end_exclusive='2026-11-05T09:00:00Z',status='CONDITIONAL_PRICE_DIAGNOSTIC_NOT_VALIDATED_DATA',
        mapping='-7200 for this Nov05 sample only, fixed by prior live clock/support winter statement; not price-fit',
        source_sha256=sha,downloaded_rows=0,existing_m1_rows=len(rows),selected_m1_rows=len(subset),eplanet_m15=len(left),dukascopy_m15=len(right),common_m15=len(common),
        left_only=sorted(a.keys()-b.keys()),right_only=sorted(b.keys()-a.keys()),excluded=excluded,metrics=metrics(diffs),
        spread_comparison='UNKNOWN_NO_SYNCHRONOUS_COMMON_QUOTES',year_certified=False,financial_backtest=False)
    dump('comparison-nov05-sanitized.json',out);return out
if __name__=='__main__':inventory();print(json.dumps(second_comparison(),indent=2))
