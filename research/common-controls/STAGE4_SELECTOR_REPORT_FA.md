# اتصال هزینه و اجرا به انتخاب راهبرد — اجرای واقعی آزمایش مصنوعی

پاسخ به PR30 comment6657879433؛ این مرحله در نسخه پژوهشی اجرا شد و برنامه نصب‌شده تغییر نکرد.

## مسیر کد و نتیجه اتصال

مسیر قبلی: engine_bridge.execute → amin_mt5.experiments.run_experiment → research.evaluate_segment → strategy.plan/size_and_target → statistics/validation selection → ResearchLedger.

مسیر جدید: engine_bridge.evaluate_strategies → **research_engine/experiments.py، بازنگری پژوهشی همان runner/selector** → scenario_segment.evaluate_segment → strategy.plan/size_and_target و risk/learning موجود → execution_scenarios.replay → net metrics → rank → ResearchLedger موجود.

این صرفاً تست replay یک سفارش نیست: حلقه train/validation/holdout و انتخاب candidate به evaluator سناریویی وصل شده است. نسخه نصب‌شده amin_mt5.experiments عمداً تغییر نکرده؛ entry point پژوهشی جدید باید صریح فراخوانی شود. execute قدیمی برای بازتولید قبلی موجود است و همچنان هیچ مجوز promotion ندارد. فایل experiments_original.py.txt مبنای مقایسه کد قبل از بازنگری است. موتور مستقل قیمت/استراتژی از صفر نوشته نشده؛ strategy، risk، sizing، learning و adaptive_exit موجود بازاستفاده می‌شوند.

شش candidate اصلی بدون mock نیز روی ۳۲۰ کندل مصنوعی اجرا شدند: ۹۶ ردیف معامله در خروجی‌های TRAIN سناریوها (شامل تکرار سناریویی؛ نه ۹۶ معامله مستقل بازار). برای اثبات رفتار رتبه‌بندی، سه fixture با سیگنال و sizing کنترل‌شده از **همان runner/evaluator/rank/ledger واقعی** عبور کردند؛ نام breakout/rejection/retest در این fixtureها صرفاً شناسه است و نتیجه مالی راهبرد اصلی نیست.

## آزمون و نتایج

۶۰ PASS، صفر FAIL/ERROR/SKIP: ۱۹ تست جدید selector، ۳۲ regression مرحله قبل و ۹ integration bridge متاثر. اجرای اولیه fixture به علت قرارگرفتن TP زیر قیمت ورود در stress، ۹ خطای LEVELS داشت؛ fixture اصلاح شد، اعتبارسنجی LEVELS حذف یا ضعیف نشد. نتیجه نهایی در stage4-test-results.txt و stage4-results.json است.

در validation مصنوعی:

| fixture | بدترین net | نتیجه |
|---|---:|---|
| سود ظاهری مثبت، هزینه بالا | ‎-14.4 USD | حذف: NONPOSITIVE_WORST_CASE |
| TP و SL قابل لمس در یک کندل | None در unknown | حذف: UNKNOWN_COST_OR_PATH |
| پایدار در سناریوهای تعریف‌شده | +18.0 USD | فقط HYPOTHETICAL_SCENARIO_ONLY |

selected_candidate و verified_best همواره None هستند؛ فقط scenario_nominee برای بررسی فرضی وجود دارد. این ارقام هیچ ادعایی درباره Eplanet، بازار واقعی یا سودآوری retest نیستند. کمیسیون fixture برابر ۴۰ دلار/لات فرضی است و کمیسیون Eplanet محسوب نمی‌شود؛ کمیسیون صفر Standard طبق پاسخ تیکت قبلی مستند شده ولی داده هزینه تاریخی کامل نیست.

با swap=None حتی با assumed_swap=0، انتخاب متوقف شد. با spread ناموجود، خطا و FAILED در ledger ثبت شد و فراخوانی بعدی BLOCKED_FAILED بود. فراخوانی یکسان آزمایش معتبر REUSE برگشت. نتایج منفی حذف نشدند. فایل‌های selector-controlled-trace.json و selector-existing-strategies.json شامل آمار همه سناریوها، نمونه trace ورود/خروج و hash تمام ردیف‌های هر بخش هستند؛ trace کامل در ledger خصوصی محلی است.

## کنترل علمی

- train/validation/holdout زمانی ۵۰/۲۵/۲۵، embargo هشت کندل. fit تنها از train بسته‌شده؛ انتخاب فقط validation. تغییر عمدی holdout رتبه را تغییر نداد. baseline بدون معامله و breakout ثابت ثبت می‌شوند.
- سه سیاست stop_first/target_first/unknown در base و stress برای همه candidateها. unknown در برخورد مبهم net=None؛ sizing بعدی روی equity نامعلوم ادامه نمی‌یابد. بازشدن کندل آن‌سوی stop، تقدم stop را ثابت می‌کند و optimistic نمی‌تواند آن را با TP جایگزین کند.
- هزینه spread/slippage در fill است و دوباره کم نمی‌شود؛ commission جدا و swap جریان نقدی علامت‌دار است. swap این مرحله مقدار صریح سناریویی به‌ازای معامله است، **نه بازسازی نرخ/رول‌اور تاریخی**.
- spread شناور با quote هم‌زمان و receipt بررسی‌شده؛ quote دارای available آینده رد می‌شود. fixture quoteها مصنوعی‌اند. spread ابتدای کندل به Ask داخل کندل تعمیم تقریبی دارد و تمام نتایج ASSUMPTION باقی می‌مانند.
- دو exit policy صریح: adaptive_existing برای رفتار موجود و fixed_sltp برای آزمایش کنترل‌شده TP/SL با target خروجی sizing. سیاست در cache identity ثبت است؛ خروجی‌ها با فرض‌های متفاوت مقایسه قطعی نمی‌شوند.
- خبر در این entry point وارد مدل نشده و ورودی غیرخالی آن fail-closed است؛ ابزار news_at موجود برای اتصال آینده محفوظ است. ادعای مدل خبر یا ۱۱۱ اندیکاتور نداریم.
- hash داده، تمام کدهای evaluator/runner/ledger و dependencies اصلی، candidateها، cost/context، policy، split، seed، protocol، تفسیر زمان و نسخه fixture در شناسه اجرا هستند. invalid dataset/FAILED حق cache معتبر ندارد.
- رتبه‌بندی بر net بدترین سناریو منهای drawdown و حداقل تعداد معاملات است؛ بدون آزمون کافی یا معامله بازمانده، نامزد انتخاب نمی‌شود. این رتبه‌بندی گواهی آماری سودآوری نیست؛ تازگی سراسری holdout و بازبینی مستقل باقی‌اند.

## بازتولید و محدودیت محیط

در پوشه research/common-controls:

```text
python -X utf8 stage4_qa.py
```

وابستگی موجود ویندوز: C:/Users/Pixel/Documents/Amin-MT5-0.4.1/amin-mt5/src. مسیر در ENGINE از engine_bridge.py مشخص است. clone تنها بدون سورس amin_mt5 موجود، integration را اجرا نمی‌کند؛ این محدودیت پنهان نیست. SQLite محلی، داده خام بروکر و فایل‌های حساب در PR نیستند.

هیچ داده بازار دوباره دانلود نشد و هیچ بک‌تست مالی واقعی در این مرحله اجرا نشد. entry point فعلاً فقط SYNTHETIC_DIAGNOSTIC/SYNTHETIC_UTC می‌پذیرد. همه ۲۶۰ فاصله و نگاشت تاریخی همچنان UNKNOWN؛ final_year_validation=BLOCKED. مدل swap تاریخی، Tick کامل و تقویم رسمی بروکر هنوز موجود نیستند.

## رسید تیکت و گام بعد

پس از بررسی کل سابقه قابل مشاهده و نبود پیام تکراری، متن تأییدشده مالک فقط یک‌بار در تیکت **۲۰۷۸۵۲** ثبت شد: زمان نمایشی **1405/08/14 - 15:53:18**، وضعیت **pending support**. تیکت جدید ساخته نشد. رسید در Issue9 comment6657924868 ثبت شد؛ تصویر پاک‌سازی‌شده همراه این گزارش است. هیچ پاسخ تازه رسمی دریافت نشده؛ پایش تکراری قبلی فعال نشد.

گام بعد: بازبینی همین selector پژوهشی و شواهد آزمون؛ پس از دریافت اسناد، بررسی جدول DST/session/gap و هزینه تاریخی بدون حدس. اتصال داده بازار فقط پس از احراز gates مربوط قابل بررسی است. کابین، تقویم و پژوهش اندیکاتورها از صف قبلی حذف نشده‌اند؛ در این مرحله ادعای تکمیل آن‌ها نمی‌شود. هیچ معامله، نصب، main، Merge، تغییر ربات یا هزینه انجام نشده است.
