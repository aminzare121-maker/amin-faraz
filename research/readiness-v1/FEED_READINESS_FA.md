# آمادگی ورود داده پس از مجوز — بدون دریافت داده

تیکت207852 وابستگی بیرونی است؛ پاسخ فنی/مجوز معتبر در این بسته وارد نشده. ابزار این مرحله فقط bytes مصنوعی در حافظه را می‌سنجد و هیچ فایل CSV/شبکه/بروکر را نمی‌خواند. no-data/no-trade/no-fit برای داده واقعی برقرار است؛ حتی status=VERIFIED ادعایی در metadata به خودی خود مجوز نمی‌دهد.

## قرارداد ورودی آینده

هویت: schema_version، feed_id/vendor/server/account-type بدون شماره حساب، exact symbol، instrument/contract/currency، acquisition tool/version/config، تاریخ اخذ، بازه درخواست و بازه واقعی، source receipt با اطلاعات حساس حذف‌شده. original-byte SHA256 و size قبل هر decode؛ hash خروجی تبدیل با chain ورودی/کد/config جدا. فایل خام immutable و copy-on-write؛ overwrite ممنوع. hash هویت است، نه اعتبار منشأ/حقوق.

مجوز: مدرک کتبی مشخص برای دریافت، ذخیره خصوصی، تحلیل/آموزش، مدت نگهداری، محدودیت انتشار/انتقال/حذف و دامنه demo/real؛ evidence id و تاریخ/نسخه. بررسی مالک/بازبین لازم است؛ بولین یا نام فایل جای سند حقوق نیست.

Tick: event timestamp با واحد و precision، available_at/receive_at، sequence یا شناسه منبع برای tickهای دارای زمان مساوی، bid و ask جدا، حجم/نوع در صورت موجود؛ bid<=ask، اعداد Decimal متناهی، duplicate exact از correction و quote جدید با timestamp یکسان تفکیک. عدم وجود Ask با spread امروزی پر نشود.

M15: bar_open UTC، bar_close=open+900s، بازه نیمه‌باز، available_at>=close، price_side=BID/ASK معلوم، OHLC مثبت و low<=open/close<=high. close همان کندل تضمین قیمت entry نیست. candle unfinished برای تصمیم ممنوع؛ timeframe بالاتر تنها پس از بسته‌شدن. تجمیع bid و ask جدا با همان session و original-tick hash. bar timestamp مبهم → UNKNOWN.

زمان: timezone/offset schedule تاریخ‌دار بروکر، DST fold/gap صریح، calendar نسخه‌دار جلسه/تعطیلات. UTC عددی به معنی احراز ساعت منبع نیست. پوشش داده نسبت به expected open-session slots سنجیده شود؛ observed، documented_closed، missing_open، unknown جدا. flat OHLC خودکار داده خراب/تعطیلی نیست. هیچ gap با forward-fill یا قیمت مصنوعی پنهان پر نشود. snapshot validator قبلی PR3 و broker_contract temporal قبلی مرجع‌اند، دوباره ساخته نشده‌اند.

هزینه: commission per-side/roundtrip/minimum و currency، spread تاریخی BidAsk، tick_size/value و conversion، swap long/short/mode/triple-day، slippage/latency/fill assumptions و minimum/freeze/stop levels، volume min/max/step/limit، contract، margin/account currency. برخی مقادیر در مشاهده قبلی (contract100، min/step.01) ثبت شده‌اند؛ این به معنی کامل‌بودن grid/cost یا تأیید حقوق نیست. نامعلوم‌ها UNKNOWN، نه صفر.

## سناریوهای پاسخ بروکر

| پاسخ کتبی | اقدام پیشنهادی پس از بررسی | وضعیت فعلی |
|---|---|---|
|مجوز مشخص و پوشش/هزینه کافی|ثبت evidence و بازه/هش/سشن؛ طرح دریافت محدود با مجوز جدا، سپس QA؛ holdout تازه قفل شود|بدون دانلود/fit در این بسته|
|اجازه فقط مشاهده یا دریافت ناکافی|حقوق ذخیره/تحلیل روشن شود؛ gap/Ask/session ناکافی به‌عنوان مانع حفظ؛ منبع جایگزین فقط با مجوز خودش|BLOCKED|
|دریافت/تحلیل ممنوع|از آن منبع استفاده نشود؛ raw جدید دریافت نشود؛ منبع قانونی جایگزین برای تصمیم مالک پیشنهاد شود|BLOCKED|
|حقوق روشن ولی commission/tick-value/session مجهول|هزینه/valuation معتبر درخواست شود؛ فرضیات فقط fixture؛ نتیجه بازار معتبر صادر نشود|BLOCKED|
|پاسخ مبهم/عمومی یا فقط demo≠real|ابهام و دامنه تعمیم ثبت؛ هیچ استنتاج به حساب واقعی|BLOCKED|

## dry-run محدود اجراشده

feed_contract.py یک QA کوچک قرارداد است، نه ingestion production یا جایگزین validator قبلی. فقط SYNTHETIC_ONLY + IN_MEMORY_FIXTURE، timezoneUTC/sessionمصنوعی؛ tickهای fixture زمان یکتا دارند. tick واقعی با timestamp مساوی نیازمند sequence/correction contract است و در این QA ساده پذیرفته نمی‌شود. schema ماشین در FEED_SCHEMA.json و وضعیت واقعی نامعلوم در feed-readiness-unknown.json.

۱۹ تست PASS؛ دو tick ساختگی، hash پیش/پس برابر. آزمون‌های منفی: scope واقعی پیش از parse رد، hash متفاوت، زمان/session نامعلوم، تکرار/وارونگی، crossed/NaN، bool timestamp، empty، OHLC، کندل ناتمام، price-side نامعلوم، gap و ستون اضافی. self-declared VERIFIED هم real_data_authorized/fit/trade را true نمی‌کند. این تست‌ها احراز مستقل حقوق یا provenance نیستند.
