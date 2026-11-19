# ممیزی شواهد نسخهٔ ChatGPT — فقط‌خواندنی

مخزن: `aminzare121-maker/amin-faraz`؛ شاخهٔ معرفی‌شده: `artin-v13-under180-development`؛ مبنای دقیق این مقایسه: commit [`5983ef142ce51957160b3a976ef43888626ceed7`](https://github.com/aminzare121-maker/amin-faraz/tree/5983ef142ce51957160b3a976ef43888626ceed7).

این گزارش فایل‌های همان commit و وضعیت اجرای CI مربوط به آن را خوانده است. هیچ کد واردشده از نسخهٔ ChatGPT اجرا نشد، هیچ فایل آن تغییر نکرد و هیچ Merge انجام نشد. نتیجهٔ نسخهٔ Codex باید جداگانه، با رسیدهای اجرای خودش، در گزارش مقایسهٔ نهایی افزوده شود؛ این گزارش برتری یکی از دو نسخه را نتیجه نمی‌گیرد.

## جدول دامنهٔ شواهد

|معیار|آنچه در نسخهٔ مرجع وجود دارد|آنچه تأیید نشده است|
|---|---|---|
|کامپایل MetaEditor|سورس MQ5 و اسکریپت کامپایل/اعتبارسنجی رسید؛ CI مربوط به syntax و قرارداد رسید|کامپایل واقعی MetaEditor در Windows مالک، EX5 واقعی و هش آن|
|اجرای MT5 DEMO|جمع‌آورندهٔ طراحی‌شده برای DEMO و M15؛ راهنمای نصب دستی|اتصال واقعی Eplanet، اتصال به چارت و دریافت واقعی CSV در نسخهٔ مرجع|
|کندل بسته‌شده|کد V2 از `start_pos>=1` و `CopyRates` استفاده می‌کند؛ کندل صفر وارد دسته نمی‌شود|صحت خروجی واقعی همان نصب/بروکر با دریافت مشاهده‌شده|
|زمان سرور|epoch و `TimeToString` اصلی MQL5 در CSV ثبت می‌شوند|تبدیل قطعی ساعت بروکر به UTC و صحت offset/DST|
|تکرار/خرابی|اعتبارسنجی OHLC، ترتیب و شبکهٔ زمانی؛ prefix-hash و آزمون‌های ساختگی|کیفیت سری واقعی Eplanet در شرایط جاری|
|ادامه/بازیابی|V2 لنگر دقیق `iBarShift(...,true)` و oldest-first؛ V4 پردازش suffix؛ V5 رسید پیش از checkpoint|قطع شبکهٔ واقعی بروکر، خاموشی واقعی Windows و بازیابی مشاهده‌شدهٔ آن‌ها|
|آرشیو|V5 immutable receipts، قفل نوشتن، fsync/atomic write؛ V7 بازپخش همهٔ زنجیره و هش prefix|احراز مستقل منشأ بروکر با صرف فایل‌ها؛ مصونیت در برابر بازنویسی هماهنگ تمام فایل‌ها توسط مهاجم دارای دسترسی کامل|
|۱۳ مسیر|ساختار۱۳مسیره و نگاشت ارجاع؛ همهٔ مسیرها مسدود|تأیید معنایی مدرس، قواعد اجرایی نهایی و مجوز معامله|
|سرعت|CI ساختگی روی Windows/Ubuntu موفق؛ زمان اجرای job ثبت است|تفکیک پنج مرحلهٔ چرخهٔ واقعی دریافت/اعتبارسنجی/پردازش/ذخیره/ممیزی، یا سرعت ویدئو تا بایگانی|

## کامپایل و EX5: تفاوت مهمِ عنوان با آزمون واقعی

فایل [.github/workflows/artin-v13-mt5-compile-gate-v3.yml](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/.github/workflows/artin-v13-mt5-compile-gate-v3.yml) صریحاً `offline contract only` است. job لینوکس آزمون Python قرارداد رسید را اجرا می‌کند. job Windows اسکریپت PowerShell را parse می‌کند و مسیر `Z:\ARTIN_NOT_INSTALLED\metaeditor64.exe` را عمداً به‌عنوان MetaEditor ناموجود می‌دهد تا وضعیت `BLOCKED_NOT_COMPILED` و نبود EX5 کنترل شود. موفقیت این CI شاهدِ درست‌بودن توقف در نبود کامپایلر است؛ شاهد کامپایل واقعی نیست.

فهرست کامل tree همان commit با `truncated=false` بررسی شد؛ فایل با پسوند `.ex5` در tree پیدا نشد. این مشاهده به معنای نبود احتمالی EX5 خصوصی در رایانه‌ای دیگر نیست؛ صرفاً در شواهد مخزنِ بررسی‌شده EX5 واقعی دیده نشد.

[README V6](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/README_ARTIN_MT5_V6_FA.md) نیز می‌گوید رسید کامپایل قابل جعل است و تطبیق محتوای آن گواهی MetaEditor نیست. V6 برای stage کردن EX5 موجود طراحی شده؛ خودش ترمینال را باز یا EA را به چارت متصل نمی‌کند. پس وجود این ابزار جای رسید واقعی کامپایل/اجرای DEMO نیست.

## نتیجهٔ واقعی CI در commit مرجع

اجرای [`42868191728`](https://github.com/aminzare121-maker/amin-faraz/actions/runs/42868191728) با `headSha=5983ef142ce51957160b3a976ef43888626ceed7` واقعاً completed/success بود. دو job:

- `synthetic-file-integrity (ubuntu-latest)`؛ آغاز `2026-11-10T17:45:31Z`، پایان `17:45:38Z`.
- `synthetic-file-integrity (windows-latest)`؛ آغاز همان `17:45:31Z`، پایان `17:45:48Z`.

در هر دو، مرحلهٔ normal و مرحلهٔ `python -O` موفق بود. [workflow V7](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/.github/workflows/artin-v13-full-chain-file-audit-v7.yml) صریحاً `synthetic only` و مجموعهٔ آزمون V7/V5 است. زمان۷یا۱۷ثانیهٔ job شامل آماده‌سازی CI است و نباید مدت چرخهٔ واقعی MT5 یا پردازش ویدئو نامیده شود. این ممیزی کد آن آزمون‌ها را محلی اجرا نکرد.

فهرست artifactهای همین run از API بررسی شد: `total_count=0`. بنابراین این اجرا، فایل EX5 یا رسید اجرای واقعی دمو به‌صورت artifact تحویل نداده است؛ این مشاهده دربارهٔ تمام runهای تاریخ مخزن ادعا نمی‌کند.

رسیدهای درون مخزن نیز مرز را حفظ کرده‌اند:

- [رسید V2](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/tools-makhzan/courses/artin/ARTIN_V13_MT5_RECOVERY_V2_VERIFIED_RECEIPT_20261110.json): fixture ساختگی،۱۷ آزمون normal و optimized گزارش‌شده؛ `mql5_metaeditor_compilation_verified=false` و `mt5_eplanet_demo_runtime_verified=false`.
- [رسید V4](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/tools-makhzan/courses/artin/ARTIN_MT5_INCREMENTAL_V4_SYNTHETIC_RECEIPT_20261110.json): بوت‌استرپ۵کندل،۳کندل جدید،۲۴آزمون گزارش‌شده،۱۳مسیر و صفر معامله؛ compile/runtime/teacher semantics همگی false.
- [رسید end-to-end V5](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/tools-makhzan/courses/artin/ARTIN_V13_V5_SYNTHETIC_E2E_RECEIPT_20261110.json):۷۰کندل ساختگی با دسته‌های۵+۳+۶۲ و اجرای تکراری۰؛ سه رسید هش‌دار؛ `real_mt5_compiler_runtime_tested=false`.
- [رسید CI V5](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/tools-makhzan/courses/artin/ARTIN_V13_V5_VERIFIED_CI_RECEIPT_20261110.json): آزمون Windows/Ubuntu گزارش شده؛ قطع واقعی برق، کامپایل MetaEditor و اجرای واقعی Eplanet صریحاً false هستند. اعداد این رسیدها گزارشِ منبع‌اند؛ اجرای V7 بالا جدا از API خوانده و احراز شد.

## بازبینی محدودِ ساختار کد

[جمع‌آورنده V2](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/ArtinV13_ShadowProbe_RecoveryV2_DemoOnly.mq5) نوع حساب DEMO، پیشوند XAUUSD و M15 را کنترل می‌کند. در تابع `SafeAccountChart` کنترل صریح برابری نام سرور با Eplanet دیده نمی‌شود؛ نام سرور در نام فایل استفاده می‌شود. بنابراین شرط «فقط Eplanet» از این نگهبان به‌تنهایی تأیید نمی‌شود. این یک مشاهدهٔ استاتیک است، نه اثبات اجرای نامطلوب روی حساب دیگر. اطلاعات حساب از فایل‌های خصوصی خوانده یا در گزارش منتشر نشده‌اند.

[V4](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/artin_mt5_incremental_observer_v4.py) قبل از پردازش ردیف‌های تازه، تمام prefix قبلی را با SHA-256 کنترل می‌کند؛ برای context فقط دو ردیف پایانی قبلی را بازمی‌خواند. raw candle geometry با عنوان وضعیت هندسی ثبت می‌شود و `teacher_rule_verified/entry_signal/trade_allowed` false هستند. این طبقه‌بندی نهایی شک/اطمینان مدرس نیست.

[V5](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/artin_mt5_durable_outbox_v5.py) رسید را پیش از checkpoint پایدار می‌کند، برای چندنویسنده قفل دارد و orphan receipt را با replay منبع کنترل می‌کند. [V7](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/artin_mt5_evidence_audit_v7.py) طول زنجیره، ترتیب، هش رسیدها، prefix منبع و بازتولید گزارش هر رسید را کنترل می‌کند؛ بنابراین ممیزی محدود به آخرین رسید نیست. سقف ممیزی V7 برابر۱۰۰۰۰رسید است و زنجیرهٔ بزرگ‌تر نیازمند بررسی محدودشده اعلام می‌شود.

این سازوکارها برای سازگاری/دست‌کاری فایل‌های محلی شواهد نرم‌افزاری دارند، اما منشأ broker/DEMO را مستقل احراز نمی‌کنند. README V7 و خود خروجی `proof_scope` همین مرز را صریح دارند. ممیزی حاضر مرور امنیتی کامل همهٔ کد یا آزمون نفوذ نیست.

## ۱۳ مسیر و معنای مدرس

[نگاشت سایهٔ مدرس](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/artin_v13_teacher_to_mt5_shadow_map.py) ساختار۱۳مسیر و۲۴ارجاع را می‌خواهد، ولی برای تمام مسیرها وضعیت `BLOCKED_TEACHER_SEMANTICS_NOT_INDEPENDENTLY_VERIFIED` و `orders_allowed=false` تولید می‌کند. [گزارش عمومی](https://github.com/aminzare121-maker/amin-faraz/blob/5983ef142ce51957160b3a976ef43888626ceed7/tools-makhzan/courses/artin/ARTIN_V13_MT5_SHADOW_BRIDGE_PUBLIC_REPORT_20261110.json) نیز تعداد مسیرهای تأییدشدهٔ مدرس را صفر می‌گوید. وجود۱۳خانهٔ ساختاری برابر پوشش اجرایی۱۳استراتژی نیست؛ محتوای خصوصی۲۴ارجاع در این مأموریت بازبینی معنایی مستقل نشد.

## حکم مقایسهٔ قابل دفاع

در commit مرجع، توسعهٔ کنترل فایل، checkpoint، بازیابیِ ساختگی و ممیزی زنجیره، شواهد کد و CI دارد. کامپایل واقعی EX5 و اجرای واقعی نسخهٔ مرجع روی DEMO Eplanet در شواهد بررسی‌شده **تأیید نشد**. README V7 نیز صریحاً گفته اجرای DEMO روی رایانهٔ مالک هنوز از سوی ChatGPT اجرا/تأیید نشده است. نبود شاهد را شکست قطعی محصول نمی‌نامیم؛ همان «تأیید نشده» می‌ماند.

تعداد کندل‌های واقعی دریافت‌شده، زمان‌های پنج مرحله، نتیجهٔ قطع‌و‌وصل واقعی و تطبیق معنایی مدرس برای نسخهٔ Codex باید با گزارش‌های مستقل خودش مقایسه شوند؛ هیچ مقدار ساختگی یا موفقیتِ انتقال‌یافته از نسخهٔ دیگر در این ستون‌ها وارد نشده است.
