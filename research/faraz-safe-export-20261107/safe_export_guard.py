"""Conservative offline guard for publishing Faraz research artifacts.
No network, no raw price reads beyond content scanning, no trade operations.
"""
import json
import re
import sys
from pathlib import Path

SENSITIVE_KEYS = re.compile(r'(?i)(password|passwd|api[_-]?key|access[_-]?token|secret|account[_-]?(?:number|login)|authorization)')
PRICE_KEYS = {'open', 'high', 'low', 'close', 'bid', 'ask', 'tick_volume', 'real_volume', 'spread'}
RAW_ROW = re.compile(r'(?im)^\s*(?:\d{4}[-./]\d{2}[-./]\d{2}[ T,;])[^\n]{0,80}(?:\d{3,5}[.,]\d{1,5}[,;\t]){2,}')

def inspect_text(text, suffix):
    reasons = []
    if suffix in {'.csv', '.tsv', '.parquet', '.db', '.sqlite', '.bi5', '.zip', '.gz'}:
        reasons.append('raw_or_binary_data_format')
    if RAW_ROW.search(text):
        reasons.append('possible_price_rows')
    if suffix == '.json':
        try:
            obj = json.loads(text)
        except ValueError:
            reasons.append('invalid_json')
        else:
            def walk(v):
                if isinstance(v, dict):
                    keys = {str(k).lower() for k in v}
                    if len(keys & PRICE_KEYS) >= 3:
                        reasons.append('ohlc_fields')
                    for k, val in v.items():
                        if SENSITIVE_KEYS.search(str(k)):
                            reasons.append('sensitive_key')
                        walk(val)
                elif isinstance(v, list):
                    for item in v: walk(item)
            walk(obj)
    if re.search(r'(?im)^\s*(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]', text):
        reasons.append('credential_assignment')
    return sorted(set(reasons))

def inspect_file(path):
    p = Path(path)
    if not p.is_file(): return ['not_regular_file']
    if p.stat().st_size > 1_000_000: return ['too_large_for_review']
    try: content = p.read_text(encoding='utf-8')
    except (UnicodeError, OSError): return ['unreadable_or_binary']
    return inspect_text(content, p.suffix.lower())

def main(argv):
    if not argv:
        print('Usage: python safe_export_guard.py FILE...', file=sys.stderr)
        return 2
    failures = 0
    for name in argv:
        reasons = inspect_file(name)
        print(json.dumps({'file': Path(name).name, 'decision': 'BLOCK' if reasons else 'REVIEW_REQUIRED', 'reasons': reasons}, ensure_ascii=False))
        failures += bool(reasons)
    return 1 if failures else 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
