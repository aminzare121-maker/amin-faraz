# مرحله صفر — موجود / قابل استفاده / شکاف واقعی

مبنا ۵ نوامبر ۲۰۲۶. فقط اسناد، کد و تست مصنوعی خوانده شده؛ CSV تاریخی باز یا پردازش نشده است.

| منبع ثابت | موجود و قابل استفاده | شکاف این مأموریت |
|---|---|---|
| faraz PR2 e9ccf7d | snapshot تحلیلگر، نقص انتخاب روی test/واحد زمان ثبت‌شده | مرجع تاریخی، اجرا نمی‌شود |
| faraz PR3 30448d0 | validator ساختار/hash/overwrite، ۲۸ تست تاریخی، مجوز مالی false | قرارداد ورودی آینده و gate مستقل؛ validator از نو ساخته نمی‌شود |
| faraz PR11 2dc3a46 | simulator مشترک و paired_bootstrap، ۳۴ تست تاریخی | عدم edge؛ قرارداد علمی تازه بدون fit واقعی |
| faraz PR12 d18f2b8 | کنترل تصادفی past-C و ۳۸ تست تاریخی؛ exposure توصیفی | expected activity مساوی، تضمین exposure مساوی نیست. fixture دقیقِ بودجه مواجهه قبل outcome اضافه می‌شود |
| faraz PR13 f2e26fd | منشأ/حقوق/session ناقص و منابع مستند | دریافت داده ممنوع؛ no-data/no-fit تا evidence |
| mt5 PR2 7943e1d | volume grid، هزینه/partial ledger، exits A/B/C، UNKNOWN reserve، ۱۴۲ تست | بازاستفاده بدون بازنویسی؛ ماتریس حجم .01/.1/1 و تفاوت mark/close با fixture |
| mt5 PR3 72b51c4 | journal/recovery/STOP/fencing/contracts؛ مجموع۲۱۸ تست | آزمون مجدد همین pure suite در کپی ایزوله؛ هیچ adapter تازه لازم نیست |
| mt5 PR4 ed4591a | snapshot واقعی risk/execution/finance؛ قفل سود توسعه با release متفاوت | فقط ممیزی؛ هیچ import یا انتقال به موتور |
| Issue1 6626346959/6627742064/6628302543 | look-ahead، grid مضربstep، partial cost، قفلSL≠realized | قرارداد همان اصول را حفظ می‌کند، بازسازی موتور ممنوع |
| Issue9 و تیکت207852 | نتیجه AI قبلی منفی/نامعتبر برای deployment؛ هزینه/حقوق نامعلوم | تمام هزینه‌های سناریو فرضی؛ ریسک۳٪/۶٪ حل‌نشده |

کارهای حذف‌شده از دوباره‌سازی: execution gateway، durable journal، volume grid، cost ledger، ATR/exit replay، CSV validator، random past-C و bootstrap. فقط fixture علمی/قرارداد readiness و تست اتصال به ماژول‌های pure اضافه می‌شوند. ۲۱۸ قبولی قبلی به‌عنوان اجرای تازه شمرده نمی‌شود تا واقعاً تکرار شود.

Issue19 دو کامنت 6654846536 و6654928051 نیز خوانده شد: آرتین فقط اسنادی و با ظرفیت آزاد بعداً؛ موتور دوم/integration در دامنه نیست. کابین مستقل در DraftPR21 تحویل شد و منتظر بازبینی است.
