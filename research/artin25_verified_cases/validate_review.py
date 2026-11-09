#!/usr/bin/env python3
"""Manual visual review notes, automatically checked against exact ASR text + original image bytes.
Scope: six high-value, explicitly named Artin teaching examples, not the entire 25-session semantics.
Never treats time proximity, OCR or a drawing as proof of instructor execution.
"""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict
import hashlib,io,json,subprocess,zipfile

REPO="aminzare121-maker/amin-faraz"
PRIORITY_ARTIFACT=13693183892
FRAMES_ARTIFACT=13693914107
OUT=Path("artin25_verified_cases_output")
OUT.mkdir(exist_ok=True)
CASES=[
 {
  "id":"A04-QUOTE-MECHANICS","seq":4,"speech_time":2203.66,
  "required_words":["معامله سلی که میگیری با بید شروع میشه","معامله بایی که میگیری با اسک شروع میشه آبیه"],
  "source_image":"board/b001_s08_g000008_t0002205000_board.png",
  "visible_source_observation":"MT5 Market Watch shows Bid and Ask columns and the SELL/BUY quote panel",
  "meaning_assessment_fa":"نمونهٔ آموزشی، قیمت Bid را به فروش و Ask را به خرید مربوط می‌کند؛ این یک سازوکار اجرای قیمت است، نه سیگنال معامله.",
  "assessment":"TEXT_AND_IMAGE_SUPPORT_PLATFORM_QUOTE_EXPLANATION",
  "visual_contradicts_source":False,"literal_entry_conditions_complete":False,
  "missing":["تأیید هویت گوینده","اثبات اینکه این توضیح قانون معاملاتی مدرس است"]
 },
 {
  "id":"A13-WEAK-TREND-REVERSE","seq":13,"speech_time":3194.15,
  "required_words":["توی روند زعیف شما فقط اجازه گرفتن پوزیشن ریورس رو دارید","یعنی بعد از یک اصلاحی با استراتیجی که بهتون یاد میدن بعدن بایی بگیرید."],
  "source_image":"board/b001_s11_g000011_t0003195000_board.png",
  "visible_source_observation":"AUD/USD 15 minute TradingView chart, schematic zigzag and diagonal TR line",
  "meaning_assessment_fa":"گفتار از محدودیت ورود در روند ضعیف و پوزیشن معکوس پس از اصلاح صحبت می‌کند؛ تصویر ترسیم آموزشی دارد اما معیار اندازه‌گیری ضعف روند و شرط دقیق ورود را نشان نمی‌دهد.",
  "assessment":"VOICE_CONSTRAINT_FOUND_CHART_PARTIAL_NO_TREND_THRESHOLD",
  "visual_contradicts_source":False,"literal_entry_conditions_complete":False,
  "missing":["تعریف عملیاتی روند ضعیف","شرط تکمیل اصلاح","تأیید نقش مدرس","جست‌وجوی اصلاح بعدی"]
 },
 {
  "id":"A15-BREAKOUT-VS-PULLBACK","seq":15,"speech_time":1546.15,
  "required_words":["یه سری از شکست ها","شما دیگه باید منتظر پول بک بمونی","جواز این رو داری که بعد از شکست بلا فاصله ورود کنی","اون برمیگرده به استراتیجی های نقطه ورودمون"],
  "source_image":"board/b001_s06_g000006_t0001545000_board.png",
  "visible_source_observation":"The visible original frame is classroom chat/screen sharing, not a clear breakout candlestick example",
  "meaning_assessment_fa":"گفتار دو حالت انتظار برای پولبک یا ورود سریع پس از شکست را مطرح می‌کند، اما مشخص نمی‌کند در کدام نوع شکست کدام حالت مجاز است.",
  "assessment":"TWO_ALTERNATIVE_EXECUTION_PATHS_UNRESOLVED",
  "visual_contradicts_source":False,"literal_entry_conditions_complete":False,
  "missing":["طبقه‌بندی شکست‌هایی که انتظار پولبک می‌خواهند","طبقه‌بندی شکست‌های ورود فوری","تصویر نمونهٔ دارای کندل مشخص","تأیید نقش مدرس"]
 },
 {
  "id":"A19-PIERCING-EXAMPLE","seq":19,"speech_time":4304.0,
  "required_words":["این کارو نمی کنم ورود نمی کنم","ولی اگر اومد پیرسینگش کرد اینجا افتاد","من اینجا ورود میکنم"],
  "source_image":"board/b001_s15_g000015_t0004305000_board.png",
  "visible_source_observation":"XAUUSD TradingView 15 minute illustrated zigzag, candle and shaded long/short position risk-reward boxes",
  "meaning_assessment_fa":"عبارات شرطی و ترسیم شماتیک از تفاوت عدم ورود و ورود پس از یک حرکت موسوم به پیرسینگ پشتیبانی می‌کنند؛ این اجرای واقعی سفارش نیست.",
  "assessment":"ILLUSTRATED_CONDITIONAL_ENTRY_BUT_INCOMPLETE_PREDICATES",
  "visual_contradicts_source":False,"literal_entry_conditions_complete":False,
  "missing":["تعریف دقیق پیرسینگ و مرجع کندلی","جهت قطعی ورود","تأیید نقش مدرس","آزمون همان مثال با دادهٔ کندلی"]
 },
 {
  "id":"A21-STOP-BEHIND-LIQUIDITY","seq":21,"speech_time":944.57,
  "required_words":["لیکویدیتی بوده","Pivot نقدی نگی بوده","ریسکش رو بپذیرم","به شرط این که تو باکس تریدت جلو باشی ورود خوب"],
  "source_image":"board/b001_s04_g000004_t0000945000_board.png",
  "visible_source_observation":"XAUUSD 15 minute chart displays a short-position risk/reward rectangle with red stop region above entry",
  "meaning_assessment_fa":"گفتار حد ضرر مرتبط با ناحیهٔ نقدینگی/پیوت و پذیرش ریسک مشروط به کیفیت ورود را توصیف می‌کند؛ فاصلهٔ دقیق و حجم معامله مشخص نیست.",
  "assessment":"ILLUSTRATIVE_STOP_PLACEMENT_CONDITION_NOT_NUMERIC",
  "visual_contradicts_source":False,"literal_entry_conditions_complete":False,
  "missing":["انتخاب قطعی پیوت معتبر","فاصلهٔ حد ضرر و حاشیهٔ ایمنی","حداکثر ریسک دلاری/درصدی","تأیید نقش مدرس"]
 },
 {
  "id":"A25-TARGET2-RISKFREE","seq":25,"speech_time":2504.05,
  "required_words":["مثلا بدونی هر وقت به تارگیت دو","رسید ریسک فیری میخوایی بکنید","یعنی استاپلاس رو ورداری بیاری بذاری نقطه ورداری","حالا به عنوان مثال دارم میگم"],
  "source_image":"board/b001_s09_g000009_t0002505000_board.png",
  "visible_source_observation":"MT5 chart drawing labels target1, target2 riskfree, target3; no verified order execution",
  "meaning_assessment_fa":"انتقال حد ضرر به نقطهٔ بدون زیان در هدف دوم به‌صراحت در قالب مثال توضیح داده شده و نباید به‌عنوان قاعدهٔ همیشگی وارد ربات شود.",
  "assessment":"EXPLICIT_EXAMPLE_NOT_UNIVERSAL_RISKFREE_POLICY",
  "visual_contradicts_source":False,"literal_entry_conditions_complete":False,
  "missing":["آیا قانون همگانی است یا فقط مثال","تعیین قیمت دقیق سربه‌سر و کارمزد","زمان فعال‌سازی در معاملات دیگر","تأیید نقش مدرس"]
 }
]
CROSS_LINKS=[
 {
  "from":"A13-WEAK-TREND-REVERSE","to":"A15-BREAKOUT-VS-PULLBACK",
  "relationship":"different market conditions may allow different entry types",
  "resolved_override":False,"proven_conflict":False,
  "pending_fa":"باید ثابت شود شرایط روند ضعیف با وضعیت شکست موردبحث مشترک است یا خیر."
 },
 {
  "from":"A15-BREAKOUT-VS-PULLBACK","to":"A19-PIERCING-EXAMPLE",
  "relationship":"candidate later elaboration on immediate-vs-confirmed entry",
  "resolved_override":False,"proven_conflict":False,
  "pending_fa":"هنوز معلوم نیست پیرسینگ مربوط به کدام دستهٔ شکست‌هاست و آیا تأیید اضافی می‌خواهد."
 },
 {
  "from":"A21-STOP-BEHIND-LIQUIDITY","to":"A25-TARGET2-RISKFREE",
  "relationship":"initial stop placement versus an example of later stop management",
  "resolved_override":False,"proven_conflict":False,
  "pending_fa":"دو مرحلهٔ متفاوت مدیریت موقعیت هستند؛ جابه‌جایی استاپ در تارگت دوم قانون کلی تأیید نشده است."
 },
 {
  "from":"A04-QUOTE-MECHANICS","to":"A19-PIERCING-EXAMPLE",
  "relationship":"execution price mechanics versus strategy decision",
  "resolved_override":False,"proven_conflict":False,
  "pending_fa":"قواعد قیمت‌گذاری سفارش، جایگزین شروط تصمیم ورود نیستند."
 }
]
def sha(b):return hashlib.sha256(b).hexdigest()
def artifact_zip(artifact_id):
    r=subprocess.run(["gh","api",f"repos/{REPO}/actions/artifacts/{artifact_id}/zip"],capture_output=True,timeout=240)
    if r.returncode:raise RuntimeError("Artifact fetch failed "+str(artifact_id)+":"+r.stderr.decode("utf8","replace")[:200])
    if not zipfile.is_zipfile(io.BytesIO(r.stdout)):raise RuntimeError("Invalid artifact zip")
    return r.stdout
def find_one(names,suffix):
    x=[n for n in names if n.endswith(suffix)]
    if len(x)!=1:raise RuntimeError(f"Expected one {suffix}, got {x}")
    return x[0]

prior=artifact_zip(PRIORITY_ARTIFACT)
with zipfile.ZipFile(io.BytesIO(prior)) as z:
    priorities=json.loads(z.read(find_one(z.namelist(),"priority_review.json")))
frames_zip=artifact_zip(FRAMES_ARTIFACT)
with zipfile.ZipFile(io.BytesIO(frames_zip)) as z:
    inside=z.read(find_one(z.namelist(),"66_original_source_frames.zip"))
with zipfile.ZipFile(io.BytesIO(inside)) as z:
    if z.testzip() is not None:raise RuntimeError("Original frame ZIP has CRC error")
    manifest=json.loads(z.read("frame_window_manifest.json"))
    source_names=z.namelist()
    records=[]
    failures=[]
    for case in CASES:
        seq,time=case["seq"],case["speech_time"]
        options=[r for r in manifest if r["session"]==seq and abs(float(r["speech_time_seconds"])-time)<0.03]
        candidates=[r for r in priorities if r["session"]==seq and abs(float(r["time"])-time)<0.03]
        if len(options)!=1 or len(candidates)!=1:raise RuntimeError("ANCHOR_NOT_UNIQUE:"+case["id"])
        raw=candidates[0]
        speech_joined=" ".join(v.get("text","") for v in raw["context"])
        missing=[q for q in case["required_words"] if q not in speech_joined]
        if missing:failures.append({"id":case["id"],"missing_text":missing})
        frame=[v for v in options[0]["frames"] if v["source_original_path"]==case["source_image"]]
        if len(frame)!=1:raise RuntimeError("Expected image path not in source manifest:"+case["id"])
        f=frame[0]
        data=z.read(f["archive_path"])
        if sha(data)!=f["source_image_sha256"]:raise RuntimeError("Original SHA-256 mismatch:"+case["id"])
        delta=abs(float(f["source_time_seconds"])-time)
        if delta>2.5:raise RuntimeError("Frame too distant from spoken example:"+case["id"]+" "+str(delta))
        case["proof"]={
            "queue_sequence":seq,
            "speech_time_seconds":time,
            "speech_literal_exact":raw["speech"],
            "speech_context_exact":raw["context"],
            "visual_original_source_path":case["source_image"],
            "source_visual_artifact_id":f["source_artifact_id"],
            "visual_SHA256":sha(data),
            "visual_delta_seconds":round(delta,3),
            "visual_manifest_frame_archive_path":f["archive_path"],
            "teacher_role_automatically_verified":False,
            "actual_trade_executed_confirmed":False
        }
        case["review_stage"]="MANUALLY_INSPECTED_VISUAL_AND_MACHINE_TRANSCRIPT; TEACHER_ROLE_NOT_VERIFIED"
        case["strategy_rule_certified"]=False
        case["mt5_auto_order_allowed"]=False
        records.append(case)
    if failures:raise RuntimeError("SOURCE_SPEECH_TEXT_MISMATCH:"+json.dumps(failures,ensure_ascii=False))

rule_contract={
 "source_cases":[v["id"] for v in records],
 "working_concepts":[
  {"id":"platform_bid_ask","evidence":"A04-QUOTE-MECHANICS","class":"platform_execution_mechanics","required_conditions_for_orders":"NOT_A_STRATEGY_RULE"},
  {"id":"weak_trend_reversal","evidence":"A13-WEAK-TREND-REVERSE","class":"conditional_entry_restriction","weak_trend_definition":None,"reversal_trigger":None},
  {"id":"breakout_or_pullback","evidence":["A15-BREAKOUT-VS-PULLBACK","A19-PIERCING-EXAMPLE"],"class":"alternative_setup_types","breakout_type_classifier":None,"pullback_trigger":None,"piercing_trigger":None},
  {"id":"initial_stop_location","evidence":"A21-STOP-BEHIND-LIQUIDITY","class":"stop_placement_example","valid_pivot_detection":None,"risk_budget":None},
  {"id":"break_even_after_target","evidence":"A25-TARGET2-RISKFREE","class":"illustrative_stop_management","applies_globally":False,"general_activation_condition":None}
 ],
 "teacher_role_verified":False,
 "independently_confirmed_complete_entry_predicates":0,
 "independently_confirmed_complete_exit_predicates":0,
 "cross_session_supersession_verified":False,
 "can_open_trade":False,
 "can_close_trade":False,
 "MT5_live_trading_forbidden":True
}
tests={
 "all_six_source_cases_have_original_image_sha256":len(records)==6 and all(len(x["proof"]["visual_SHA256"])==64 for x in records),
 "literal_speech_context_confirmed":len(failures)==0,
 "frame_delta_at_most_2_5_seconds":all(x["proof"]["visual_delta_seconds"]<=2.5 for x in records),
 "none_claims_teacher_voice_verified":all(x["proof"]["teacher_role_automatically_verified"] is False for x in records),
 "no_unverified_strategy_rule_executable":all(x["mt5_auto_order_allowed"] is False for x in records),
 "cross_session_links_no_unsupported_override":all(x["resolved_override"] is False for x in CROSS_LINKS)
}
summary={
 "schema":"artin25_manual_semantic_case_audit_v1",
 "source_priority_artifact":PRIORITY_ARTIFACT,
 "source_original_frame_artifact":FRAMES_ARTIFACT,
 "reviewed_cases":len(records),
 "sessions_directly_reviewed":sorted(set(x["seq"] for x in records)),
 "source_image_hashes_verified":sum(bool(x["proof"]["visual_SHA256"]) for x in records),
 "explicit_cross_session_relationships_audited":len(CROSS_LINKS),
 "teacher_method_complete_certification":False,
 "valid_strategy_entry_conditions":0,
 "approved_mt5_order_rules":0,
 "tests":tests
}
def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf8")
save("six_semantic_source_cases.json",records)
save("cross_session_conflict_review.json",CROSS_LINKS)
save("strategy_predicate_gaps.json",rule_contract)
save("test_results.json",tests)
save("summary.json",summary)
print("ARTIN_MANUAL_SEMANTIC_AUDIT="+json.dumps(summary,ensure_ascii=False),flush=True)
print("ARTIN_SEMANTIC_CASES="+json.dumps([{"id":x["id"],"classification":x["assessment"],"imageSHA256":x["proof"]["visual_SHA256"],"delta":x["proof"]["visual_delta_seconds"]} for x in records]),flush=True)
if not all(tests.values()):raise SystemExit(2)
