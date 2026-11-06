"""Independent rational audit of recorded traces; does not rerun strategies."""
import json,hashlib,sys
from fractions import Fraction as F
from pathlib import Path
from factorial_run import cached,ROOT,PRIVATE_OUTPUT

def main():
    summary=json.loads((ROOT/'factorial-summary.json').read_text())
    before_id='81a11e869cb5c6a842baa13729263d963bf41f55295dc96d84f7bedea838dbb1'
    before=cached(before_id);after=cached(summary['identity'])
    cells=resolved_checks=unknown_checks=0;changes=[]
    metrics=('positions','resolved','unresolved','scenario_net_usd','scenario_max_drawdown_usd','known_partial_net_usd')
    for wid,methods in after.items():
        for name,modes in methods.items():
            if name=='baseline_SMA':continue
            for mode,policies in modes.items():
                for policy,r in policies.items():
                    cells+=1;old=before[wid][name][mode][policy]
                    if any(r[k]!=old[k] for k in metrics):changes.append([wid,name,mode,policy])
                    equity=peak=dd=F(0)
                    for row in r['rows']:
                        assert row['signal_time']<=row['entry_time']
                        assert all(x['effective_time']>=row['entry_time']+900 for x in row.get('stop_adjustments',[]))
                        if row['net_scenario_usd'] is None:
                            unknown_checks+=1;assert r['scenario_net_usd'] is None;continue
                        sign=1 if row['side']=='buy' else -1
                        gross=sign*(F(row['exit'])-F(row['entry']))*100*F(row['lots'])
                        net=gross-F(summary['policy']['costs']['commission_roundtrip_per_lot'])*F(row['lots'])
                        assert F(row['gross_scenario_usd'])==gross and F(row['net_scenario_usd'])==net
                        resolved_checks+=1;equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity)
                    assert F(r['known_partial_net_usd'])==equity
                    if r['scenario_net_usd'] is not None:
                        assert F(r['scenario_net_usd'])==equity and F(r['scenario_max_drawdown_usd'])==dd
    audit=json.loads((ROOT/'limited-window-audit.json').read_text())
    receipt_checks={}
    for file,sha in audit['evidence_hashes'].items():
        actual=hashlib.sha256((ROOT/file).read_bytes()).hexdigest()
        if actual!=sha:raise ValueError('EVIDENCE_RECEIPT_CHANGED')
        receipt_checks[file]=actual
    result=dict(before_identity=before_id,after_identity=summary['identity'],matrix_cells=144,
        compared_cells=cells,changed_financial_cells=changes,
        rational_resolved_row_checks=resolved_checks,unknown_row_checks=unknown_checks,
        note='Checks across scenario variants, NOT independent market trades',
        evidence_hashes_verified=receipt_checks,
        corrected_tick_count=7946,tick_coverage='Nov05 08:30-09:00 CONDITIONAL_UTC only',
        Nov04_ticks=0,session='UNKNOWN',historical_slippage='UNKNOWN',historical_rollover='UNKNOWN',
        mtm_drawdown='UNKNOWN',original_trading_modules_loaded=any(x in sys.modules for x in ('MetaTrader5','amin_mt5.mt5')),
        status='ARITHMETIC_CHECKS_PASS_NOT_FINANCIAL_APPROVAL')
    (ROOT/'factorial-independent-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
