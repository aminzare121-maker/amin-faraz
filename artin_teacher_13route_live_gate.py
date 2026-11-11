"""Causal 13-route instructor-core validation before any DEMO trade decision.

All 13 routes are evaluated from CLOSED real candles with the immutable S19
source-patched teacher core.  PDF geometry is not a teacher-approved entry.
Without independently verified context facts (sentiment, zone, pivot, half leg,
teacher corrections), the result is review-only, NEVER an order approval.
No broker API imports or order commands are present in this module.
"""
from __future__ import annotations
import hashlib
import importlib
import json
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = HERE / 'teacher_s19' / 'teacher_core_s19'
SOURCE = 'ARTIN_25_SESSION_MACHINE_SPEECH_PLUS_TECHNICAL_FXM_NOT_INDEPENDENTLY_CERTIFIED'
PINNED_MANIFEST_CANONICAL_SHA256 = '9485596ddef62ccec983c4d34b8ae3e6073e59a2e67a2671c55491f02c22b1a2'

class TeacherCoreUnavailable(RuntimeError):
    pass


def verified_core():
    manifest_path = CORE/'TEACHER_CORE_S19_PATCH_MANIFEST.json'
    if not manifest_path.is_file():
        raise TeacherCoreUnavailable('S19_TEACHER_CORE_NOT_INSTALLED')
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        canonical=json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')
        if hashlib.sha256(canonical).hexdigest()!=PINNED_MANIFEST_CANONICAL_SHA256:
            raise TeacherCoreUnavailable('S19_SOURCE_MANIFEST_CONTENT_CHANGED')
        if set(manifest['changed_files']) != {'entry_engine.py','raw_pipeline.py','examples.py'}:
            raise TeacherCoreUnavailable('UNEXPECTED_S19_CORRECTION_SCOPE')
        if manifest['original_core_git_commit'] != 'b48fb06f8b2b0d134292025f5b27fc670ad2a293':
            raise TeacherCoreUnavailable('BASE_TEACHER_SOURCE_CHANGED')
        for name, expected in manifest['sha256'].items():
            path=CORE/name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise TeacherCoreUnavailable('S19_CORE_SHA_MISMATCH:'+name)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise TeacherCoreUnavailable('INVALID_S19_SOURCE_MANIFEST') from exc
    return PINNED_MANIFEST_CANONICAL_SHA256


def review_closed_bars(bars, *, limit=64):
    """Diagnose 13 routes from causally closed OHLC, without invented context.

    Returns 26 decisions on final M15 candle (two sides x 13 routes).  Every
    geometry candidate still requires full teacher evidence, not PDF similarity.
    Caller must never infer authorization merely from `status == ELIGIBLE`.
    """
    manifest_sha=verified_core()
    from artin_s19_auto_sequence import observe_s19_three
    if not isinstance(bars,(list,tuple)) or len(bars)<3:
        raise TeacherCoreUnavailable('CLOSED_M15_HISTORY_TOO_SHORT')
    if type(limit) is not int or limit<3 or limit>4096:
        raise TeacherCoreUnavailable('INVALID_TEACHER_WINDOW')
    # Import exact reviewed, SHA-pinned engine; reject preloaded conflicting
    # library module from another directory rather than running mixed versions.
    engine_path=str(CORE.resolve())
    for mod in ('entry_engine','raw_geometry','raw_pipeline','teacher_features',
                'context_inputs','zone_behavior','punch_behavior','pullback_bridge',
                'confirmed_pause','relative_sequence'):
        existing=sys.modules.get(mod)
        if existing is not None:
            f=getattr(existing,'__file__',None)
            if not f or Path(f).resolve().parent!=CORE.resolve():
                raise TeacherCoreUnavailable('MIXED_TEACHER_CODE_IMPORT:'+mod)
    if engine_path not in sys.path:
        sys.path.insert(0,engine_path)
    import entry_engine
    from raw_geometry import Candle
    from raw_pipeline import RawPipeline
    if len(entry_engine.RULE_IDS)!=13:
        raise TeacherCoreUnavailable('THIRTEEN_ROUTE_CONTRACT_CHANGED')
    subset=bars[-limit:]
    raw_hash=hashlib.sha256(json.dumps([
        [b.t,str(b.open),str(b.high),str(b.low),str(b.close)] for b in subset],
        ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
    pipeline=RawPipeline('ARTIN_LIVE_ALL_13_SOURCE_GUARD',entry_engine.RULE_IDS,
                         900,raw_hash,contexts=())
    result=None
    prev=None
    for b in subset:
        if type(b.t) is not int or b.t<0:
            raise TeacherCoreUnavailable('INVALID_NATIVE_BAR_TIME')
        if prev is not None and b.t<=prev:
            raise TeacherCoreUnavailable('UNSORTED_OR_DUPLICATE_BAR_TIME')
        prev=b.t
        candle=Candle(b.t,b.t+900,*(Decimal(str(getattr(b,k))) for k in ('open','high','low','close')))
        result=pipeline.step(candle)
    decisions=result['decisions']
    s19_geometry=observe_s19_three(subset)
    from artin_teacher_structure_observer import observe_structure
    automatic_structure=observe_structure(subset)
    if len(decisions)!=26:
        raise TeacherCoreUnavailable('NOT_ALL_13_ROUTES_REVIEWED')
    summary=[{'side':d['side'],'rule_id':d['rule_id'],'status':d['status'],
              'reasons':list(d['reasons']),'missing_dependencies':list(d['missing_dependencies']),
              'future_dependencies':list(d['future_dependencies']),
              'sources':list(d['sources']),'order_created':bool(d['order_created'])}
             for d in decisions]
    return {'schema':'artin_live_full13_teacher_guard_v1','last_closed_at':result['at'],
            'teacher_source_manifest_sha256':manifest_sha,'raw_ohlc_sha256':raw_hash,
            'rules_checked':13,'directions_checked':2,'decisions_checked':len(summary),
            'decisions':summary,
            's19_three_candle_auto_measurement':s19_geometry,
            'automatic_structure':automatic_structure,
            'video_teacher_semantics_independently_approved':False,
            'pdf_is_supplement_not_override':True,
            'broker_orders_authorized':False,
            'source_scope':SOURCE}


def gate_pdf_candidate(candidate,review):
    """Require same-side matching route AND independent source verification.

    On the present evidence, no teacher model is independently certified,
    hence ALWAYS blocks orders; the candidate remains visible for research.
    """
    if candidate.route.startswith('REVERSAL_'):
        compatible=('REVERSAL_CLASSIC','REVERSAL_THREE','REVERSAL_STAR')
    elif candidate.route.startswith('BREAK_'):
        compatible=('BREAK_STRONG','BREAK_WEAK_PIVOT','BREAK_WEAK_FULLBODY_EXCEPTION',
                    'BREAK_VERY_STRONG_RETEST')
    else:
        compatible=()
    matches=[d for d in review['decisions']
             if d['side']==candidate.side and d['rule_id'] in compatible]
    all_complete=[d for d in matches if d['status']=='ELIGIBLE'
                  and not d['missing_dependencies'] and not d['future_dependencies']]
    approved=(review['video_teacher_semantics_independently_approved'] is True and
              candidate.teacher_semantics_fully_verified is True and
              bool(all_complete))
    return {'candidate':candidate.route,'side':candidate.side,
            'matched_teacher_routes':[d['rule_id'] for d in matches],
            'source_complete_routes':[d['rule_id'] for d in all_complete],
            'video_semantics_verified':review['video_teacher_semantics_independently_approved'],
            'teacher_entry_authorized':approved,
            'status':'TEACHER_SOURCE_APPROVED' if approved else 'BLOCKED_INCOMPLETE_TEACHER_SOURCE',
            'orders_allowed':bool(approved)}