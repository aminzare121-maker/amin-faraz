"""Prospective XAUUSD forecast registry. No broker calls and no order capability.

Only a locally verified forward registry can supply deployment evidence. Imported
replays are useful tests, never a substitute for predictions recorded in advance.
"""
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from .model import dec

HORIZONS = (7_200_000, 14_400_000, 604_800_000)
MAX_QUOTE_AGE_MS = 2_000
TARGET_TOLERANCE_MS = 60_000
MIN_INDEPENDENT = 200
MIN_PER_SIDE = 30
MIN_ACCURACY_LOWER_95 = .80
CALIBRATION_WINDOW_MS = 90*86_400_000
_REGISTRY_PROVENANCE = object()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('Nonnegative integer timestamp required')
    return value


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _forecast(forecast, now_ms, simulation):
    _integer(now_ms)
    if not isinstance(forecast, dict):
        raise ValueError('Forecast object required')
    required = {'id', 'generated_ms', 'target_ms', 'entry_price', 'entry_observed_ms', 'direction',
                'uncertainty', 'baseline_direction', 'policy_sha256', 'source_ids', 'evidence_sha256'}
    if not required <= set(forecast) <= required | {'symbol', 'report_generated_ms', 'entry_cost_fraction'}:
        raise ValueError('Unexpected forecast fields')
    row = dict(forecast, symbol=forecast.get('symbol', 'XAUUSD'))
    if row['symbol'] != 'XAUUSD' or not isinstance(row['id'], str) or not 1 <= len(row['id']) <= 160:
        raise ValueError('Invalid forecast identity')
    generated = _integer(row['generated_ms'])
    target = _integer(row['target_ms'])
    observed = _integer(row['entry_observed_ms'])
    if not 0 <= now_ms - generated <= 10_000:
        raise ValueError('Forecast must be captured immediately before outcome')
    if target - generated not in HORIZONS or target <= now_ms:
        raise ValueError('Frozen future horizon required')
    if not 0 <= generated - observed <= MAX_QUOTE_AGE_MS:
        raise ValueError('Fresh causal entry quote required')
    if 'report_generated_ms' in row and not 0 <= generated-_integer(row['report_generated_ms']) <= 180_000:
        raise ValueError('Research report must be fresh at capture')
    if row['direction'] not in ('buy', 'sell', 'neutral') or row['baseline_direction'] not in ('buy', 'sell'):
        raise ValueError('Invalid direction')
    if row['uncertainty'] not in ('low', 'medium', 'high'):
        raise ValueError('Explicit uncertainty required')
    if not _hash(row['policy_sha256']) or not _hash(row['evidence_sha256']):
        raise ValueError('Frozen policy and evidence digests required')
    sources = row['source_ids']
    if not isinstance(sources, list) or not 2 <= len(sources) <= 20 or any(not isinstance(s, str) or not 1 <= len(s) <= 80 for s in sources) or len(set(sources)) != len(sources):
        raise ValueError('Distinct source identities required')
    if type(simulation) is not bool or dec(row['entry_price']) <= 0:
        raise ValueError('Invalid entry price or capture mode')
    if 'entry_cost_fraction' in row:
        if not 0 <= dec(row['entry_cost_fraction']) <= dec('.1'):
            raise ValueError('Invalid frozen entry cost')
        row['entry_cost_fraction'] = str(dec(row['entry_cost_fraction']))
    row.update(entry_price=str(dec(row['entry_price'])), source_ids=sorted(sources),
               captured_ms=now_ms, simulation=simulation, horizon_ms=target-generated)
    return row


def _outcome(forecast, outcome, now_ms):
    _integer(now_ms)
    if not isinstance(outcome, dict) or set(outcome) != {'price', 'observed_ms', 'received_ms', 'cost_fraction', 'source'}:
        raise ValueError('Exact outcome fields required')
    observed = _integer(outcome['observed_ms'])
    received = _integer(outcome['received_ms'])
    if not forecast['target_ms'] <= observed <= forecast['target_ms'] + TARGET_TOLERANCE_MS:
        raise ValueError('Outcome quote outside frozen target window')
    if not observed <= received <= now_ms or received-observed > TARGET_TOLERANCE_MS or now_ms-received > TARGET_TOLERANCE_MS:
        raise ValueError('Outcome must be received causally without backfill')
    if dec(outcome['price']) <= 0 or not 0 <= dec(outcome['cost_fraction']) <= dec('.1'):
        raise ValueError('Invalid price or costs')
    if 'entry_cost_fraction' in forecast and dec(outcome['cost_fraction']) < dec(forecast['entry_cost_fraction']):
        raise ValueError('Outcome costs cannot erase frozen entry costs')
    if not isinstance(outcome['source'], str) or not 1 <= len(outcome['source']) <= 100:
        raise ValueError('Outcome source required')
    return dict(outcome, price=str(dec(outcome['price'])), cost_fraction=str(dec(outcome['cost_fraction'])), settled_ms=now_ms)


def wilson_lower(successes, count):
    if count == 0:
        return None
    z = 1.959963984540054
    p = successes/count
    return (p+z*z/(2*count)-z*math.sqrt(p*(1-p)/count+z*z/(4*count*count)))/(1+z*z/count)


def _lower_mean(values):
    if len(values) < 2:
        return None
    mean = sum(values)/len(values)
    variance = sum((v-mean)**2 for v in values)/(len(values)-1)
    return mean-1.959963984540054*math.sqrt(variance/len(values))


def evaluate_records(records, now_ms, policy_sha256, *, horizon_ms=14_400_000, provenance_verified=False, source_ids=None):
    """Chronological independent holdout metrics; a plain replay cannot authorize use.

    The uncertainty filter keeps low-uncertainty agreement with the price baseline.
    Overlapping target windows and reused evidence are excluded from independent
    counts, and malformed/future rows are rejected rather than silently dropped.
    """
    # True supplied by an imported JSON file or caller is not proof. Only the
    # verified registry's in-process capability is accepted by this evaluator.
    provenance_verified = provenance_verified is _REGISTRY_PROVENANCE
    _integer(now_ms)
    if not _hash(policy_sha256) or horizon_ms not in HORIZONS or not isinstance(records, list):
        raise ValueError('Invalid evaluation request')
    if source_ids is not None and (not isinstance(source_ids,list) or len(source_ids)>20 or
            any(not isinstance(s,str) or not 1<=len(s)<=80 for s in source_ids) or len(set(source_ids))!=len(source_ids)):
        raise ValueError('Invalid exact source cohort')
    cohort=sorted(source_ids) if source_ids is not None else None
    eligible = []
    pending = 0
    missed = 0
    aged_out = 0
    unverified_sources = 0
    legacy_costs = 0
    window_start = max(0, now_ms-CALIBRATION_WINDOW_MS)
    for item in records:
        forecast = item['forecast']
        if forecast['policy_sha256'] != policy_sha256 or forecast['horizon_ms'] != horizon_ms:
            continue
        # Re-validate stored inputs with their original capture clock.
        checked = _forecast({k:v for k,v in forecast.items() if k not in ('captured_ms', 'simulation', 'horizon_ms')},
                            forecast['captured_ms'], forecast['simulation'])
        if checked != forecast or forecast['captured_ms'] > now_ms:
            raise ValueError('Invalid or future forecast record')
        if cohort is not None and forecast['source_ids'] != cohort:
            continue
        outcome = item.get('outcome')
        if forecast['generated_ms'] < window_start:
            aged_out += 1
            continue
        if outcome is None:
            if now_ms > forecast['target_ms']+TARGET_TOLERANCE_MS:
                missed += 1
            else:
                pending += 1
            continue
        validated = _outcome(forecast, {k:v for k,v in outcome.items() if k != 'settled_ms'}, outcome['settled_ms'])
        if validated != outcome or outcome['settled_ms'] > now_ms:
            raise ValueError('Invalid or future outcome record')
        if forecast['simulation'] is False and outcome['source'] != 'broker-demo':
            unverified_sources += 1
            continue
        if forecast['simulation'] is False and 'entry_cost_fraction' not in forecast:
            legacy_costs += 1
            continue
        eligible.append(item)
    eligible.sort(key=lambda r:(r['forecast']['generated_ms'], r['forecast']['id']))
    independent = []
    seen_ids = set()
    seen_evidence = set()
    previous_target = -1
    for item in eligible:
        f = item['forecast']
        if f['id'] in seen_ids:
            raise ValueError('Duplicate forecast identity')
        seen_ids.add(f['id'])
        if f['generated_ms'] <= previous_target or f['evidence_sha256'] in seen_evidence:
            continue
        independent.append(item)
        previous_target = f['target_ms']
        seen_evidence.add(f['evidence_sha256'])
    directional = [r for r in independent if r['forecast']['direction'] in ('buy', 'sell')]
    successes = 0
    baseline = []
    filtered = []
    selected_returns = []
    counts = {'buy':0, 'sell':0}
    for item in independent:
        f, o = item['forecast'], item['outcome']
        change = float(dec(o['price'])/dec(f['entry_price'])-1)
        costs = float(dec(o['cost_fraction']))
        baseline_return = change*(1 if f['baseline_direction'] == 'buy' else -1)-costs
        selected = f['uncertainty'] == 'low' and f['direction'] == f['baseline_direction']
        filtered_return = baseline_return if selected else 0.0
        baseline.append(baseline_return)
        filtered.append(filtered_return)
        if selected:
            selected_returns.append(filtered_return)
        if f['direction'] in counts:
            counts[f['direction']] += 1
            prediction_return = change*(1 if f['direction'] == 'buy' else -1)-costs
            successes += prediction_return > 0
    n = len(independent)
    lower = wilson_lower(successes, len(directional))
    improvement = [a-b for a,b in zip(filtered, baseline)]
    improvement_lower = _lower_mean(improvement)
    selected_lower = _lower_mean(selected_returns)
    reasons = []
    source_sets=sorted({tuple(r['forecast']['source_ids']) for r in independent})
    evaluation_scope=cohort if cohort is not None else list(source_sets[0]) if len(source_sets)==1 else []
    if cohort is None and len(source_sets)>1:
        reasons.append('SOURCE_COHORT_NOT_SPECIFIED')
    if horizon_ms==604_800_000:
        reasons.append('LONG_HORIZON_REPORT_ONLY')
    if legacy_costs:
        reasons.append('LEGACY_ENTRY_COST_MISSING')
    if unverified_sources:
        reasons.append('SOURCE_NOT_VERIFIED')
    forward = bool(independent) and all(r['forecast']['simulation'] is False for r in independent)
    if not provenance_verified or not forward:
        reasons.append('FORWARD_CAPTURE_NOT_VERIFIED')
    if n < MIN_INDEPENDENT or any(counts[s] < MIN_PER_SIDE for s in counts):
        reasons.append('INSUFFICIENT_INDEPENDENT_FORECASTS')
    if lower is None or lower < MIN_ACCURACY_LOWER_95:
        reasons.append('ACCURACY_LOWER_BOUND_TOO_LOW')
    coverage = len(selected_returns)/n if n else None
    if coverage is None or not .1 <= coverage <= .9:
        reasons.append('FILTER_COVERAGE_NOT_ESTABLISHED')
    if selected_lower is None or selected_lower <= 0 or improvement_lower is None or improvement_lower <= 0:
        reasons.append('NET_BENEFIT_NOT_ESTABLISHED')
    latest = max((r['outcome']['settled_ms'] for r in independent), default=0)
    # A cached certificate must also expire when its oldest included sample
    # leaves the rolling window, rather than preserving that sample for a week.
    oldest = min((r['forecast']['generated_ms'] for r in independent), default=0)
    expires = min(latest+7*86_400_000, oldest+CALIBRATION_WINDOW_MS) if latest else 0
    if not latest or now_ms > expires:
        reasons.append('EVALUATION_STALE')
    payload = {'policy_sha256':policy_sha256, 'horizon_ms':horizon_ms,
               'records_sha256':digest(independent), 'independent_ids':[r['forecast']['id'] for r in independent],
               'evaluation_scope_source_ids':evaluation_scope}
    return {**payload, 'assessment_sha256':digest(payload), 'issued_ms':now_ms, 'expires_ms':expires,
            'source_ids':sorted({s for r in independent for s in r['forecast']['source_ids']}),
            'source_sets':[list(s) for s in source_sets],
            'sample_count':len(eligible), 'pending_count':pending, 'missed_count':missed,
            'aged_out_count':aged_out, 'unverified_source_count':unverified_sources,
            'legacy_entry_cost_missing_count':legacy_costs,
            'calibration_window_start_ms':window_start, 'calibration_window_days':90,
            'independent_sample_count':n,
            'directional_sample_count':len(directional), 'direction_counts':counts,
            'success_count':successes, 'accuracy':successes/len(directional) if directional else None,
            'accuracy_wilson_lower_95':lower, 'minimum_accuracy_lower_95_required':MIN_ACCURACY_LOWER_95, 'coverage':coverage,
            'baseline_mean_net_return':sum(baseline)/n if n else None,
            'filtered_mean_net_return':sum(filtered)/n if n else None,
            'selected_mean_net_return_lower_95':selected_lower,
            'improvement_mean_net_return_lower_95':improvement_lower,
            'forward_capture_verified':provenance_verified and forward,
            'deployment_eligible':not reasons, 'reasons':reasons,
            'claimed_accuracy_88_89_verified':False, 'can_execute':False}


class ForecastRegistry:
    """Write-once forecasts and outcomes with an append-only hash audit trail."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS forecasts(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outcomes(id TEXT PRIMARY KEY REFERENCES forecasts(id),payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY,kind TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,previous_hash TEXT NOT NULL,hash TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS forecast_no_update BEFORE UPDATE ON forecasts BEGIN SELECT RAISE(ABORT,'Forecast immutable'); END;
                CREATE TRIGGER IF NOT EXISTS forecast_no_delete BEFORE DELETE ON forecasts BEGIN SELECT RAISE(ABORT,'Forecast immutable'); END;
                CREATE TRIGGER IF NOT EXISTS outcome_no_update BEFORE UPDATE ON outcomes BEGIN SELECT RAISE(ABORT,'Outcome immutable'); END;
                CREATE TRIGGER IF NOT EXISTS outcome_no_delete BEFORE DELETE ON outcomes BEGIN SELECT RAISE(ABORT,'Outcome immutable'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'Audit immutable'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'Audit immutable'); END;
            ''')
        if not self.verify():
            raise ValueError('Forecast registry audit invalid')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _append(db, kind, identity, row):
        previous = db.execute('SELECT hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
        previous = previous[0] if previous else '0'*64
        payload = canonical(row)
        value = digest([kind, identity, payload, previous])
        db.execute('INSERT INTO audit(kind,id,payload,previous_hash,hash) VALUES(?,?,?,?,?)', (kind, identity, payload, previous, value))

    def register_forecast(self, forecast, now_ms, *, simulation=True):
        row = _forecast(forecast, now_ms, simulation)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO forecasts VALUES(?,?)', (row['id'], canonical(row)))
            self._append(db, 'forecast', row['id'], row)
        return row['id']

    def settle(self, forecast_id, outcome, now_ms):
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM forecasts WHERE id=?', (forecast_id,)).fetchone()
            if row is None:
                raise ValueError('Unknown forecast')
            result = _outcome(json.loads(row[0]), outcome, now_ms)
            db.execute('INSERT INTO outcomes VALUES(?,?)', (forecast_id, canonical(result)))
            self._append(db, 'outcome', forecast_id, result)
        return result

    def records(self):
        with self._connect() as db:
            return [{'forecast':json.loads(f), 'outcome':json.loads(o) if o else None}
                    for f,o in db.execute('SELECT f.payload,o.payload FROM forecasts f LEFT JOIN outcomes o ON f.id=o.id ORDER BY f.id')]

    def contains(self, forecast_id):
        with self._connect() as db:
            return db.execute('SELECT 1 FROM forecasts WHERE id=?', (forecast_id,)).fetchone() is not None

    def pending(self, now_ms):
        _integer(now_ms)
        return [r['forecast'] for r in self.records() if r['outcome'] is None and r['forecast']['target_ms'] <= now_ms <= r['forecast']['target_ms']+TARGET_TOLERANCE_MS]

    def verify(self):
        previous = '0'*64
        expected = 1
        forecasts, outcomes = {}, {}
        with self._connect() as db:
            for seq,kind,identity,payload,prior,value in db.execute('SELECT * FROM audit ORDER BY seq'):
                if seq != expected or prior != previous or value != digest([kind,identity,payload,previous]):
                    return False
                if kind == 'forecast' and identity not in forecasts:
                    forecasts[identity] = payload
                elif kind == 'outcome' and identity in forecasts and identity not in outcomes:
                    outcomes[identity] = payload
                else:
                    return False
                previous, expected = value, expected+1
            return forecasts == dict(db.execute('SELECT id,payload FROM forecasts')) and outcomes == dict(db.execute('SELECT id,payload FROM outcomes'))

    def summarize(self, policy_sha256, now_ms, horizon_ms=14_400_000, *, source_ids=None):
        if not self.verify():
            raise ValueError('Forecast registry audit invalid')
        return evaluate_records(self.records(), now_ms, policy_sha256, horizon_ms=horizon_ms,
                                provenance_verified=_REGISTRY_PROVENANCE,source_ids=source_ids)
