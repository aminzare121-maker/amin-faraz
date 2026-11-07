# ادامه A/B فرمان PR30 — ۵ نوامبر ۲۰۲۶

مبنا d52d28d و دستور6659248049؛ تغییر فقط پژوهشی. معیار A کامل نشده و BLOCKED است؛ مسیر B در حد synthetic end-to-end اجرا شده، نه گواهی مقایسه مالی معتبر.

## A — بازیابی و مهاجرت

چهار SQLite موجود در پوشه common-research فقط‌خواندنی inventory شدند (بانک اصلی، selector، backup و restored). قبل از آزمایش‌های تازه این مرحله:۱۳ردیف،۵run یکتا؛ نسخه‌های backup دوباره به عنوان پژوهش شمرده نشدند. **صفر exposure با بازه UTC و لحظه مواجهه کامل تأییدشده،۵ اجرای بالقوه NEEDS_REVIEW**. چهار run حالت VALID و یکی FAILED داشت؛ FAILED نیز دلیل اثبات عدم مواجهه نیست. checksum نتیجه‌ها در فایل خصوصی inventory موجود است. نام فایل/زمان ایجاد run یا شاخص۲۴۸کندل به‌تنهایی timestamp قابل‌اعتماد نیست. عدد۵ فهرست کامل همه آزمایش‌های دستگاه/تاریخ نیست؛ فقط دامنه چهار بانک اعلام‌شده است. تعداد مواجهه‌های خارج از این دامنه نامعلوم است.

exposure_migration.py از جدول exposure همان holdout_guard استفاده می‌کند؛ موتور/دفتر مرجع دوم نساخت. plan غیرخالی، وضعیت VERIFIED، UTC و منشأ می‌خواهد؛ ورودی واقعی مبهم مهاجرت نمی‌شود. manifest و hash، backup SQLite مستقل، تراکنش BEGIN IMMEDIATE، schema version و زنجیره نسخه افزوده شد. نوشتن همه رکوردها/manifest در یک تراکنش است. تکرار عین manifest REUSE، اختلاف یک run رد می‌شود؛ قطع قبل commit rollback می‌شود. checkpoint جداگانه checksum تمام exposureها و زنجیره را مقایسه می‌کند.

آزمون بازگرداندن snapshot قدیمی واقعاً فایل را جایگزین کرد و با checkpoint جدید رد شد؛ بازگرداندن هم‌زمان دفتر و checkpoint قدیمی قابل تشخیص نیست. anchor مقاوم مستقل تأمین نشده؛ **ROLLBACK_PROTECTION_UNVERIFIED، financial_gate=BLOCKED**. مهاجرت واقعی/ساخت دفتر خالی انجام نشد. هیچ داده خام یا بانک خصوصی بارگذاری نمی‌شود.

## B — کنترل تصادفی متصل به موتور موجود

مسیر واقعی: engine_bridge → runner موجود → scenario_segment → همان replay/cost برای نامزد و کنترل → metrics/rank → همان ResearchLedger. SPEC ثابت پنج seed1729،2718،31415،42017،65537 و بودجه۵ کنترل دارد؛ جهت فقط hash(seed,entry_time) است. تغییر seed در ورودی رد می‌شود؛ spec و فایل کنترل در fingerprint cache قرار دارند. طراحی قبل از اجرای fixture ثابت شد؛ این ثبت طراحیِ diagnostics است، نه گواهی preregistration مالی یا تازگی جهانی holdout.

کنترل مشروط به فرصت ورود علّی نامزد است: همان entry_time، lot، فاصله stop/target از entry و ریسک اولیه دلاری، همان horizon و policy و inputs هزینه. direction تصادفی است؛ stop/target حول قیمت ورودی سمت جدید قرینه می‌شوند. نتیجه کنترل مسیر خروج و هزینه خودش را از همان evaluator می‌گیرد. از exit_time آینده برای ساخت مدت مصنوعی استفاده نمی‌شود. adaptive موجود با همان تنظیمات اجرا می‌شود.

برای هر seed مسیر سرمایه جدا دنبال می‌شود. اگر سرمایه قبل ورود با نامزد برابر نباشد، مدت خروج متفاوت باشد، معامله باز بماند یا swap/path ناشناخته باشد، INCOMPARABLE است. همه trades/seeds حفظ می‌شوند؛ زیرمجموعه دلخواه تطبیق‌یافته انتخاب نمی‌شود. اگر هر مقایسه لازم ناقص باشد، نامزد امتیاز نمی‌گیرد. فقط در تطبیق کامل باید از **تمام** کنترل‌های ثابت در validation بهتر باشد؛ seed برنده انتخاب نمی‌شود. این سیاست conservative screen است، نه آزمون معنی‌داری یا تصحیح آماری تضمین‌شده چندآزمونی. آزمون بازار همچنان ممنوع است.

این conditional paired control یک portfolio تصادفی مستقل با ورودهای آزاد نیست؛ با اختلاف مسیر سرمایه یا مدت، سازگاری را جعل نمی‌کند. توسعه matching پیچیده‌تر یا matching روی نتایج آینده بدون پروتکل جدید مجاز نیست. baseline ثابت breakout و بدون معامله موجود حفظ شدند. holdout در انتخاب وارد نمی‌شود.

## نتیجه اجرای واقعی مصنوعی

سه fixture اصلی کنترل‌شده (فقط signal/sizing fixture؛ سایر مسیر واقعی) در بانک selector موجود ثبت شدند:

-۵۷۸ ردیف validation سناریویی،۲۸۹۰ ردیف کنترل پنج-seed؛ این‌ها معامله مستقل نیستند.
-۳۳۴ ردیف paired و۲۵۵۶ INCOMPARABLE؛ هیچ ردیفی برای بهترشدن نتیجه حذف نشد.
-هر سه نامزد BLOCKED؛ حتی retest با worst-case فرضی+۱۸دلار به دلیل عدم مقایسه منصفانه انتخاب نشد.
-scenario_nominee=None،verified_best=None؛ هیچ سودآوری بازار تأیید نیست.
-fixture فاقد spread واقعاً FAILED_RECORDED شد و منشأ SPREAD_UNKNOWN در بانک موجود است.
-run نهایی66121ec43b886035c7500c0dc86ab267b91b5c47c8197a7231a17a2c60f04499.

در بازبینی خروجی نخست، comparable در سطح ranking فقط یکسانی context را نشان می‌داد؛ با وجود کنترل نامعتبر می‌توانست true باشد. به context_comparable و comparable کل تفکیک شد. اجرای وابسته بعد اصلاح تکرار و نتیجه/سابقه اول حفظ شد (initial-summary،run176fa446…). این اصلاح بر امتیازها اثر نداشت؛ نمایش وضعیت را دقیق کرد.

## آزمون‌ها

**۵۴ تست متمایز PASS، صفرFAIL/ERROR/SKIP؛۱۹جدید و۳۵regression مرتبط**:
۱۰ migration،۹controls و۳۵selector/guard/protocol قبلی متاثر. لاگ نخست controls۸، regression۳۶(شامل یک تست تازه متغیر lot/duration)، سپس بازآزمایی۹controls پس از اصلاح نمایش comparable است؛ تکرارها شمارش مجدد نشده‌اند. تست‌های اولیه شکست ثبت‌شده نداشتند. اصلاح جاگذاری hook حین بازبینی کد، پیش از اجرای تست انجام شد.

پوشش: snapshot/manifest/ledger mismatch،missing،duplicate،interrupted transaction،دوwriter،timezoneنامعلوم؛ runner واقعی،replay seed،lot/initialrisk/context equality،duration/capital mismatch،UNKNOWNswap/path،holdout-invariance،cache reuse،خطای هزینه و ثبت FAILED. crash recovery سیستم‌عامل/قطع برق واقعاً آزموده نشده؛ آزمون interruption استثنای قبل commit بود. fixtureهای قدیمی بدون تغییر دوباره دریافت نشدند.

بازتولید: `python -X utf8 -m unittest test_exposure_migration test_matched_controls test_selector test_holdout_guard test_validity_carry_protocol.ProtocolTests -v`؛ integration نیازمند سورس محلی amin_mt5 قبلی است. stage7_qa.py اجرای جدید را فقط با هویت وابستگی همان بانک ثبت/بازیابی می‌کند. موجودی exposure قبل این اجراها snapshot شده؛ اجراهای تازه در بانک افزوده شدند و برای مهاجرت بعدی باید لحاظ شوند.

## باقی‌مانده

A: بازسازی تاریخ دقیق مواجهه و نماد/clock معتبر، پوشش بانک‌های دیگر، anchor مستقل؛ BLOCKED و بدون ادعای ضد دست‌کاری مالک. B: آزمون مستقل علمی بازار و روش matching عملی برای مسیرهای متفاوت، معنی‌داری/چندآزمونی، همگی ناتمام و مالی مسدود. داده یک‌ساله و۲۶۰gap UNKNOWN؛ درخواست Eplanet تکرار نشد. آرتین،کابین،تقویم،۱۱۱اندیکاتور،جارویس و سایر مأموریت‌ها محفوظ‌اند. هیچ معامله،نصب،Merge،تغییر ربات/main یا هزینه انجام نشد.
