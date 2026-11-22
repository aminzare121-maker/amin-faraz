# درگاه رسمی پرداخت فروش هوش امین — وضعیت بدون ادعای تسویه

- مشتریان اندروید از **Google Play Billing** خرید می‌کنند؛ گوگل مسئول پردازش وجه است.
- این Worker فقط رسید اشتراک را **از Google Play Developer API واقعی** بررسی می‌کند و نتیجه معتبر را به حساب همان خریدار وصل می‌کند. رسید دستگاه به‌تنهایی معتبر نیست.
- در `/billing/verify` باید `Authorization: Bearer amin_...`، متن JSON با `purchase_token` و شناسهٔ خرید متناظر وجود داشته باشد. مقدار `obfuscatedExternalAccountId` در خرید Google Play باید SHA-256 کامل همین کلید حساب باشد. هر مشتری کلید امن جدا دارد و کلید او نباید در GitHub یا کد APK ذخیره شود.
- استعلام فقط اشتراک ACTIVE، GRACE_PERIOD و CANCELED دارای تاریخ انقضای آینده را می‌پذیرد؛ PENDING، ON_HOLD، PAUSED و EXPIRED رد می‌شود. رسید فقط یک‌بار به یک حساب مشخص تعلق دارد، و دادهٔ خام رسید در پایگاه ذخیره نمی‌شود.
- گزارش درآمد و مبلغ واقعی تسویه فقط از **Google Play Console** استخراج می‌شود. این کد هیچ مبلغ فروش یا موجودی جعلی محاسبه نمی‌کند و هیچ وجهی در Google Pay نگه نمی‌دارد.
- گوگل معمولاً درآمد را حدود میانهٔ ماه بعد به **حساب بانکی احراز هویت‌شدهٔ همان فروشنده** می‌پردازد. گوگل سهم تو و ناشر دیگر را خودکار تقسیم نمی‌کند. اگر ناشر قانونی شخص دیگری باشد، قرارداد و سازوکار تسویهٔ جدا لازم است.

## راه‌اندازی در حساب فروشنده واجد شرایط (هنوز انجام‌نشده)
1. احراز هویت حقیقی و محل کسب‌وکار در کشور مجاز، حساب بانکی قابل تأیید، Play Console و قرارداد Google Payments تکمیل شوند. VPN، کارت خرید مجازی یا معرفی نشانی صوری جایگزین مدارک نیست.
2. پکیج `com.amin.support.mobile` را در همان Play Console ثبت و اشتراک `amin_support_monthly` و قیمت را با تصمیم مالک بسازید. برنامهٔ فعلی هنوز خرید درون‌برنامه‌ای را فعال نمی‌کند.
3. به حساب سرویس Google Cloud دسترسی حداقلی Play Developer API برای برنامه بدهید؛ JSON آن را فقط به‌صورت Cloudflare secret با نام `PLAY_SERVICE_ACCOUNT_JSON` ثبت کنید؛ نه فایل عمومی و نه کد برنامه.
4. D1 ایجاد کنید، `wrangler.toml` را با شناسهٔ واقعی D1 تکمیل کنید و `db/schema.sql` را اجرا کنید.
5. بعد از احراز فروشنده و آماده‌شدن محصول، `AMIN_MERCHANT_READY=1` تنظیم شود و Google Play test purchases با Play Console License Testing و دستگاه واقعی بررسی شوند.
6. تنها پس از اتصال کلاینت Billing Library، آزمون استعلام روی Google، ارتباط واقعی مدل و آزمون شبکه مقصد، فروش عمومی فعال شود.

**این ماژول برای اضافه‌شدن به موتور هوش امین است، نه استقرار یا فروش کامل.** در حالت فعلی flag فروش ۰ است و همهٔ درخواست‌های فعال‌سازی رد می‌شوند. GitHub Actions فقط آزمون قوانین، نه خرید واقعی و نه دریافت واقعی سود را اجرا می‌کند.

اسناد رسمی:
- https://developer.android.com/google/play/billing/security
- https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptionsv2/get
- https://support.google.com/googleplay/android-developer/answer/7161440
- https://support.google.com/googleplay/android-developer/answer/9306917
