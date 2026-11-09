#!/usr/bin/env python3
"""Apply Artin teacher-source hierarchy without manufacturing semantic certainty.

Oral instruction in the original video is the authority.  The teacher's
19-page handwritten Technical.pdf is a *supporting* reference to clarify
terminology and teaching scenarios.  Machine ASR is not authenticated oral
speech.  Neither a PDF page nor a plausible interpretation authorizes a trade.
"""
import re

SHA256 = re.compile(r'^[0-9a-f]{64}$')
DECISIONS = {'ENTER', 'EXIT', 'HOLD', 'NO_TRADE'}


def good_sha(s):
    return isinstance(s, str) and SHA256.fullmatch(s) is not None


def resolve_priority(case):
    """Return a non-trading provenance/authority verdict.

    The decision is only a provenance/preference verdict, not a certificate of
    correctness.  A reviewed oral statement overrides interpretation from
    the handbook; contradictory handbook language triggers explicit review.
    """
    if not isinstance(case, dict):
        raise TypeError('case must be a dictionary')
    oral = case.get('oral_evidence')
    page = case.get('pdf_reference')
    result = {
        'authority': 'ORIGINAL_TEACHER_SPEECH',
        'pdf_role': 'SUPPLEMENTAL_CLARIFICATION_ONLY',
        'teacher_semantics_certified': False,
        'decision_certified': False,
        'mt5_trade_allowed': False,
        'oral_expected_decision': None,
        'status': None,
        'reasons': [],
    }
    if page is not None:
        if not isinstance(page, dict) or not (type(page.get('page')) is int and 1 <= page['page'] <= 19) or not good_sha(page.get('pdf_sha256')):
            result['status'] = 'INVALID_PDF_PROVENANCE'
            result['reasons'].append('page number and Technical.pdf SHA-256 required')
            return result
        if page.get('claim_of_teacher_speech_verified') is True or page.get('trade_permission') is True:
            result['status'] = 'IMPROPER_PDF_PROMOTION'
            result['reasons'].append('PDF cannot certify oral instruction or issue trades')
            return result
    if not isinstance(oral, dict):
        result['status'] = 'ORAL_SOURCE_MISSING'
        result['reasons'].append('PDF alone may clarify a topic, not establish a spoken trading rule')
        return result
    if not good_sha(oral.get('audio_sha256')) or not isinstance(oral.get('session'), int) or not 1 <= oral['session'] <= 25:
        result['status'] = 'INVALID_ORAL_ANCHOR'
        result['reasons'].append('original audio source hash and lesson id required')
        return result
    start, end = oral.get('start_seconds'), oral.get('end_seconds')
    if type(start) not in (int, float) or type(end) not in (int, float) or not 0 <= start <= end:
        result['status'] = 'INVALID_ORAL_TIME'
        result['reasons'].append('original video speech time interval required')
        return result
    if oral.get('speaker_is_teacher_verified') is not True or oral.get('words_checked_against_original_audio') is not True:
        result['status'] = 'ORAL_AUDIO_REVIEW_REQUIRED'
        result['reasons'].append('machine ASR cannot establish teacher identity or exact speech')
        return result
    if oral.get('meaning_reviewed_against_context') is not True:
        result['status'] = 'ORAL_MEANING_REVIEW_REQUIRED'
        result['reasons'].append('spoken wording needs surrounding speech and original visuals')
        return result
    result['oral_expected_decision'] = oral.get('teacher_decision') if oral.get('teacher_decision') in DECISIONS else None
    if page and page.get('meaning_conflict_with_oral') is True:
        result['status'] = 'ORAL_PRIMARY_PDF_CONFLICT_FLAGGED'
        result['reasons'].append('prefer independently checked oral lesson; mark PDF discrepancy for review')
        return result
    if oral.get('later_session_correction_claimed') is True and oral.get('later_correction_verified') is not True:
        result['status'] = 'LATER_LESSON_CORRECTION_UNVERIFIED'
        result['reasons'].append('later lecture not automatically a verified change to old rule')
        return result
    result['status'] = 'ORAL_PRIMARY_CONTEXT_REVIEWED'
    if not (oral.get('entry_exit_exception_order_complete') is True and
            oral.get('independent_motor_comparison_passed') is True and
            result['oral_expected_decision'] is not None):
        result['reasons'].append('standalone provenance check does not certify executable decisions')
    # Deliberately never promote source-precedence checks into autonomous-trading approval.
    return result


def candidate_rule_with_pdf_ok(rule):
    """Backward-compatible guard: only applies to claims citing a PDF page."""
    if 'pdf_reference' not in rule:
        return True, None
    answer = resolve_priority(rule)
    if answer['status'] != 'ORAL_PRIMARY_CONTEXT_REVIEWED':
        return False, 'pdf_source_priority_' + answer['status'].lower()
    return True, None