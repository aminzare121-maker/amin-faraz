"""Offline preflight for Faraz gap manifest. No market access, no trades."""
import csv
from datetime import datetime, timedelta
from pathlib import Path

def validate(path):
    errors=[]; seen=set(); intervals=[]
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        required={'gap_id','first_missing_candle_open_raw_label','missing_m15_count'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            return ['missing required columns']
        for line,row in enumerate(reader,2):
            try:
                gid=int(row['gap_id']); n=int(row['missing_m15_count'])
                t=datetime.fromisoformat(row['first_missing_candle_open_raw_label'])
                if t.tzinfo is not None or t.second or t.microsecond or t.minute%15 or n<=0 or n>40000 or gid<=0:
                    raise ValueError('invalid count/id/time alignment')
                if gid in seen: errors.append(f'line {line}: duplicate gap_id')
                seen.add(gid)
                intervals.append((t,t+timedelta(minutes=15*n),line))
            except (ValueError,TypeError,OverflowError,KeyError):
                errors.append(f'line {line}: invalid gap record')
    for a,b in zip(sorted(intervals),sorted(intervals)[1:]):
        if b[0]<a[1]:errors.append(f'line {b[2]}: overlapping gap interval')
    return errors
