"""Source-linked competing-scenario workflow, an engineering interpretation.

This module does not reproduce a proprietary book method and does not forecast
gold from political headlines. It executes explicit conditions over comparable
observations, keeps alternatives, and reports what changed since the last run.
"""
from datetime import datetime, timezone
import math
import re

from .sources import SOURCES
from .cross_impact import analyze as cross_impact_analysis
from .scenario_grid import analyze as scenario_grid_analysis

METHOD_VERSION = 'source-linked-scenarios-v2'
_ACTORS = {
    'fed-news': 'بانک مرکزی آمریکا', 'bls-news': 'ادارهٔ آمار کار آمریکا',
    'bls-calendar': 'ادارهٔ آمار کار آمریکا', 'us-10y': 'بازار اوراق خزانهٔ آمریکا',
    'oil-wti': 'بازار نفت WTI', 'world-growth': 'اقتصاد کشورها؛ سری بانک جهانی',
    'natural-events': 'نهادهای گزارش رخدادهای طبیعی',
    'world-risk-news': 'بازیگران خبرهای جهانی؛ هویت و کنش نیازمند تأیید مستقل',
}
_METHOD_SOURCES = [
    {'id': 'motaharnia-ai-first-2017', 'section': 'P4: collection, monitoring/classification, tracing, processing; engineering mapping only',
     'used_by': 'sources.collect/raw archive; research_context.public_context; analyze drivers/scenarios/revisions'},
    {'id': 'motaharnia-hormuz-grid-2026', 'section': 'full essay: direct conflict and energy resilience axes; four conditional futures',
     'used_by': 'scenario_grid.analyze'},
    {'id': 'motaharnia-art-crossimpact-2025', 'section': 'sections3-4,3-5,4: direct cross-impact; note18: MASL',
     'used_by': 'cross_impact.analyze/_domain_scan'},
    {'id': 'motaharnia-world-order-2017', 'section': 'pp853–854 research hypotheses/methodology; p858 leading indicators',
     'used_by': 'analyze:exploration/indicator_support'},
    {'id': 'motaharnia-glassy-2017', 'section': 'pp2088–2090 STEEPV; p2091 selection of scenario logics',
     'used_by': '_domain_scan/analyze:exploration'},
    {'id': 'motaharnia-syria-2017', 'section': 'سناریو آیندهٔ نگاه و رویکرد ترامپ؛ سه سناریوی رقیب',
     'used_by': '_scenarios'},
    {'id': 'motaharnia-iran-us-2018', 'section': 'بند پایانی پیش از واژگان کلیدی؛ بازنگری روندها و عدم قطعیت‌ها',
     'used_by': 'analyze:revision_triggers/transitions'},
    {'id': 'motaharnia-discourse-2025', 'section': 'صفحات ۲–۴: مفاهیم و روش تحلیل گفتمان؛ صفحات ۹–۱۰: نتیجه و اظهارات',
     'used_by': '_driver/analyze:uncertainties'},
]

_DOMAINS = {
    'social': ('اجتماعی', ('bls-news',)),
    'technological': ('فناوری', ()),
    'economic': ('اقتصادی', ('us-10y', 'oil-wti', 'fed-news', 'bls-news', 'world-growth')),
    'environmental': ('محیط زیست', ('natural-events',)),
    'political': ('سیاسی', ('fed-news', 'world-risk-news')),
    'values': ('ارزشی و فرهنگی', ()),
    'media': ('رسانه', ()), 'army': ('نیروی نظامی', ()),
    'security': ('امنیت', ()), 'law': ('حقوقی', ()),
}


def _domain_scan(sources, drivers):
    """Engineering coverage map, never infer domain facts from headlines."""
    rows = []
    for identity, (title, allowed) in _DOMAINS.items():
        observed = sorted(set(allowed).intersection(sources))
        comparable = [d['id'] for d in drivers if d['source_id'] in observed and d['state'] != 'unknown']
        rows.append({'id': identity, 'title': title, 'observed_source_ids': observed,
                     'comparable_driver_ids': comparable,
                     'status': 'comparable-observation' if comparable else 'source-only' if observed else 'missing',
                     'coverage_complete': False})
    return rows


def _logic_assessments(drivers):
    """Expose executable trend logic and exact gaps in other logics."""
    comparable = [d for d in drivers if d['state'] != 'unknown']
    rows = []
    missing = {
        'winners-losers': ['actor-specific outcome measure', 'actor goal and baseline', 'verified attribution of outcome'],
        'challenge-response': ['timestamped challenge event', 'same-actor timestamped response', 'independent event confirmation'],
        'revolution': ['defined regime or structure variable', 'predeclared change threshold', 'verified before/after observations'],
        'cycles': ['regularly spaced long time series', 'predeclared cycle period', 'out-of-sample recurrence test'],
    }
    for logic, required in missing.items():
        rows.append({'logic': logic, 'status': 'missing-required-inputs', 'required_inputs': required,
                     'assessment': None, 'engineering_interpretation': True,
                     'source_id': 'motaharnia-glassy-2017', 'section': 'p2091',
                     'revision_trigger': 'REQUIRED_INPUTS_BECOME_VERIFIED'})
    rows.append({'logic': 'evolution', 'status': 'assessed-observation-pattern' if comparable else 'missing-required-inputs',
                 'required_inputs': ['comparable period/unit observations'],
                 'assessment': {'changed_driver_ids': [d['id'] for d in comparable if d['state'] != 'stable'],
                                'stable_driver_ids': [d['id'] for d in comparable if d['state'] == 'stable'],
                                'causal_or_regime_inference': False} if comparable else None,
                 'engineering_interpretation': True, 'source_id': 'motaharnia-glassy-2017',
                 'section': 'p2091', 'revision_trigger': 'COMPARABLE_OBSERVATION_CHANGED'})
    return rows


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _period(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?', value):
        return None
    try:
        return datetime.strptime(value, {4: '%Y', 7: '%Y-%m', 10: '%Y-%m-%d'}[len(value)]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fresh_source(row, now_ms, known):
    if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row.get('id') not in known:
        return False
    stamp = row.get('checked_ms')
    return (row.get('status') == 'available' and row.get('source_url') == known[row['id']].url
            and type(stamp) is int and 0 <= now_ms - stamp <= 180000)


def _driver(raw, source, now_ms):
    """Compare only same-unit, causal periods; absence never becomes zero."""
    item = {'id': raw.get('id'), 'source_id': source['id'], 'source_url': source['source_url'],
            'actor': _ACTORS.get(source['id'], 'ناشر منبع پژوهشی'),
            'title': str(raw.get('title', source['id']))[:160], 'state': 'unknown',
            'value': raw.get('value') if _number(raw.get('value')) else None,
            'previous_value': None, 'period': raw.get('period'),
            'unit': str(raw.get('unit', 'نامعلوم'))[:60], 'observed_ms': source['checked_ms'],
            'frequency': raw.get('frequency'),
            'horizon': 'long_term' if raw.get('frequency') in ('annual', 'monthly') else 'short_term',
            'gaps': []}
    period = _period(raw.get('period'))
    prior_period = _period(raw.get('previous_period'))
    if period is None or period.timestamp() * 1000 > now_ms:
        item['gaps'].append('PERIOD_MISSING_OR_FUTURE')
    if raw.get('previous_unit', raw.get('unit')) != raw.get('unit') or not raw.get('unit'):
        item['gaps'].append('UNITS_NOT_COMPARABLE')
    if raw.get('frequency') not in ('daily', 'monthly', 'annual'):
        item['gaps'].append('FREQUENCY_UNSPECIFIED')
    elif any(len(str(raw.get(key))) != {'daily': 10, 'monthly': 7, 'annual': 4}[raw['frequency']]
             for key in ('period', 'previous_period')):
        item['gaps'].append('PERIOD_FREQUENCY_MISMATCH')
    if item['value'] is None or not _number(raw.get('previous_value')):
        item['gaps'].append('COMPARABLE_PREVIOUS_OBSERVATION_MISSING')
    if period and (prior_period is None or prior_period >= period):
        item['gaps'].append('PERIODS_NOT_FORWARD_ORDERED')
    observed = raw.get('observed_ms', source['checked_ms'])
    if type(observed) is not int or not 0 <= now_ms - observed <= 180000:
        item['gaps'].append('OBSERVATION_STALE_OR_FUTURE')
    published = raw.get('published_ms')
    # Unknown publication time remains explicit even when comparing public levels.
    item['publication_time_verified'] = (type(published) is int and type(observed) is int
                                         and 0 <= published <= observed <= now_ms)
    if type(published) is int and (published > now_ms or type(observed) is int and published > observed):
        item['gaps'].append('PUBLICATION_IN_FUTURE')
    if not item['publication_time_verified']:
        item['gaps'].append('PUBLICATION_TIME_UNVERIFIED')
    if period:
        age_days = (datetime.fromtimestamp(now_ms / 1000, timezone.utc) - period).days
        maximum = {'daily': 7, 'monthly': 93, 'annual': 3 * 366}.get(raw.get('frequency'), 0)
        if age_days > maximum:
            item['gaps'].append('OBSERVATION_PERIOD_TOO_OLD')
    blocking = [g for g in item['gaps'] if g != 'PUBLICATION_TIME_UNVERIFIED']
    if not blocking:
        item['previous_value'] = raw['previous_value']
        item['previous_period'] = raw['previous_period']
        delta = item['value'] - item['previous_value']
        if math.isfinite(delta):
            item['state'] = 'rising' if delta > 0 else 'falling' if delta < 0 else 'stable'
            item['delta'] = delta
        else:
            item['gaps'].append('NONFINITE_CHANGE')
    return item


def _scenarios(drivers, horizon):
    # Counts classify input evidence, not its causal effect on a traded asset.
    scoped = [d for d in drivers if d['horizon'] == horizon]
    known = [d for d in scoped if d['state'] != 'unknown']
    # Repeated metrics from one source must not masquerade as independent sources.
    distinct = len({d['source_id'] for d in known})
    up = [d['id'] for d in known if d['state'] == 'rising']
    down = [d['id'] for d in known if d['state'] == 'falling']
    flat = [d['id'] for d in known if d['state'] == 'stable']
    active = ('insufficient' if distinct < 2 else 'mixed' if up and down else
              'rising' if up else 'falling' if down else 'stable')
    names = {'insufficient': 'شاهد مقایسه‌پذیر کافی نیست', 'mixed': 'پیشران‌ها ناهم‌جهت‌اند',
             'rising': 'سطح پیشران‌های مشاهده‌شده افزایشی است',
             'falling': 'سطح پیشران‌های مشاهده‌شده کاهشی است', 'stable': 'سطح پیشران‌ها تغییر نکرده است'}
    conditions = {
        'insufficient': 'کمتر از دو منبع مستقل با مشاهدهٔ قابل‌مقایسه',
        'mixed': 'حداقل دو منبع مستقل؛ وجود افزایش و کاهش هم‌زمان در پیشران‌ها',
        'rising': 'حداقل دو منبع مستقل؛ دست‌کم یک افزایش و نبود کاهش',
        'falling': 'حداقل دو منبع مستقل؛ دست‌کم یک کاهش و نبود افزایش',
        'stable': 'حداقل دو منبع مستقل؛ تمام مشاهدات قابل‌مقایسه بدون تغییر',
    }
    return ([{'id': horizon + ':' + key, 'title': title, 'horizon': horizon,
              'active': key == active, 'condition': conditions[key],
              'supporting_driver_ids': up + down + flat if key == active else [],
              'method_source_ids': ['motaharnia-syria-2017'],
              'asset_direction': 'unknown', 'probability': None}
             for key, title in names.items()], horizon + ':' + active)


def analyze(evidence, now_ms, previous=None):
    """Execute registers, alternatives and revision triggers over public evidence.

    ``driver_observations`` may supply period/unit/value/previous_value comparisons.
    Otherwise source.latest is used and compared with a previous framework only
    when its observation period advances. Titles are never parsed as price signals.
    """
    if type(now_ms) is not int or not 0 <= now_ms <= 253402300799999:
        raise ValueError('A nonnegative integer observation time is required')
    evidence = evidence if isinstance(evidence, dict) else {}
    previous = previous if isinstance(previous, dict) else {}
    known = {s.id: s for s in SOURCES}
    sources = {}
    uncertainties = []
    if previous and (type(previous.get('generated_ms')) is not int or previous['generated_ms'] > now_ms):
        previous = {}
        uncertainties.append({'code': 'PREVIOUS_FRAMEWORK_TIME_UNVERIFIED'})
    raw_sources = evidence.get('public_sources', [])
    for row in raw_sources[:20] if isinstance(raw_sources, list) else []:
        if _fresh_source(row, now_ms, known):
            if row['id'] in sources:
                uncertainties.append({'code': 'DUPLICATE_SOURCE', 'source_id': row['id']})
                continue
            sources[row['id']] = row
        elif isinstance(row, dict):
            uncertainties.append({'code': 'SOURCE_UNAVAILABLE_OR_STALE', 'source_id': str(row.get('id', ''))[:80]})
    old_rows = previous.get('drivers', [])
    old = {d['id']: d for d in old_rows if isinstance(d, dict) and isinstance(d.get('id'), str)} if isinstance(old_rows, list) else {}
    raw_observations = evidence.get('driver_observations', [])
    raw_observations = raw_observations[:30] if isinstance(raw_observations, list) else []
    observations = [dict(r) for r in raw_observations if isinstance(r, dict)]
    explicit_sources = {r.get('source_id') for r in observations if isinstance(r.get('source_id'), str)}
    for source_id, row in sources.items():
        latest = row.get('latest')
        if source_id in explicit_sources or not isinstance(latest, dict):
            continue
        raw = {'id': source_id, 'source_id': source_id, 'value': latest.get('value'),
               'unit': latest.get('unit'), 'period': latest.get('observation_date'),
               'frequency': row.get('frequency')}
        prior = old.get(source_id, {})
        if prior.get('source_id') == source_id:
            if prior.get('period') == raw['period'] and prior.get('frequency') == raw['frequency']:
                # Same-period polling/revision retains the earlier comparison
                # period, rather than inventing a trend between two same-day values.
                raw.update(previous_value=prior.get('previous_value'), previous_period=prior.get('previous_period'),
                           previous_unit=prior.get('unit'))
            else:
                raw.update(previous_value=prior.get('value'), previous_period=prior.get('period'), previous_unit=prior.get('unit'))
        observations.append(raw)
    drivers = []
    seen = set()
    for raw in observations:
        identity = raw.get('id')
        if not isinstance(identity, str) or not identity or len(identity) > 80 or identity in seen:
            uncertainties.append({'code': 'DRIVER_ID_INVALID_OR_DUPLICATE'})
            continue
        seen.add(identity)
        source = sources.get(raw.get('source_id')) if isinstance(raw.get('source_id'), str) else None
        if source is None:
            uncertainties.append({'code': 'DRIVER_SOURCE_NOT_VERIFIED', 'driver_id': identity})
            continue
        driver = _driver(raw, source, now_ms)
        drivers.append(driver)
        uncertainties.extend({'code': gap, 'driver_id': identity} for gap in driver['gaps'])
    # A headline establishes that a publisher has a headline, not that its claim is true.
    for source_id, row in sources.items():
        if row.get('records'):
            uncertainties.append({'code': 'HEADLINES_NOT_VERIFIED_OUTCOMES', 'source_id': source_id})
    scenarios = []
    active = {}
    for horizon in ('short_term', 'long_term'):
        items, selected = _scenarios(drivers, horizon)
        scenarios.extend(items)
        active[horizon] = selected
    changes = []
    for driver in drivers:
        prior = old.get(driver['id'])
        if prior and any(driver.get(k) != prior.get(k) for k in ('value', 'period', 'state')):
            changes.append({'driver_id': driver['id'], 'before': prior.get('state'),
                            'after': driver['state'], 'trigger': 'OBSERVATION_CHANGED'})
    previous_active = previous.get('active_scenarios', {})
    previous_active = previous_active if isinstance(previous_active, dict) else {}
    transitions = [{'horizon': h, 'from': previous_active.get(h), 'to': current,
                    'trigger': 'EVIDENCE_OR_COVERAGE_CHANGED'}
                   for h, current in active.items() if previous_active.get(h) != current]
    summary = ('چارچوب سناریو با ' + str(len(sources)) + ' منبع تازه و ' + str(len(drivers)) +
               ' پیشران اجرا شد. کوتاه‌مدت: ' + next(s['title'] for s in scenarios if s['id'] == active['short_term']) +
               '؛ بلندمدت: ' + next(s['title'] for s in scenarios if s['id'] == active['long_term']) +
               '. این طبقه‌بندی، جهت طلا یا درصد دقت نیست؛ فرضیهٔ اثر بر قیمت باید جدا سنجیده شود.')
    return {'method_version': METHOD_VERSION, 'generated_ms': now_ms,
            'attribution': {'engineering_interpretation': True, 'complete_author_method': False,
                            'sources': [dict(row) for row in _METHOD_SOURCES]},
            'actors': [{'source_id': k, 'name': _ACTORS.get(k, 'ناشر پژوهش'),
                        'source_url': v['source_url'], 'observed_ms': v['checked_ms']} for k, v in sources.items()],
            'drivers': drivers, 'uncertainties': uncertainties, 'scenarios': scenarios,
            'domain_scan': _domain_scan(sources, drivers),
            'cross_impact': cross_impact_analysis(evidence.get('cross_impact')),
            'hormuz_exploration': scenario_grid_analysis(evidence.get('hormuz_exploration'), now_ms),
            'indicator_support': {
                horizon: {**{state: sum(d['state'] == state for d in drivers if d['horizon'] == horizon)
                              for state in ('rising', 'falling', 'stable', 'unknown')},
                          'total': sum(d['horizon'] == horizon for d in drivers), 'probability': None}
                for horizon in ('short_term', 'long_term')},
            'exploration': {'mode': 'exploratory', 'preference_affects_active_scenario': False,
                            'scenario_logics': ['winners-losers', 'challenge-response', 'evolution', 'revolution', 'cycles'],
                            'logic_assessments': _logic_assessments(drivers),
                            'logic_selected_automatically': False,
                            'note': 'منطق سناریو و آیندهٔ مطلوب، به‌تنهایی شاهد وقوع یا احتمال نیستند.'},
            'active_scenario': active['short_term'], 'active_scenarios': active,
            'transitions': transitions, 'revision_triggers': changes,
            'revision_conditions': ['انتشار مشاهدهٔ تازه یا اصلاح‌شده', 'کهنه‌شدن یا قطع منبع',
                                    'تعارض جهت پیشران‌های قابل‌مقایسه'],
            'summary_fa': summary, 'asset_direction': 'unknown', 'calibrated_accuracy_percent': None,
            'can_execute': False}
