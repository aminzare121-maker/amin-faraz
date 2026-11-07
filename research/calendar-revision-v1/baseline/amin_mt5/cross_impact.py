"""Advisory direct cross-impact arithmetic, never an inferred price model.

Source: DOI 10.22034/mr.2023.15266.5462, sections 3-4, 3-5, 4.
The caller supplies expert ratings and their evidence. This module does not
authenticate experts, invent missing cells, reproduce MICMAC, or estimate odds.
"""
from copy import deepcopy
import hashlib
import json
from urllib.parse import urlparse

SOURCE_URL = 'https://nashr.majles.ir/article_10322.html'


def analyze(payload=None):
    """Accept {labels, matrix, provenance:{source_url, assessed_on, assessor}}.

    Scores are ordinal integers 0..3 or 'P' (potential, not numeric four).
    Diagonal must be zero. P contributes no known direct score, and leaves
    affected row/column totals incomplete. No automatic quadrant threshold.
    """
    base = {'method': 'direct-cross-impact-v1', 'source_url': SOURCE_URL,
            'source_sections': ['3-4', '3-5', '4'], 'can_execute': False,
            'calibrated_accuracy_percent': None, 'probability': None,
            'full_micmac_implemented': False, 'caller_provenance_independently_verified': False,
            'note_fa': 'جمع امتیازهای کارشناسی، احتمال یا اثر علّی اثبات‌شده نیست؛ ماتریس بازار از خبرها ساخته نمی‌شود.'}
    def refuse(reason):
        return {**base, 'status': 'missing-required-inputs' if payload is None else 'invalid-input',
                'reason': reason, 'rows': [], 'complete': False}
    if not isinstance(payload, dict):
        return refuse('provenance-backed-expert-matrix-required')
    labels, matrix, provenance = (payload.get(k) for k in ('labels', 'matrix', 'provenance'))
    if not isinstance(labels, list) or not 2 <= len(labels) <= 100 or any(
            not isinstance(s, str) or not s.strip() or len(s) > 200 for s in labels) or len(set(labels)) != len(labels):
        return refuse('unique-nonempty-labels-required')
    if not isinstance(provenance, dict) or any(not isinstance(provenance.get(k), str) or not provenance[k].strip()
            for k in ('source_url', 'assessed_on', 'assessor')):
        return refuse('source-date-and-assessor-required')
    try:
        parsed = urlparse(provenance['source_url'])
    except ValueError:
        return refuse('public-https-provenance-required')
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        return refuse('public-https-provenance-required')
    n = len(labels)
    if not isinstance(matrix, list) or len(matrix) != n or any(not isinstance(r, list) or len(r) != n for r in matrix):
        return refuse('complete-square-matrix-required')
    for i, row in enumerate(matrix):
        for j, score in enumerate(row):
            if not (type(score) is int and 0 <= score <= 3 or score == 'P'):
                return refuse('ratings-must-be-integers-zero-through-three-or-P')
            if i == j and (type(score) is not int or score != 0):
                return refuse('zero-diagonal-required')
    rows = []
    for i, label in enumerate(labels):
        outgoing, incoming = matrix[i], [r[i] for r in matrix]
        out_p, in_p = outgoing.count('P'), incoming.count('P')
        influence = sum(x for x in outgoing if type(x) is int)
        dependence = sum(x for x in incoming if type(x) is int)
        rows.append({'label': label, 'known_direct_influence': influence,
                     'known_direct_dependence': dependence,
                     'direct_influence': None if out_p else influence,
                     'direct_dependence': None if in_p else dependence,
                     'potential_outgoing_count': out_p, 'potential_incoming_count': in_p,
                     'quadrant': None})
    digest = hashlib.sha256(json.dumps({'labels': labels, 'matrix': matrix, 'provenance': provenance},
        sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    complete = all('P' not in r for r in matrix)
    return {**base, 'status': 'computed' if complete else 'potential-ratings-unresolved',
            'complete': complete, 'rows': rows, 'provenance': deepcopy(provenance),
            'input_sha256': digest, 'quadrant_thresholds': None,
            'classification_status': 'explicit-thresholds-and-domain-validation-required',
            'indirect_effects': None, 'potential_numeric_substitution': None}
