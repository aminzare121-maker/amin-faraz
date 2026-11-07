"""Grounded context capsules and conservative classroom-noise quarantine for Artin.

Only utterance-linked candidate anchors are emitted; a model cannot create a
teacher rule by summarizing a video. Source quotes and neighboring context are
for review, not for trade permission. This module has no trading interface.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

CAPSULE_KINDS = frozenset({"QUESTION", "ANSWER", "CORRECTION", "RULE", "EXCEPTION", "EXAMPLE", "CLASSROOM_NOISE"})
NOISE_CATEGORIES = frozenset({
    "CLASS_TECHNICAL_SUPPORT", "CLASS_ADMINISTRATION", "UNRELATED_CONVERSATION"
})

# Narrow cues for disruptions in a lesson; NEVER infer that a trading statement
# is noise solely because it contains 'technical', 'internet' or 'video'.
TECH_NOISE_PHRASES = (
    "میکروفون قطع", "صدای من قطع", "صدا قطع", "صدام قطع", "صدا نمیاد",
    "صدا نمی آد", "تصویر قطع", "تصویر نمیاد", "اینترنت قطع", "لینک کلاس",
    "اتصال کلاس", "دوربین خاموش", "اسکرین شیر", "اشتراک صفحه قطع",
    "لپ تاپ هنگ", "سیستم هنگ", "کلاس ضبط نمیشه",
    "جلسه رو ضبط", "پخش فیلم قطع", "جلسه بعد کی", "کلاس کی شروع",
)
TRADING_TERMS = (
    "کندل", "نمودار", "چارت", "معامله", "خرید", "فروش", "پوزیشن", "سیگنال",
    "بازار", "طلا", "قیمت", "تارگت", "استاپ", "حد ضرر", "حد سود", "روند",
    "پیوت", "ناحیه", "مقاومت", "حمایت", "ریسک", "سرمایه", "پرایس",
    "الگو", "بدنه", "سایه", "فیک", "بازگشت", "نقطه ورود", "خروج",
)


def normalized(text: str) -> str:
    val=unicodedata.normalize("NFKC",text).casefold()
    val=val.replace("ي","ی").replace("ك","ک").replace("\u200c"," ")
    return " ".join(re.sub(r"\s+", " ", val).split())


def noise_risk(text: str) -> str:
    """Return CLEAR_OFFTOPIC, MIXED_CONTEXT_REVIEW, or NOT_IDENTIFIED.

    CLEAR_OFFTOPIC is only a conservative screening hint, NOT a claim about
    source media. Uncertain mixed utterances are kept for audiovisual review.
    """
    val=normalized(text)
    cue=any(normalized(x) in val for x in TECH_NOISE_PHRASES)
    if not cue:
        return "NOT_IDENTIFIED"
    if any(normalized(x) in val for x in TRADING_TERMS):
        return "MIXED_CONTEXT_REVIEW"
    return "CLEAR_OFFTOPIC"


def make_capsule_id(chunk_num: int, source_id: str, quote: str) -> str:
    sig=f"{chunk_num}|{source_id}|{quote}"
    return "ac_"+hashlib.sha256(sig.encode("utf8")).hexdigest()[:20]


def validate_capsule(raw: object, core_segments: list[dict], part: dict) -> tuple[dict,list[dict]]:
    """Accept anchors with exact quotes from this chunk's core, never fabricated.

    Model may nominate teacher/question/correction relevance, but cannot verify
    teacher identity or authorize trading.
    """
    if not isinstance(raw,dict) or not isinstance(raw.get("anchors"),list):
        raise ValueError("Context model must return anchors array")
    by_id={s["id"]:s for s in core_segments}
    accepted,rejected=[],[]
    used=set()
    for i,item in enumerate(raw["anchors"][:100]):
        if not isinstance(item,dict):
            rejected.append({"index":i,"reason":"INVALID_ANCHOR"});continue
        source_id=item.get("source_id")
        src=by_id.get(source_id) if isinstance(source_id,str) else None
        quote=item.get("exact_quote")
        kind=item.get("kind")
        if not src or not isinstance(quote,str) or not quote.strip() or kind not in CAPSULE_KINDS:
            rejected.append({"index":i,"reason":"UNKNOWN_SOURCE_OR_KIND"});continue
        # Grounding is required at the exact segment; do not rely on free summary.
        if normalized(quote) not in normalized(src["text"]):
            rejected.append({"index":i,"reason":"FABRICATED_QUOTE"});continue
        if not (part["core_start"]<=src["start"]<part["core_end"]):
            rejected.append({"index":i,"reason":"NON_OWNED_CONTEXT"});continue
        k=(source_id,normalized(quote),kind)
        if k in used: continue
        used.add(k)
        cue=noise_risk(quote)
        if cue=="CLEAR_OFFTOPIC":
            kind="CLASSROOM_NOISE"
        accepted.append({"id":make_capsule_id(part["chunk"],source_id,quote),
                        "source_id":source_id,"chunk":part["chunk"],
                        "start":src["start"],"end":src["end"],
                        "exact_quote":quote,"kind_candidate":kind,
                        "noise_risk":cue,"speaker":"UNKNOWN",
                        "teacher_verified":False,"can_change_artin_engine":False})
    return {"schema":"artin_grounded_context_capsule_v1",
            "chunk":part["chunk"],"anchors":accepted,
            "teacher_meaning_understood_and_verified":False,
            "speaker_verified":False,"trade_ready":False},rejected


def adjacent_context(chunk_num: int, capsules: dict[int,dict]) -> dict:
    """Exactly previous/next 5-minute anchor windows; never assert ownership."""
    out={}
    for label,number in (("previous",chunk_num-1),("next",chunk_num+1)):
        capsule=capsules.get(number)
        out[label]={"chunk":number if capsule else None,
                    "anchors":(capsule.get("anchors",[]) if capsule else []),
                    "role":"CONTEXT_ONLY_NOT_PROOF_OR_EVENT_OWNER"}
    return out


def quarantine_events(events: list[dict]) -> tuple[list[dict],list[dict]]:
    """Preserve uncertain/noisy statements separately, never delete original evidence."""
    instructional,quarantine=[],[]
    for event in events:
        risk=noise_risk(event.get("quote", ""))
        model_says_noise=event.get("kind")=="CLASSROOM_NOISE"
        if risk!="NOT_IDENTIFIED" or model_says_noise:
            copied=dict(event)
            copied["noise_review_status"]=(
                "CLEAR_CLASS_TECH_NOT_TRADING" if risk=="CLEAR_OFFTOPIC"
                else "MIXED_TECH_AND_TRADING_REVIEW" if risk=="MIXED_CONTEXT_REVIEW"
                else "MODEL_NOISE_CANDIDATE_REQUIRE_REVIEW")
            copied["can_change_artin_engine"]=False
            quarantine.append(copied)
        else:
            instructional.append(event)
    return instructional,quarantine
