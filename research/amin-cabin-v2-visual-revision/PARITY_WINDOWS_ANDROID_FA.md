# برابری Windows و Android — قرارداد اصلاح‌شده

مبنای مقدم: Issue16 comment6655068199. دو محصول اصلی هم‌ارزش‌اند؛ هیچ مشتری برای استفاده از یکی ملزم به مالکیت دستگاه دیگر نیست. نسخه گوشی نمایشگر محدود نیست. برابری قرارداد/ظاهر با برابری عملیاتی اثبات‌شده فرق دارد.

| صفحه | ویندوز | اندروید | مشترک در موتور | شواهد تست | شکاف واقعی |
|---|---|---|---|---|---|
|۱ نمای اصلی|سرمایه، تصمیم، نمودار، وضعیت|همان قابلیت‌ها با چیدمان لمس|snapshot نسخه‌دار و زمان‌دار|هر دو قاب هشت صفحه و UNKNOWN؛ داده ساختگی|تازگی/latency عملیاتی هیچ‌کدام سنجیده نشده|
|۲ نمودار|host بومی MT5 پس از مجوز؛ چارت تحلیلی|چارت بومی/وب کنترل‌پذیر معادل؛ نه اجرای باینری MT5 ویندوز|فید و تصمیم یکسان، قیمت/زمان یکسان|نمودار مصنوعی؛ host واقعاً فعال نیست|Android chart adapter و Windows host integration آزموده نشده|
|۳ سفارش|دستی/نیمه‌خودکار/خودکار با اختیار|همان سه حالت و مدیریت پوزیشن/سفارش|authorizer، risk veto، command id، ledger|قاب گوشی همان controls؛ mock رد/duplicate دارد|موتور عملیاتی مشترک و احراز هویت تولیدی هیچ‌کدام وصل نیست|
|۴ ریسک|سقف، توقف، سود شناور/تحقق‌یافته|همان اختیارات و محاسبات|نگهبان مستقل، policy hash، ۳٪/۶٪ حل‌نشده|حسابگر فرضی، unknown veto|spec/cost واقعی و policy مصوب کم است|
|۵ AI|مدل، هش، دلایل، عدم قطعیت|همان مدل/نتایج/دلایل|یک نسخه artifact و audit|NO TRADE و UNKNOWN|edge، model معتبر و readiness اثبات نشده|
|۶ گزارش|ژورنال، خطا، reconciliation|همان گزارش و امکان بررسی|journal معتبر، sequence، idempotency|تست محلی قطع/reconnect بدون rearm؛ resilience قبلی|durability UI و sync عملیاتی دو OS آزموده نشده|
|۷ اتصال|مستقل از گوشی شخصی|مستقل از Windows شخصی|host مدیریت‌شده نامزد، کنترل واحد|قطع موبایل در mock اثر بر موتور ندارد|SLA، tenant isolation، failover و هزینه نامعلوم|
|۸ ابزارها|برنامه‌ها، شخصیت‌ها، ملودی، مجوز مالک|همان هدف؛ اجرای اپ با API همان OS|تنظیمات مجاز؛ مستقل از معامله|placeholder غیرفعال در هر دو|فایل/حقوق موسیقی، launcher دو OS، فایل اصلی لوگو کم است|

## نامزد معماری، نه تصمیم نصب

دو کلاینت کامل Windows و Android → API احراز هویت و فرمان مشترک → یک نگهبان و منبع حقیقت/دفتر → adapter مجاز بروکر. در صورت نیاز MT5، Windows می‌تواند در سمت سرویس باشد، نه الزام رایانه مشتری. هیچ VPS خریداری/ایجاد یا سرویس مستقر نشده است.

بازاستفاده: Windows C# و Android Java در snapshot ed4591a؛ از صفر بازنویسی نشوند. قرارداد typed/versioned برای snapshot و command. idempotency key از scope tenant/account + command_id، hash payload، policy/model version و expiry تشکیل شود؛ تکرار با payload متفاوت رد، نتیجه نامعلوم رزرو شود. exactly-once بروکر ادعا نمی‌شود. هویت دستگاه با هویت سفارش یکی نیست؛ دو کلاینت نباید یک عمل را دوبار اجرا کنند. قراردادهای pure و durable/fenced در mt5-review PR3 (72b51c4) مرجع‌اند؛ gateway تکراری اینجا ساخته نشده.

احراز هویت: token کوتاه، مجوز سمت سرور، ابطال نشست، ذخیره امن Credential Manager/Keystore؛ راز بروکر روی کلاینت نگهداری نشود. tenant/account isolation و quota باید آزموده شوند؛ checksum احراز اصالت نیست. TLS، امضای artifact، policy epoch، audit بدون راز و backup/restore لازم‌اند؛ هنوز در mock پیاده نشده‌اند.

## رفع مانع، هزینه و آزمون پیش از مجوز عملیاتی

| مانع | فناوری/کار پیشنهادی | هزینه و وابستگی | آزمون آفلاین بعدی و معیار |
|---|---|---|---|
|نمایش معادل چارت|Windows host موجود + Android chart component با قرارداد quote واحد|مجوز کتابخانه/داده و نفرساعت UNKNOWN؛ انتخاب با مالک|trace مصنوعی یکسان؛ OHLC/time/side برابر؛ stale هشدار هر دو|
|مشتری تنها-گوشی و تنها-ویندوز|سرویس مشترک مدیریت‌شده، adapter جدا و یک دفتر|Windows hosting/licence، broker automation terms، multiuser licence، SLA، backup، bandwidth همگی استعلام لازم|دو client actor مستقل؛ قطع/خروج یکی نباید state موتور را خاموش کند|
|فرمان همزمان و گم‌شدن پاسخ|reuse durable journal/fenced authority|طراحی identity و storage recovery؛ بدون هزینه واقعی فعلی|duplicate از هر دو دستگاه فقط یک logical attempt؛ UNKNOWN بدون resend و reconciliation|
|کیفیت عملکرد|timestamp server/receive/render/ack، clock skew، health هر جزء|بودجه latency/freshness/SLA هنوز تصویب نشده|report p50/p95/p99 و max، drop/reorder/delay/reconnect؛ سقف عددی قبل سنجش قفل شود؛ نبود عدد=قبولی نامعلوم|
|Android background و Windows exit|service-side guardian، اعلان push و fallback درون‌برنامه‌ای|مجوز push، محدودیت Android و شبکه/حریم خصوصی|app killed، screen locked، اینترنت قطع؛ هشدار delivery/ack تفکیک و retry غیرمعاملاتی|
|امنیت و چندکاربری|auth scopes، tenant boundary، replay/expiry/epoch|ممیزی و مدل تجاری/مجوز broker UNKNOWN|cross-tenant denial، revoked token، replay، restore؛ هیچ نمونه حساب واقعی وارد نشود|

خرید، نصب کلاینت، VPS، قرارداد سرویس/کتابخانه، حساب، معامله و تغییر main مجوز جدا می‌خواهد. طراحی/fixture غیرمعاملاتی در مجوز فعلی است. هزینه واقعی صفر خرج‌شده؛ قیمت ماهانه یا SLA حدس زده نشده. ضعف Windows و Android با اولویت برابر بررسی می‌شود.

## وضعیت اثبات

سه تست تازه فقط برابری فهرست قرارداد هشت صفحه، عدم الزام دستگاه دیگر و عدم ادعای readiness را کنترل می‌کنند. مرورگر گوشی Android واقعی نیست. اجرای same UI در دو عرض، اثبات background service، اعلان OS، latency شبکه، چندکاربری یا حفاظت بروکر نیست. همه موارد اخیر NOT_TESTED / UNKNOWN باقی‌اند.
