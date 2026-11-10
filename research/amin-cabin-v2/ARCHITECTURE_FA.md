# مرحله B — معماری اجرایی پیشنهادی؛ هنوز در محصول اعمال نشده

## مرزبندی و بازاستفاده

Windows همان WinForms/Workspace، میزبانی NativeTerminalPanel و lifecycle فعلی را نگه دارد. صفحات جدید پس از تأیید تک‌به‌تک پشت feature flag خاموش و adapter نمایشی اضافه شوند. نمونه فعلی HTML/CSS/JS ابزار بررسی UX است، نه جایگزینی فناوری برنامه یا اتصال WebView به موتور. Android کلاینت کنترل/مشاهده مجزا باقی می‌ماند؛ پرونده API/SDK بروکر برای موتور مستقل گوشی موضوع دیگری است.

سه مرز production پیشنهادی: نمایش فقط‌خواندنی، سرویس فرمان دارای مجوز، نگهبان مستقل دارای حق veto. نگهبان در UI یا وابسته به زنده‌بودن گوشی نباشد. قطع گوشی موتور Windows را نمی‌بندد؛ قطع broker/new ticks ورودی جدید را متوقف می‌کند. تنها حد پذیرفته‌شده و تطبیق‌شده سمت بروکر حفاظت سروری محسوب شود؛ در قطع، سلامت آن بدون شاهد UNKNOWN است. از کار افتادن process نگهبان باید executor را fail-closed کند.

## قرارداد پیشنهادی API (در mock هیچ endpoint فعالی نیست)

GET /v2/cabin/state پاسخ یک snapshot اتمی با schema_version، sequence، server_observed_utc، received_utc، account_kind (DEMO/REAL/UNKNOWN)، symbol دقیق، source_id غیرشخصی، terminal/broker_demo/engine/data_fresh/execution_armed و reason_codes بدهد. هر وضعیت evidence_time و TTL خودش را داشته باشد؛ زمان آینده، sequence برگشتی و JSON ناقص reject شوند. reference مناسب clock monotonic محلی برای elapsed و UTC برای journal؛ clock skew ظاهر شود، پنهان نشود.

```json
{"schema_version":1,"sequence":1,"source":"mock","symbol":"XAUUSD.st","account_kind":"UNKNOWN","terminal":{"state":"UNKNOWN","observed_utc":null},"broker_demo":{"state":"UNKNOWN","observed_utc":null},"engine":{"state":"UNKNOWN","observed_utc":null},"data_fresh":{"state":"UNKNOWN","age_ms":null},"execution_armed":false,"equity":null,"floating_pnl":null,"realized_net_pnl":null,"cost_spec":null,"protection":"UNKNOWN"}
```

GET /v2/decisions: decision_id، BUY/SELL/NO_TRADE، model_kind=RULES/TRAINED، model_id/hash/version، feature_schema_hash، data_window_end، reasons، uncertainty_method/value یا null، evidence provenance. confidence فقط score مدل و نه درصد برد؛ مدل نامعتبر/منقضی یا بدون قرارداد هزینه NO_TRADE.

POST /v2/commands فقط در فاز مجاز آینده: request_id یکتا، expected_sequence، proposal_hash، mode، issued/expires_utc، symbol، direction، volume_lots_decimal، SL/TP و policy_version. نقش/هویت/expiry/idempotency و guardها سمت سرور بررسی شوند. پاسخ decision=REJECTED/PENDING_APPROVAL/ACCEPTED_SIMULATION/ACKNOWLEDGED؛ ACK با FILLED یکی نیست. شناسه تکراری با payload متفاوت 409 و با payload برابر همان نتیجه ثابت برگردد؛ journal قبل از side effect به دیسک پایدار نوشته شود. نمونه صرفاً id را deduplicate می‌کند و durability/payload conflict را پیاده نکرده است.

GET /v2/reconciliation بر اساس request id و broker order/deal ids وضعیت UNKNOWN/PENDING/FILLED/REJECTED را بازسازی کند؛ پس از timeout هیچ retry ارسال کور انجام نشود. intent و fill جدا نگه داشته شوند. پاسخ ناقص یا نامطمئن execution_armed=false. endpoint جدید هنوز مجوز اتصال ندارد.

## حالت‌ها و حدود اختیار

| حالت | منشأ پیشنهاد | اختیار انسانی | شرط توقف |
|---|---|---|---|
| دستی | مالک | تأیید هر درخواست با پارامترهای ثابت | veto مستقل محافظ؛ unknown/cost/stale |
| نیمه‌خودکار | پیشنهاد معتبر سیستم | تأیید همان hash، expiry و پارامتر؛ تغییر نیازمند تأیید جدید | انقضای پیشنهاد یا تفاوت وضعیت |
| خودکار | سیاست محدود و مدل مصوب | اجازه scoped و زمان‌دارِ جدا، نه با انتخاب منو | هر guard نامعلوم/ناسالم؛ restart/reconnect بدون rearm |

انتخاب mode در UI هیچ‌گاه permission را تغییر ندهد. نمایش ساده در auto/semi حفظ شود، جزئیات در مرکز AI جدا و تحت اختیار قابل مشاهده است. STOP ورودی جدید را ممنوع و pendingهای هنوز ارسال‌نشده را لغو می‌کند؛ بستن موقعیت باز action جدا با اختیار مستقل است. rollback کد، معامله قبلی را برنمی‌گرداند.

## ریسک، حسابداری و بازگشت اتصال

هدف۳٪/release۶٪ conflict باز است. پیش از implementation، مالک باید مبنا (equity آغاز روز یا balance)، timezone روز، زیان باز+بسته+fees، deposit/withdraw adjustments و سیاست position باز پس از limit را تصویب کند. کوچک‌ترین null/NaN/infinite/invalid identity/currency/tick-value یا stale، رد. محاسبه حجم با decimal و tick_size/value و step/min/max واقعی؛ floor حجم به step، بررسی ریسک مجدد و رد اگر min lot از سقف بالاتر باشد. برای ابزار غیرخطی از روش P&L رسمی broker در محیط مجاز استفاده شود؛ contract=100 نباید به همه نمادها تعمیم یابد.

مثال صرفاً آموزشی: contract=100، حرکت۱۰، spread=.30 و commission roundtrip=8/lot؛ ۱lot ناخالص1000، هزینه38، خالص962 USD؛ .01lot ناخالص10، هزینه.38، خالص9.62. سوآپ/لغزش حذف شده‌اند و minimum commission unknown است؛ این نتایج نرخ واقعی بروکر/سود پیش‌بینی‌شده نیستند. قفل سود و trailing فقط ریسک/SL را تغییر می‌دهند؛ تنها fill بستن جزئی و کسر هزینه در ledger سود را realized می‌کند. volume باقی‌مانده و realized/floating جدا. نمونه بدون fill، realized=0.

reconnect → DISARMED → تطبیق intent/deal و snapshot تازه → بازبینی guardها → اجازه مستقل مالک. هیچ صف گوشی خودکار flush نشود. دوام journal، فایل snapshot و backup با hash و restore-test واقعی لازم است. backup حاوی راز رمزگذاری محلی و سیاست retention جدا؛ داده شخصی در GitHub ممنوع.

## نقشه صفحات و معیار قبولی مستقل

| صفحه / تصویر نمونه | حداقل کنترل/داده | معیار و وضعیت فعلی |
|---|---|---|
| ۱ نمای اصلی /01 | سرمایه، floating/realized، summary decision | UNKNOWN به صورت —؛ عدد ساختگی فقط در بخش برچسب‌دار. ساخته در mock |
| ۲ MT5 /02 | جایگاه host، وضعیت مستقل، مسیر diagnostics | عدم launch بدون دستور؛ چارت و خطای API همزمان قابل فهم. محل host فقط mock |
| ۳ معاملات /03 | سه حالت، تأیید، ارزیابی، تکرار، journal | بدون sender؛ تکرار id یک journal؛ رد unknown. ساخته در mock |
| ۴ ریسک /04 | conflict۳/۶، هزینه و حجم نمونه | دو سناریوی۱/.۰۱، null هزینه واقعی و جدایی realized. ساخته در mock |
| ۵ AI /05 | مدل/hash/دلیل/عدم قطعیت | model unknown، عدم ادعای trained/confidence-winrate. ساخته در mock |
| ۶ آزمایشگاه /06 | قطع/کهنه/unknown/reconnect/reconcile/reset | هیچ reconnect rearm نکند؛ نتایج inspectable. ساخته در mock |
| ۷ ارتباط /07 | نقش Windows/mobile، قطع گوشی | محافظ مستقل؛ «بدون اتصال» روشن. شبیه‌سازی فقط |
| ۸ ابزارها /08 | فهرست نیازهای اپ/شخصیت/موسیقی/تقویم | دکمه‌های ناتمام disabled و «بعداً». wireframe، قابلیت واقعی نیست |

RTL: بعدی به صفحه index+1، کلید چپ و swipe راست؛ قبلی کلید راست/swipe چپ. منو مستقیم، boundary بدون wrap، focus روی عنوان؛ فرم/چارت gesture را نمی‌دزدند؛ reduced-motion سیستم و گزینه دستی. slide کوتاه .22s. در موبایل منو افقی و کارت‌ها یک‌ستونه؛ آزمون touch واقعی Android و readers قبل integration لازم است. هر صفحه مستقل برای تأیید مالک عرضه می‌شود؛ approved=false برای همه.

## امکانات غیرمعاملاتی و امنیت

برنامه‌ها، شخصیت‌ها و ملودی store/API جدا از trading DB. owner/user هر دو داده خصوصی خود را می‌سازند؛ فقط owner موارد خودش را موردی عمومی می‌کند و لغو سمت سرور اعمال شود. اپ بومی فقط Intent رسمی همان دستگاه؛ نشست اپ خوانده/کپی نشود. + همیشه باقی، بدون سقف دلخواه، pagination و کمبود فضای واقعی. موسیقی چهار عنوان Issue8 فقط سلیقه تأیید شده؛ فایل/مجوز/انتساب/حقوق توزیع باید جدا احراز شود، پخش با فرمان کاربر، حلقه۴→۱ و مدیریت فقط مالک. لوگوی گزینه۴ و آیکون ساده‌شده بدون فایل و تأیید جدا وارد نصب نشوند.

اصل دسترسی حداقلی، هیچ secret داخل UI/URL/log، کوتاه‌عمر بودن session و nonce/replay protection، error redaction، rate-limit و payload validation. مدل AI اختیار مستقیم executor ندارد. دفاع محصول به obfuscation محدود نمی‌شود و هیچ حفاظت صددرصدی ادعا نمی‌شود.
