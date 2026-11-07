"""A fail-closed audit of Artin's raw decision trace.

This is NOT verification of the teacher's recordings. A lesson timestamp or a
Python unit test is not evidence that all student questions and teacher
corrections have been faithfully implemented. The gate only reports why the
current candidate CANNOT be promoted to a teacher-faithful paper trade.

The gate deliberately has no "approve" switch. Opening it requires a later,
independently reviewed media+dialogue+visual+positive/negative-case record and
explicitly tested implementation. It has no broker or network interface.
"""
import json
from collections import Counter
from pathlib import Path

from entry_engine import RULE_IDS, SOURCES

REQUIRED_TRACE_FIELDS = (
    'input_fingerprint', 'dependency_facts', 'missing_dependencies',
    'future_dependencies', 'context_required_keys', 'policy_required_keys',
    'derived_required_keys', 'sources',
)
SOURCE_ORIGINS = frozenset((
    'DERIVED_FROM_RAW', 'DERIVED_MIXED',
    'SOURCED_CONTEXT', 'DECLARED_RESEARCH_POLICY',
))


def audit_candidate(decision, at, classroom_index=None):
    """Describe a raw ELIGIBLE decision without ever authenticating teacher media."""
    rule = decision.get('rule_id')
    side = decision.get('side')
    base = {
        'signal_at': at,
        'side': side,
        'rule_id': rule,
        'state': 'REVIEW',
        'teacher_rule_verified': False,
        'teacher_media_independently_reviewed': False,
        'can_execute_as_teacher_method': False,
        'documented_lesson_ranges_not_verified': list(SOURCES.get(rule, ())),
        'missing_dependencies': decision.get('missing_dependencies', []),
        'context_required_keys': decision.get('context_required_keys', []),
        'policy_required_keys': decision.get('policy_required_keys', []),
    }
    def review(reason):
        return dict(base, reason=reason)

    if type(at) is not int or at < 0 or side not in ('BUY', 'SELL'):
        return review('INVALID_DECISION_IDENTITY')
    if rule not in RULE_IDS:
        return review('UNREGISTERED_RULE')
    if rule == 'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE':
        return review('EXPLICIT_RESEARCH_HYPOTHESIS_NOT_CONFIRMED_TEACHER_FORMULA')
    if classroom_index is not None:
        if classroom_index.get('schema') != 'artin_classroom_rule_index_v1' or not isinstance(classroom_index.get('rules'), dict):
            raise ValueError('Unsupported classroom dialogue review index')
        rule_review = classroom_index['rules'].get(rule)
        base['classroom_dialogue_review'] = rule_review
        if not isinstance(rule_review, dict):
            return review('RULE_NOT_IN_CLASSROOM_DIALOGUE_REVIEW_INDEX')
        if rule_review.get('rule_can_trade') is not False:
            raise ValueError('Classroom dialogue index cannot grant trade permission')
        if rule_review.get('reason') != 'FULL_TEACHER_EXAMPLES_AND_SEMANTICS_UNVERIFIED':
            return review('DIALOGUE_' + str(rule_review.get('reason','UNKNOWN')))
        # A complete-looking text index does NOT verify that classroom media,
        # question/answer semantics or real positive/negative cases were checked.
        base['classroom_index_is_not_teacher_verification'] = True
    if decision.get('status') != 'ELIGIBLE':
        return review('NOT_ELIGIBLE_RAW_DECISION')
    if any(name not in decision for name in REQUIRED_TRACE_FIELDS):
        return review('RAW_TRACE_PROVENANCE_FIELDS_MISSING')
    if not isinstance(decision['missing_dependencies'], list) or not isinstance(decision['future_dependencies'], list):
        return review('RAW_TRACE_INVALID_DEPENDENCY_INVENTORY')
    if decision['missing_dependencies']:
        return review('RAW_TRACE_HAS_MISSING_DEPENDENCIES')
    if decision['future_dependencies']:
        return review('RAW_TRACE_USES_FUTURE_DEPENDENCIES')
    facts = decision['dependency_facts']
    if not isinstance(facts, dict) or not facts:
        return review('RAW_TRACE_HAS_NO_DEPENDENCY_FACTS')
    if any(not isinstance(f, dict) or type(f.get('known_at')) is not int or
           f['known_at'] > at or f['known_at'] < 0 or
           type(f.get('source')) is not str or not f['source'].strip() or
           f.get('origin') not in SOURCE_ORIGINS for f in facts.values()):
        return review('RAW_TRACE_FACT_PROVENANCE_INVALID')
    if not isinstance(decision['policy_required_keys'], list) or not isinstance(decision['context_required_keys'], list):
        return review('RAW_TRACE_INVALID_CONTEXT_INVENTORY')
    if decision['policy_required_keys']:
        return review('RESEARCH_DIRECTION_POLICY_NEEDS_SOURCE_REVIEW')
    if decision['context_required_keys']:
        return review('EXTERNAL_CONTEXT_NEEDS_SOURCE_REVIEW')
    if any(f['origin'] == 'SOURCED_CONTEXT' for f in facts.values()):
        return review('UNREVIEWED_CONTEXT_ORIGIN')
    if any(f['origin'] == 'DERIVED_MIXED' for f in facts.values()):
        return review('MIXED_DERIVATION_REQUIRES_TEACHER_CASE_REVIEW')
    if not decision.get('sources'):
        return review('TEACHER_LESSON_REFERENCE_MISSING')
    # Even all-from-raw facts prove causal computation only, not semantics.
    return review('ORIGINAL_TEACHER_DIALOGUE_VISUAL_AND_CASES_NOT_VERIFIED')


def inventory():
    """Report source availability, not what any teacher or student said."""
    path = Path(__file__).resolve().parent / 'docs' / 'SOURCE_COVERAGE.json'
    doc = json.loads(path.read_text(encoding='utf-8-sig'))
    sessions = doc['sessions']
    return {
        'kind': 'FILE_AVAILABILITY_INVENTORY_NOT_COMPLETED_LISTENING',
        'listed_sessions': len(sessions),
        'sessions_without_audio': [s['session'] for s in sessions if not s.get('audio_available')],
        'sessions_without_video': [s['session'] for s in sessions if not s.get('video_available')],
        'transcript_files_recorded': sum(len(s.get('transcript_files', [])) for s in sessions),
        'independently_reheard_entire_course_in_this_work': False,
    }


def summarize_audits(audits):
    counts = Counter(a['reason'] for a in audits)
    return {
        'reviewed_candidates': len(audits),
        'can_execute_as_teacher_method': 0,
        'reasons': dict(sorted(counts.items())),
        'all_teacher_provenance_gates_closed': True,
    }
