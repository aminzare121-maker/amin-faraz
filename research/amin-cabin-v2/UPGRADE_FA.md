# مرحله D — ارتقای تدریجی پیشنهادی، بدون اجرا در نصب

| اولویت | بازاستفاده | اصلاح لازم | در انتظار |
|---|---|---|---|
| ۱ | Workspace و TerminalSummary | snapshot مشترک freshness/timeout، حالت‌های مستقل | تأیید صفحه۱/۲ و binding source→binary |
| ۲ | OwnerForm status و alert | پاک‌کردن عدد کهنه، زمان آخرین موفقیت، retry محدود با backoff | قرارداد API و تست integration مجزا |
| ۳ | risk/execution/audit | نگهبان مستقل، idempotency durable، reconcile fail-closed | تصمیم۳٪/۶٪، day/basis، هزینه/نماد واقعی |
| ۴ | manual/auto panels | selector سه‌حالته بدون انتقال permission؛ تأیید hash+expiry | تأیید صفحه۳ و سیاست هر mode |
| ۵ | StrategyReviewPanel | identity/hash/uncertainty و دلیل NO TRADE | مدل/استراتژی واقعاً معتبر؛ انتخاب۱۲ اندیکاتور |
| ۶ | Android client/OwnerExternalApps | state مشترک، کنترل کم‌اختیار و حفظ صفحه | تست دستگاه و مجوز اتصال، نه استقلال فرضی موتور |
| ۷ | navigation/stores جدا | اپ‌ها/شخصیت‌ها/ملودی/تقویم | فایل لوگو/حقوق موسیقی و انتشار موردی |

گام‌ها: ابتدا همین نمونه/هرصفحه بازبینی؛ سپس پس از مجوز جدا branch اصلاح کوچک برای همان صفحه، تست واحد و قراردادی، build ایزوله با binding هش، امضای خروجی و backup نصب، نمایش آفلاین نسخه مالک، و فقط بعد از مجوز جدید integration با دمو. هیچ مرحله خودکار به REAL یا نصب/merge منتهی نمی‌شود. هر مرحله manifest version/schema/config hash و forward/backward compatibility داشته باشد.

Rollback: قبل از نصب آینده خروجی و config سالم قبلی با هش حفظ شود؛ feature flag پیش‌فرض خاموش؛ migration ابتدا copy و validation، نه rewrite تنها نسخه. در failure flag خاموش و نسخه قبلی به روش atomic بازگردد. restore database باید بر نسخه کپی آزموده و گزارش شود؛ rollback نباید intent مبهم یا فرمان قدیمی را دوباره ارسال کند. معامله انجام‌شده با rollback قابل خنثی‌کردن نیست.

معیار توقف: mismatch هویت یا هش، نقص قرارداد/schema، stale/unknown، نبود clock قابل اعتماد، رفتار متفاوت با snapshot، خطای ACL، duplicate اثرگذار، reconnect دارای rearm، عدم بازیابی backup، رد/ابهام مجوز داده یا نیاز به دسترسی بیشتر. معیار قبولی مرحله اتصال آینده: تست قطعی مستقل fail-closed، journal durable، replay/no duplicate، تطبیق معامله/هزینه، UI عدم عددسازی، trace sanitization، تأیید جدا مالک و حدود demo روشن.

آنچه اکنون تحویل می‌شود ممیزی، معماری، ۸صفحه نمونه و آزمون mock است. رفع قطعی خطای API نصب، نگهبان production، ledger بروکر، پایش واقعی وضعیت و اپ نهایی ساخته یا تأیید نشده‌اند. ادامه کابین وابسته به پاسخ تیکت نیست؛ هزینه‌ها تا پاسخ معتبر UNKNOWN می‌مانند. کار ارتین در گفت‌وگوی مستقل تغییری نکرده و این بسته هیچ منبع مشترک آن را ویرایش نمی‌کند.
