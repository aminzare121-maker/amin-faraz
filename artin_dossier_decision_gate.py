"""Private 13-route dossier -> Artin decision boundary, fail-closed.

Candidate ASR and nearby visual metadata do not certify teacher decisions.
No private content is logged or sent to a broker.
"""
from __future__ import annotations
from collections.abc import Mapping
from artin_13_teacher_acceptance_matrix import EXPECTED_ROUTES


def inspect_dossier(dossier: Mapping) -> dict:
    """Validate citation coverage; return a non-executable decision."""
    blocked = {'decision': 'BLOCKED', 'executable': False,
               'trade_authorized': False, 'approved_rule_outcomes': []}
    if not isinstance(dossier, Mapping):
        return {**blocked, 'reason': 'INVALID_PRIVATE_DOSSIER'}
    routes = dossier.get('routes')
    if not isinstance(routes, list) or len(routes) != len(EXPECTED_ROUTES):
        return {**blocked, 'reason': 'INCOMPLETE_PRIVATE_DOSSIER'}
    ids = [r.get('route_id') if isinstance(r, Mapping) else None for r in routes]
    # Untrusted dossier fields must fail closed, not raise TypeError on lists/dicts.
    if any(not isinstance(i, str) for i in ids):
        return {**blocked, 'reason': 'INVALID_PRIVATE_ROUTE_SET'}
    if len(set(ids)) != len(ids) or set(ids) != EXPECTED_ROUTES:
        return {**blocked, 'reason': 'INVALID_PRIVATE_ROUTE_SET'}
    seen = set()
    for route in routes:
        intervals = route.get('citation_intervals')
        # The private source-session index must agree with cited intervals.
        # A mismatched index cannot be used to locate an original AV replay.
        declared_sessions = route.get('source_sessions')
        if declared_sessions is not None:
            if (not isinstance(declared_sessions, list) or
                any(type(x) is not int or not 1 <= x <= 25 for x in declared_sessions) or
                len(set(declared_sessions)) != len(declared_sessions)):
                return {**blocked, 'reason': 'INVALID_SOURCE_SESSION_INDEX'}
        if not isinstance(intervals, list) or not intervals:
            return {**blocked, 'reason': 'MISSING_SOURCE_INTERVALS'}
        # Validate interval objects and scalar session IDs before set operations:
        # malformed private evidence must be rejected, never crash the motor.
        if any(not isinstance(x, Mapping) for x in intervals):
            return {**blocked, 'reason': 'INVALID_SOURCE_INTERVAL'}
        if any(type(x.get('session')) is not int for x in intervals):
            return {**blocked, 'reason': 'INVALID_SOURCE_INTERVAL'}
        if declared_sessions is not None and set(declared_sessions) != {x['session'] for x in intervals}:
            return {**blocked, 'reason': 'SOURCE_SESSION_INDEX_MISMATCH'}
        for interval in intervals:
            if not isinstance(interval, Mapping):
                return {**blocked, 'reason': 'INVALID_SOURCE_INTERVAL'}
            idx, session = interval.get('index'), interval.get('session')
            start, end = interval.get('start'), interval.get('end')
            if (type(idx) is not int or type(session) is not int or
                not 1 <= session <= 25 or idx in seen or idx not in range(1, 25) or
                type(start) not in (int, float) or type(end) not in (int, float) or
                not 0 <= start < end < float('inf')):
                return {**blocked, 'reason': 'INVALID_SOURCE_INTERVAL'}
            seen.add(idx)
    if seen != set(range(1, 25)) or dossier.get('citations') != 24:
        return {**blocked, 'reason': 'INCOMPLETE_CITATION_COVERAGE'}
    # Source identity only: never pass candidate words or chart interpretation to entry predicates.
    # This per-route mapping permits auditing the exact dossier coverage at the engine boundary.
    route_sources = {r['route_id']: {'citation_indexes': sorted(x['index'] for x in r['citation_intervals']),
                                   'source_sessions': sorted({x['session'] for x in r['citation_intervals']})}
                     for r in routes}
    # Caller-provided approval flags cannot replace original AV review.
    return {**blocked, 'reason': 'ORIGINAL_TEACHER_AV_REPLAY_NOT_CERTIFIED',
            'candidate_routes': len(routes), 'source_intervals': len(seen),
            'route_source_identity': route_sources}
