"""Explicit two-axis Hormuz exploration, sourced to a public author essay.

Axes are analyst-supplied assessments, never inferred from headlines or prices.
"""
from copy import deepcopy
from urllib.parse import urlparse

SOURCE_URL = 'https://cimorg.org/تنگه-هرمز-در-چارچوب-هارتلند-و-ریملند/'
AXES = ('direct_gulf_conflict', 'energy_market_resilience')
SCENARIOS = (
    ('knife-edge', 'تعادل لبه تیغ', 'low', 'low'),
    ('closure-reopening', 'شوک انسداد و بازگشایی قهری', 'high', 'low'),
    ('beyond-hormuz', 'عبور از هرمز یا بی‌اثر شدن گلوگاه', 'low', 'high'),
    ('rival-orders', 'دوپارگی پرهزینه و نظم‌های رقیب', 'high', 'high'),
)


def _public_reference(url):
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme == 'https' and bool(parsed.netloc) and not parsed.username and not parsed.password
    except ValueError:
        return False


def analyze(payload=None, now_ms=None):
    """Accept {'axes': {axis: {'state':'low'|'high'|'unknown',
    'evidence_refs':[public HTTPS URLs], 'assessed_ms':int, 'rationale':str}}}.

    References/date/rationale establish traceability, not independent verification.
    Freshness and independence require domain-specific validation by caller.
    """
    assessments, gaps = {}, []
    axes = payload.get('axes', {}) if isinstance(payload, dict) else {}
    if not isinstance(axes, dict):
        axes = {}
    for axis in AXES:
        item = axes.get(axis)
        valid = isinstance(item, dict) and item.get('state') in ('low', 'high', 'unknown')
        if valid and item['state'] != 'unknown':
            refs = item.get('evidence_refs')
            valid = isinstance(refs, list) and 0 < len(refs) <= 20 and all(
                _public_reference(url) for url in refs)
            assessed = item.get('assessed_ms')
            valid = valid and type(assessed) is int and assessed > 0
            valid = valid and isinstance(item.get('rationale'), str) and bool(item['rationale'].strip())
            if now_ms is not None:
                valid = valid and type(now_ms) is int and assessed <= now_ms
        if not valid or item['state'] == 'unknown':
            assessments[axis] = {'state': 'unknown', 'assessment_validated': False}
            gaps.append(axis)
        else:
            assessments[axis] = {**deepcopy(item), 'assessment_validated': False,
                                 'traceability_fields_valid': True}
    rows = []
    for identity, title, conflict, resilience in SCENARIOS:
        conditions = dict(zip(AXES, (conflict, resilience)))
        incompatible = any(assessments[a]['state'] not in ('unknown', v) for a, v in conditions.items())
        rows.append({'id': identity, 'title': title, 'conditions': conditions,
                     'compatible': not incompatible,
                     'active_under_supplied_assessments': not gaps and not incompatible,
                     'probability': None, 'source_url': SOURCE_URL})
    return {'method': 'hormuz-two-axis-exploration-v1', 'source_url': SOURCE_URL,
            'status': 'missing-required-inputs' if gaps else 'conditional-on-supplied-assessments',
            'axes': assessments, 'missing_axes': gaps, 'scenarios': rows,
            'active_scenario_id': next((r['id'] for r in rows if r['active_under_supplied_assessments']), None),
            'revision_triggers': [{'axis': a, 'condition': 'assessment-or-supporting-evidence-changes'} for a in AXES],
            'early_warning_status': 'source-proposes-future-indicator-definition-no-validated-thresholds',
            'early_warning_indicators': [], 'independence_verified': False,
            'asset_direction': 'unknown', 'can_execute': False, 'probability': None,
            'note_fa': 'چهار سناریوی شرطی مقاله؛ استقلال محورها، شواهد تازه و آستانهٔ هشدار هنوز باید مستقل سنجیده شوند.'}
