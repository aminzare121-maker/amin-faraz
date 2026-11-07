# milestone B — بازاستفاده آزمایشگاه مسیر معامله

۲۱۸ آزمون قبلی واقعاً در کپی ایزوله اجرا شد: baseline۱۴۲ + D1۳۵ + D2۱۹ + D3۲۲؛ صفر failure/error/skip. source SHA256 همان `574ce39acbb7090cff21ba778637a77b2101e146641e446bf72282988e40c0fc`؛ ۳۲ فایل baseline قبل/بعد برابر. Python موجود استفاده شد، dependency نصب نشد. لاگ و نتیجه جدید در vendor/resilience/reports/resilience-lab قرار دارد. گزارش‌های baseline دیگر در vendor تاریخی و صرفاً برای hash binding‌اند، اجرای تازه نیستند.

ماژول‌های قبلی بدون تغییر از mt5-review PR3 commit72b51c49a38888a03d9b6455833086bcff196366 بازاستفاده شدند؛ ۴۹ فایل کپی‌شده پیش از اجرا با Git blob مرجع تطبیق داشتند. موتور اصلی یا داده CSV import نشد.

| مرحله قرارداد | شاهد موجود و اجراشده | شکاف |
|---|---|---|
|propose→veto→approval|tests/test_decision،test_authorization،test_integration|اعتبار درون فرایند مصنوعی، نه هویت بروکر|
|entry→UNKNOWN→reserve|test_execution،test_durable|رزرو risk/notional/margin؛ هیچ adapter واقعی|
|partial fill/close و هزینه|test_risk_money،test_durable،test_broker_contract|بدون fill واقعی؛ cost نامعلوم fail-closed|
|SL/trailing/خروج A/B/C|test_exits_time؛ گپ، latency، future/unfinished candle، stop proposed/ack/observed جدا|هیچ حفاظت سروری واقعی تأیید نمی‌شود|
|reconciliation/duplicate/STOP/reconnect|test_authority،test_journal،test_process_recovery|kill فرایند آزمایشی انجام شد؛ قطع برق سخت‌افزاری آزموده نشده|
|ledger realized/floating|money immutable ledger و duplicate payload conflict|هزینه دیرهنگام/بروکر باید با قرارداد جدا تطبیق یابد|

تکمیل شکاف کوچک: risk_matrix.py از همان money/risk استفاده می‌کند، موتور جدید نیست. ۱۰ آزمون تازه PASS. حجم‌های .01/.1/1 و contract100 فقط fixture هستند. ورود Ask4000.30، خروج Bid4009، spread.30 و commission رفت‌وبرگشت8/lot همگی فرضی‌اند. سود شناور خالص8.62/86.2/862؛ تغییرSL به تنهایی realized=0. بستن تأییدشده مصنوعی حجم.01/.05/.5، realized=8.62/43.1/431 و باقیمانده0/43.1/431؛ تکرار deal دوباره ثبت نمی‌شود. .01 زیر minimum به .005 تقسیم نمی‌شود.

break-even Bid فرضی4000.38 بعد هزینه net=0. خروج گپی فرضی3994 زیان -6.38/-63.8/-638 می‌دهد؛ stop تضمین سقف زیان نیست. جدول کامل reports/B-matrix.json. این اعداد نتیجه حساب یا راهبرد بازار نیستند.

تیکت207852، commission/tick-value واقعی و مجوز داده هنوز UNKNOWN؛ ورود واقعی BLOCKED، ریسک۳٪/۶٪ حل‌نشده. count تازه B برابر۲۲۸ (۲۱۸ reused +۱۰ matrix)؛ شمار scenario trace به شمار تست اضافه نشده است. تلاش نخست ماتریس۸تست بود، سپس دو کنترل break-even/gap افزوده و نسخه نهایی۱۰تست مجدداً اجرا شد؛ شمار تلاش‌ها جمع نشده است.
