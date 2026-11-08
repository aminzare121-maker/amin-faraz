"""Post-run report export only: never refit, tune or modify experiment outputs."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def main():
    a_path, b_path = [ROOT/"outputs.PRIVATE"/run/"summary.json" for run in ("run-003", "run-004")]
    a, b = [json.loads(p.read_text(encoding="utf-8")) for p in (a_path, b_path)]
    x, y = [{k: v for k, v in z.items() if k != "execution_seconds"} for z in (a, b)]
    if x != y:
        raise ValueError("Two complete runs differ")
    repro = [(p.parent/"reproducibility.sha256").read_text().strip() for p in (a_path, b_path)]
    if repro[0] != repro[1]:
        raise ValueError("Reproducibility hashes differ")
    public = dict(a)
    public["portfolio_results"] = [{k: v for k, v in row.items() if k != "daily_pnl"}
                                     for row in a["portfolio_results"]]
    public["reproducibility"] = {"canonical_hash": repro[0], "complete_runs": 2,
        "execution_seconds": [a["execution_seconds"], b["execution_seconds"]],
        "equal_except_elapsed_seconds": True,
        "model_files_sha256": [sha(p.parent/"models.PRIVATE.json") for p in (a_path, b_path)],
        "portfolio_files_sha256": [sha(p.parent/"portfolios.PRIVATE.json") for p in (a_path, b_path)]}
    public["trial_history"] = {"unique_model_fold_condition_trials": 72, "portfolio_cases_per_run": 45,
        "final_repeat_runs": 2, "model_fit_calls_in_final_complete_runs": 144,
        "earlier_preserved_runs": ["run-001", "run-002"], "total_complete_run_fit_calls": 288,
        "previous_external_trials_already_seen": 40, "new_hyperparameter_searches": 0,
        "hypotheses_contract_commit_before_first_outcomes_local": "d45f25919a18f1d64a0dc1bc7d0ac57a0a214dbe",
        "source_history": "0.1.0 run001/002 preserved. After those, a causal Tehran-midnight guard reset bug was fixed without changing thresholds, model, costs or policy; regression added; 0.1.1 run003/004 are authoritative repeat pair.",
        "synthetic_verification_history": "Initial30 tests had2 erroneous-DD-fixture failures; fixture corrected to actual risk-sized volume, assertions retained. Final34 tests passed including Tehran midnight regression."}
    # Public export never contains fitted coefficients, raw OHLC or trade rows.
    text = json.dumps(public, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    if any(s in text for s in ("C:\\Users\\", "C:/Users/", '"weights":', '"entry_price":', '"exit_price":')):
        raise ValueError("Unsafe public report export")
    reports = ROOT/"reports"
    (reports/"aggregate-results.json").write_text(text+"\n", encoding="utf-8")
    rows = a["portfolio_results"]
    primary = [r for r in rows if r["quality"] == "strict" and r["scenario"] == "base"]
    lines = ["# نتیجهٔ واقعی آزمایش آفلاین AI — توسعهٔ گذشته‌نگر با فرض‌های پژوهشی", "",
        "**نتیجه: مزیت سودده و قابل تأیید AI اثبات نشد؛ هیچ arm دارای معامله در سناریوهای اجراشده net مثبت نداشت.** مدل‌ها در بعضی شرایط کمتر معامله و کمتر زیان کردند؛ عدم معامله B0 نتیجه بهتری داشت. این آزمون، سود واقعی/کارایی حساب یا آزمون تأییدی مستقل نیست.", "",
        "دو اجرای نهایی کامل نسخه۰٫۱٫۱ با کد/داده ثابت، هرکدام۴۵portfolio و۷۲fit مدل، به‌ترتیب "+str(a["execution_seconds"])+" و "+str(b["execution_seconds"])+"ثانیه طول کشیدند. هر۷۲مدل در هر اجرا fit شدند؛ صفر خطای اجرایی یا foldِ فاقد مدل. ۳۴تست مصنوعی پاس شد. دو اجرای قبلی۰٫۱٫۰ حفظ شدند؛ پس از کشف و اصلاح bugمرزروزتهران، جفت اجرای نهایی تازه انجام شد. هیچ threshold/هزینه/مدل/سیاست به‌خاطر نتیجه انتخاب نشد. هر۴fold توسعه قبلاً دیده‌شده و تاریخ ارزیابی مشترک `2026-07-01..2026-11-03` است.", "",
        "## جدول اصلی: strict/base", "",
        "همهٔ دلارها فرضی‌اند: equityآغاز۱۰هزارUSD، contract100 فرضی، riskسفارش۰٫۲۵٪/DDروزانه۲٪/کل۸٪، TP2R/timeout4h. هزینه پایه spread.50USD/oz، commission10USD/lotرفت‌وبرگشت، slip.20هرطرف، swap0فرضی، latency15minپس ازclose. این‌ها specEplanet یا سیاست عملیاتی مالک نیستند؛ margin/liquidity مدل نشده‌اند.", "",
        "| arm | سیگنال | معامله | setupبدون معامله | netUSD | expectancyUSD | PF | MDD% با MTM محافظه‌کارانه | بدترین روزUSD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|" ]
    for r in primary:
        m = r["metrics"]
        lines.append(f'| {r["arm"]} | {m["n_signals"]} | {m["trades"]} | {m["no_trade"]} | {number(m["net_pnl"])} | {number(m["expectancy"])} | {number(m["profit_factor"],3)} | {number(m["max_drawdown_pct"],3)} | {number(m["worst_day"])} |')
    lines += ["", "ستون setupبدون معامله = سیگنال‌های arm منهای معاملات؛ شامل overlap/ریسک/آستانه/expiry است و همهٔ کندل‌های بدونsetup نیست. B0 اصلاً setupتولید نمی‌کند و در تمام کندل‌ها عدم معامله دارد؛ صفر این ستون به معنی عدم وجود تصمیم no-trade نیست. شمار eligibility/exclusion روی کل۲۹۲۳۴bar در JSON کامل آمده است.", "",
        "M1/M2 فقط فیلتر ورود روی B1 هستند؛ جهت/SL/TP/خروج را یاد نگرفته‌اند. هر۴fold مدل trained غیرnull و calibrator جدا داشت؛ بنابراین کاهش فعالیت ناشی از آستانهٔ ثابت و داده است، نه fallbackمدل غایب. ۶ و۴معامله درbase برای ادعای expectancyپایدار کافی نیست. در کیفیت‌هایinclusive، مدل‌ها۰معامله دادند؛ این مساوی B0 است، نه شاهد سوددهی AI.", "",
        "## net هر fold در strict/base", "",
        "| arm | WF1 | WF2 | WF3 | WF4 |", "|---|---:|---:|---:|---:|"]
    for r in primary:
        lines.append("| "+r["arm"]+" | "+" | ".join(number(r["fold_daily_net"][f"WF{i}"]) for i in range(1,5))+" |")
    lines += ["", "## تمام حساسیت‌های ازپیش‌ثبت‌شده", "",
        "base/high_cost/delayed همگی هزینه‌دارند؛ دو کیفیتinclusive نیز در جدول هستند و نتیجه‌ای انتخاب/پنهان نشده است. در high_cost،spread/fee/slip دوبرابر وswapفرضی۵USD/lot/night است؛delayed تأخیر۳۰دقیقه وswap۵ دارد. تغییر کیفیت، تقویم واقعیsession را تأیید نمی‌کند.", "",
        "| کیفیت | هزینه | arm | معاملات | netUSD | MDD% |", "|---|---|---|---:|---:|---:|"]
    for r in rows:
        m = r["metrics"]
        lines.append(f'| {r["quality"]} | {r["scenario"]} | {r["arm"]} | {m["trades"]} | {number(m["net_pnl"])} | {number(m["max_drawdown_pct"],3)} |')
    lines += ["", "## اختلاف با B1 و عدم قطعیت", "",
        "bootstrap جفت‌شده بر۱۲۵روز تقویمی مشترک با zero-days، بلوک۱/۵/۱۰روز و۱۰۰۰تکرار انجام شد. برای بلوک۵روز:", "",
        "| arm strict/base | اختلاف net با B1،USD | CI95% اکتشافی اختلاف کل،USD |", "|---|---:|---:|"]
    for r in primary:
        if r["arm"] in ("M1", "M2"):
            p = next(v for v in r["paired_difference_vs_B1"] if v["block_days"] == 5)
            lines.append(f'| {r["arm"]} | {number(p["total_net_delta"])} | [{number(p["total_delta_ci95"][0])}, {number(p["total_delta_ci95"][1])}] |')
    lines += ["", "CIاختلاف مثبت با B1زیان‌ده، اثبات سود مثبت مدل یا برتری بر B0 نیست. قدرت/حداقلاثر آزمون تأییدی تازه قفل نشده؛ ۶/۴معاملهٔ مدل و دادهٔ قبلاً دیده‌شده، تفسیر تأییدی را نمی‌پذیرند. net همهٔ۴۵case با period_net برابر بود و post_end_pnl=0؛ اختلاف CI با همان جریان روزانه سازگار است.", "",
        "## کیفیت، بازتولید و محدودیت", "",
        "strict از۲۹۲۳۴bar تنها۷۳۴۵bar واجد شرایط داشت:۱۶۷۶۰به‌خاطرflat درگذشته۶۴bar،۳۴۰۲gap،۱۶۶۴proxyآخرهفتهUTC و۶۳warmup رد شدند. این ردها در مشتق/منطق causalاست؛ هیچ ردیف اصل حذف/پر/بازنویسی نشد. inclusive-weekdays۲۴۱۰۵ وinclusive-irregular۲۹۱۷۱bar واجدشرایط داشتند. کیفیت واقعی session درهرسه نامعلوم است.", "",
        "اصلCSVهمچنان SHA256 `"+a["data"]["sha256"]+"` دارد؛ بازه364روزتقویمیِ شبکه و فاقدvolume/Ask/spreadاست. منبع/حق/session تأییدنشده‌اند. source/contract در حین دو اجرا تغییر نکردند و socket/process audit guard فعال بود. هیچ داده جدید،dependency،حساب،MT5،Vault،سفارش یاpromotion به موتور استفاده نشد.", "",
        "هش بازتولید دو اجرا: `"+repro[0]+"`.", "",
        "خطای آموزش/اجرا۰؛ در ساخت آزمون مصنوعی اولیه۲assert به‌دلیلfixtureاشتباه DD failedشد:fixtureحجم.1فرض‌می‌کرد ولیsizingحجم.05می‌داد؛ fixtureباافت intrabarکافی اصلاح شد، نهimplementationبرایpass. سپس۳۳تست قبل از داده پاس شد. پس از دو اجرای۰٫۱٫۰، اشکال مستقل resetguardدرتصمیمی‌که‌دقیقاًنیمه‌شب‌تهران‌است پیدا و با regression۳۴ام اصلاح شد؛ دو اجرای تازه با منطق ثابت۰٫۱٫۱ انجام شدند. نسخه‌های قبلی حذف نشدند؛ هیچ threshold/هزینه/سیاست برای بهترکردنP&Lعوض نشد.", "",
        "[خلاصهٔ عددی کامل، hashمدل‌ها،C/V/E metrics،همهtrialها](aggregate-results.json) · [لاگ تست](synthetic-tests.log) · [اجرای نهایی اول](run-003.log) · [تکرار نهایی](run-004.log) · [قبلی۱](run-001.log) · [قبلی۲](run-002.log). مدل/وزن وtrade/privatepathمنتشرنشده‌اند. بازتولید نیازمندCSVمجاز جداگانه است.", "",
        "**نتیجهٔ اجرایی:** در این نسخه و فرض‌ها، پیشنهاد ارتقا یااتصال دمو نداریم. مسیر بعد رفع provenance/specو بررسی فرض‌های داده/label/هزینه در بازبینی است؛ تغییر آستانه برای زیبا کردن همیننتیجه انجام نشد. فرض سوددهیِ این دو فیلتر در این آزمایش تأیید نشد؛ این، حکم ناممکن‌بودن همهAIها نیست."]
    (reports/"RESULTS.fa.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps({"exported_cases": len(rows), "reproducible": True,
                      "aggregate_bytes": len(text.encode()), "result_bytes": (reports/"RESULTS.fa.md").stat().st_size}))


if __name__ == "__main__":
    main()
