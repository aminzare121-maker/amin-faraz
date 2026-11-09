#!/usr/bin/env python3
"""Four additional original-image case checks, not strategy or teacher-identity certification."""
import hashlib,io,json,pathlib,subprocess,zipfile
R="aminzare121-maker/amin-faraz"; O=pathlib.Path("artin25_more_cases_output");O.mkdir(exist_ok=True)
FR=13693914107;PR=13693183892
CASES=[
 {"id":"A12-CANDLE-BODY","sequence":12,"time":2294.42,
  "original_image":"board/b001_s08_g000008_t0002295000_board.png",
  "quote_required":["خب به تمام کندل هایی که","بدنه های بزرگتر از سایه دارن"],
  "visible":"Handwritten original diagram shows two candle bodies and their wicks",
  "meaning_fa":"آموزش تمایز بدنه و سایهٔ کندل در گفتار و تصویر دیده می‌شود؛ شرط تبدیل آن به سیگنال ورود مشخص نیست.",
  "status":"EXPLANATION_SUPPORTED_BUT_NOT_ENTRY_RULE",
  "needed":["آستانهٔ کمی بدنه به سایه","جایگاه شکل کندل در الگوی ورود","تأیید هویت گوینده"]},
 {"id":"A14-TREND-TYPES","sequence":14,"time":973.8,
  "original_image":"board/b001_s04_g000004_t0000975000_board.png",
  "quote_required":["اون توانا مثلا یه روند سعودی نوزولیه یا رنج میزنه"],
  "visible":"Original handwritten list explicitly labels up-trend, down-trend and range-trend",
  "meaning_fa":"سه نوع حالت صعودی، نزولی و رنج در گفتار و تخته تأیید محتوایی می‌شوند؛ معیار الگوریتمی تشخیص آن‌ها هنوز موجود نیست.",
  "status":"REGIME_CATEGORIES_SUPPORTED_NO_AUTOMATIC_CLASSIFIER",
  "needed":["تعریف دقیق قله/کف یا شیب لازم","تایم‌فریم تصمیم","شرط تغییر حالت","تأیید هویت گوینده"]},
 {"id":"A18-ENTRY-SCHEMATIC","sequence":18,"time":822.99,
  "original_image":"board/b001_s03_g000003_t0000825000_board.png",
  "quote_required":["من اگر میخواستم ورود بکنم","داشت و پوزیشن داشتم"],
  "visible":"TradingView XAUUSD 15m with PV, OB, descending trendline and circled reactions; no brokerage order proof",
  "meaning_fa":"گفتار به ورودِ فرضی در ناحیهٔ خاص اشاره دارد و تصویر نمودار متناظر دارد، اما معیار قطعی ورود و وقوع سفارش ثابت نشده است.",
  "status":"ILLUSTRATIVE_ENTRY_NOT_ORDER_EXECUTION",
  "needed":["قیمت و زمان دقیق ورود فرضی","نقش پیوت، اردربلاک و خط روند","حد ضرر","تأیید هویت گوینده"]},
 {"id":"A24-RR-ARITHMETIC","sequence":24,"time":3610.07,
  "original_image":"board/b001_s13_g000013_t0003615000_board.png",
  "quote_required":["چما استاپلاست ده دولاره","تیپیت میتونه تا 13 دولار وای سید سود بگید","که آرواره 1 و 3 بشید"],
  "visible":"Actual whiteboard shows RR=reward/risk and distinct examples 20/10=2, 8/10=0.8, alongside Reduction, Riskfree and SweepProfit",
  "meaning_fa":"اصل محاسبهٔ نسبت سود به زیان تأیید محتوایی دارد؛ مثال ۱۳ دلار سود و ۱۰ دلار زیان در گفتار است، اما اعداد تصویر مربوط به مثال‌های دیگری هستند. هیچ حداقل RR عمومی از آن نتیجه نمی‌شود.",
  "status":"RR_FORMULA_SUPPORTED_NUMERIC_EXAMPLES_DISTINCT",
  "needed":["تشخیص سیاست حداقل RR","اثر کاهش حجم و سود ذخیره‌شده","مثال کندلی معاملاتی همان جلسه","تأیید هویت گوینده"]}
]
def get_art(id):
    p=subprocess.run(["gh","api",f"repos/{R}/actions/artifacts/{id}/zip"],capture_output=True,timeout=200)
    if p.returncode:raise RuntimeError("SOURCE_DOWNLOAD "+str(id)+" "+p.stderr.decode("utf8","replace")[:180])
    if not zipfile.is_zipfile(io.BytesIO(p.stdout)):raise RuntimeError("NOT_ZIP")
    return p.stdout
with zipfile.ZipFile(io.BytesIO(get_art(PR))) as z:
    n=[x for x in z.namelist() if x.endswith("priority_review.json")]
    assert len(n)==1
    windows=json.loads(z.read(n[0]))
with zipfile.ZipFile(io.BytesIO(get_art(FR))) as z:
    n=[x for x in z.namelist() if x.endswith("66_original_source_frames.zip")]
    assert len(n)==1
    nested=z.read(n[0])
with zipfile.ZipFile(io.BytesIO(nested)) as z:
    manifest=json.loads(z.read("frame_window_manifest.json"))
    for case in CASES:
        seq,t=case["sequence"],case["time"]
        row=[x for x in windows if x["session"]==seq and abs(x["time"]-t)<0.025]
        frame_record=[x for x in manifest if x["session"]==seq and abs(x["speech_time_seconds"]-t)<0.025]
        if len(row)!=1 or len(frame_record)!=1:raise RuntimeError("AMBIGUOUS_SOURCE_WINDOW "+case["id"])
        context=" ".join(x["text"] for x in row[0]["context"])
        if not all(q in context for q in case["quote_required"]):raise RuntimeError("ASR_QUOTE_MISMATCH "+case["id"])
        frames=[x for x in frame_record[0]["frames"] if x["source_original_path"]==case["original_image"]]
        if len(frames)!=1:raise RuntimeError("VISUAL_SOURCE_NOT_FOUND "+case["id"])
        f=frames[0];blob=z.read(f["archive_path"])
        h=hashlib.sha256(blob).hexdigest()
        if h!=f["source_image_sha256"]:raise RuntimeError("IMAGE_HASH_MISMATCH "+case["id"])
        case["source_proof"]={
            "original_ASR":row[0]["speech"],
            "context_exact":row[0]["context"],
            "original_image_sha256":h,
            "original_image_artifact":f["source_artifact_id"],
            "image_timestamp":f["source_time_seconds"],
            "distance_to_speech_seconds":round(abs(f["source_time_seconds"]-t),3)
        }
        if case["source_proof"]["distance_to_speech_seconds"]>6:raise RuntimeError("VISUAL_TOO_DISTANT "+case["id"])
        case["speaker_role_independently_proven"]=False
        case["executable_strategy_rule"]=False
LINKS=[
 {"earlier":"A12-CANDLE-BODY","later":"A19-PIERCING-EXAMPLE","relation":"Candlestick morphology potentially matters to later illustrated entry but has no proven mandatory role","confirmed_supersession":False},
 {"earlier":"A14-TREND-TYPES","later":"A13-WEAK-TREND-REVERSE","relation":"Regime categories and weak-trend reversal constraints need an explicit shared classifier","confirmed_supersession":False},
 {"earlier":"A18-ENTRY-SCHEMATIC","later":"A19-PIERCING-EXAMPLE","relation":"Pivot/OB example and later piercing are both entry illustrations; not proven same strategy","confirmed_supersession":False},
 {"earlier":"A24-RR-ARITHMETIC","later":"A25-TARGET2-RISKFREE","relation":"Reward/risk calculation is distinct from later illustrative break-even stop management","confirmed_supersession":False}
]
# These are mathematical consistency tests, not instructor strategy backtests.
riskreward=lambda reward,risk: reward/risk if risk>0 else None
tests={
 "all_four_original_images_SHA256_match":len(CASES)==4 and all(len(x["source_proof"]["original_image_sha256"])==64 for x in CASES),
 "ASR_quotes_correspond_to_original_window":all(len(x["source_proof"]["context_exact"])>=3 for x in CASES),
 "risk_reward_math_examples":riskreward(20,10)==2 and riskreward(8,10)==0.8 and riskreward(13,10)==1.3,
 "no_teacher_role_claim":all(not x["speaker_role_independently_proven"] for x in CASES),
 "no_unsupported_entry_rule":all(not x["executable_strategy_rule"] for x in CASES),
 "no_fake_cross_session_override":all(not x["confirmed_supersession"] for x in LINKS)
}
summary={
 "schema":"artin_more_four_semantic_sources_v1",
 "reviewed":4,"sessions":[x["sequence"] for x in CASES],
 "source_visual_artifact":FR,"source_speech_artifact":PR,
 "all_original_visual_sha256_checked":True,
 "new_instruction_concepts_reviewed":4,
 "pending_cross_session_links":len(LINKS),
 "confirmed_teacher_trading_rules":0,
 "mql5_compile_or_backtest_completed":False,
 "tests":tests
}
for name,obj in [("cases.json",CASES),("cross_session_links.json",LINKS),("tests.json",tests),("summary.json",summary)]:
    (O/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf8")
print("ARTIN_FOUR_MORE_SEMANTIC_AUDIT="+json.dumps(summary,ensure_ascii=False),flush=True)
if not all(tests.values()):raise SystemExit(2)
