"""Reproducible synthetic shadow demonstration; not market data and not teacher rules.

Produces two paper fills and one blocked decision to verify the actual replay path.
No broker, MT5, external dependencies, credentials, source recordings or network.
"""
import csv
import gzip
import hashlib
import json
import tempfile
from pathlib import Path

from paper_m15_shadow import replay


def demo():
    # OHLC levels and ELIGIBLE decisions below are entirely invented as a software fixture.
    bars = [
        (0,    '3998', '4002', '3997', '4000'),
        (900,  '4000', '4012', '3998', '4010'),
        (1800, '4010', '4011', '4006', '4007'),
        (2700, '4007', '4014', '4005', '4012'),
        (3600, '4012', '4013', '4008', '4010'),
        (4500, '4010', '4015', '4009', '4013'),
        (5400, '4013', '4016', '4011', '4014'),
    ]
    fixtures = {
        0:    ('BUY', 'BREAK_STRONG', 'ELIGIBLE'),
        1800: ('SELL', 'REVERSAL_CLASSIC', 'ELIGIBLE'),
        3600: ('BUY', 'BREAK_STRONG', 'ELIGIBLE'),
        4500: ('SELL', 'REVERSAL_STAR', 'REVIEW'),
    }
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        csv_file, trace, summary, specs = (
            root / 'M15_SYNTHETIC.csv',
            root / 'PRIVATE_raw_decisions.jsonl.gz',
            root / 'SUMMARY.json',
            root / 'trade_specs.json',
        )
        with csv_file.open('w', newline='', encoding='utf8') as f:
            writer = csv.writer(f)
            writer.writerow(['time_raw_epoch', 'open', 'high', 'low', 'close'])
            writer.writerows(bars)
        digest = hashlib.sha256(csv_file.read_bytes()).hexdigest()
        with gzip.open(trace, 'wt', encoding='utf8') as f:
            for t, _, _, _, _ in bars:
                decisions = []
                if t in fixtures:
                    side, rule, status = fixtures[t]
                    decisions.append({'status': status, 'side': side, 'rule_id': rule})
                f.write(json.dumps({'bar_opened_at': t, 'at': t + 900,
                                    'decisions': decisions}) + '\n')
        summary.write_text(json.dumps({'csv_sha256': digest, 'interval_seconds': 900,
                                       'observed_bars': len(bars)}), encoding='utf8')
        # These are lab assumptions, deliberately not claimed to be quotations from teacher.
        cases = [
            {'signal_at': 900, 'side': 'BUY', 'rule_id': 'BREAK_STRONG',
             'known_at': 900, 'source': 'lab-fixture-buy-entry',
             'stop_source': 'lab-fixture-buy-stop',
             'target_source': 'lab-fixture-buy-target',
             'stop': '3995', 'target': '4010'},
            {'signal_at': 2700, 'side': 'SELL', 'rule_id': 'REVERSAL_CLASSIC',
             'known_at': 2700, 'source': 'lab-fixture-sell-entry',
             'stop_source': 'lab-fixture-sell-stop',
             'target_source': 'lab-fixture-sell-target',
             'stop': '4012', 'target': '3997'},
        ]
        specs.write_text(json.dumps({'specs': cases}), encoding='utf8')
        result = replay(csv_file, trace, summary, specs,
                        contract_value='100', lot_size='0.01', roundtrip_fee='6')
        assert result['M15_bars'] == 7
        assert result['eligible_decisions'] == 3
        assert result['completed_paper_trades'] == 2
        assert result['paper_net_usd_closed_only'] == '4.88'
        assert result['outcomes_by_state'] == {'CLOSED_PAPER': 2, 'BLOCKED': 1}
        assert result['teacher_method_verified'] is False
        assert result['teacher_verified_trade_count'] == 0
        assert result['strategy_pnl_verified'] is False
        return {
            'experiment': 'SYNTHETIC_XAUUSD_LIKE_SHADOW_DEMO_NOT_MARKET_BACKTEST',
            'data_source': 'MADE_UP_OFFLINE_BARS_AND_FORCED_ELIGIBLE_SIGNALS',
            'bars': result['M15_bars'],
            'eligible_decisions': result['eligible_decisions'],
            'review_decisions': result['all_decision_statuses'].get('REVIEW', 0),
            'closed_paper_trades': result['completed_paper_trades'],
            'blocked': result['blockers'],
            'net_usd_closed_only': result['paper_net_usd_closed_only'],
            'assumed_contract_units_per_lot': '100',
            'assumed_lot': '0.01',
            'assumed_fee_usd_per_lot_roundtrip': '6',
            'teacher_method_verified': result['teacher_method_verified'],
            'orders_sent': result['orders_sent'],
            'trades': result['trades'],
        }


if __name__ == '__main__':
    print(json.dumps(demo(), indent=2, ensure_ascii=False))
