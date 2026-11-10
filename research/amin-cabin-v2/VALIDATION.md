# مرحله C — آزمون‌های واقعاً اجراشده، ۲۰۲۶-۱۱-۰۵

محیط: Windows، Node v26.13.0 موجود؛ dependency نصب نشد. فرمان: `node --test tests/model.test.cjs`، خروجی واقعی `test-results.txt`: **۴۰ PASS، صفر FAIL، صفر SKIP**. از این تعداد یک تست syntax برای app.js است. اجرای نخست ۳۹تست منطق پاس شد ولی مرورگر به‌علت quote اشتباه صفحه AI خالی بود؛ خطا اصلاح، تست parse اضافه و مجموعه کامل دوباره پاس شد. نتیجه اولیه به‌عنوان موفقیت UI گزارش نشده است.

پوشش: UNKNOWN چهار وضعیت، زمان NaN/Infinity/آینده/کهنه و مرزTTL، هزینه/ریسک نامعلوم، توقف، بازگشت اتصال و تطبیق بدون rearm، قطع موبایل مستقل، تأیید دستی/semi، مدل نامعلوم، idempotency درخواست پذیرفته/ردشده، حجم۱/.۰۱ با هزینه فرضی، ناوبری RTL/boundaries/gesture و ممنوعیت اتصال CSP. در تمام mockها ordersSent=0؛ هیچ adapter معاملاتی وجود ندارد.

## آزمون واقعی مرورگر (دستی با ابزار UI، نه تست خودکار دستگاه)

پس از اصلاح syntax، همه۸صفحه با دکمه بعدی مشاهده و۸تصویر viewport ثبت شد. صفحه اول previous و آخر next غیرفعال بودند. انتخاب مستقیم منو از صفحه۷ به۱ و کلید Right از۸ به۷ کار کرد. روی صفحه۳ ارزیابی در UNKNOWN رد شد و تکرار شناسه همان پاسخ را بدون ژورنال جدید نشان داد. در صفحه۴ انتخاب۰٫۰۱lot خروجی gross10/cost.38/net9.62/realized0 را نمایش داد. در صفحه۶ قطع engine=OFFLINE و بازگشت engine=OK اما data_fresh=UNKNOWN، execution_armed=DISARMED و reconciliation required باقی ماند. قطع گوشی وضعیت موتور را تغییر نداد. STOP پیام فقط‌نمونه و عدم ارسال نشان داد. checkbox کاهش حرکت فعال شد و computed animationName='none' تأیید شد. DOM: clientWidth1265/scrollWidth1265، بدون horizontal overflow.

تصاویر این پوشه تصاویر خود **نمونه آفلاین** هستند، نه حساب واقعی یا کابین نصب‌شده. محدودیت screenshot ابزار: viewport است؛ قسمت‌های پایین صفحه با پیمایش قابل مشاهده‌اند، تصویر تضمین capture تمام صفحه نیست. هیچ داده خصوصی در نمونه استفاده نشده است.

| تصویر | صفحه |
|---|---|
| [01](evidence/01-overview.png) | نمای اصلی |
| [02](evidence/02-terminal.png) | محل نمایش MT5؛ بدون ترمینال واقعی |
| [03](evidence/03-orders.png) | رد و تکرار درخواست نمونه |
| [04](evidence/04-risk.png) | هزینه فرضی حجم کوچک |
| [05](evidence/05-ai.png) | AI بدون مدل معتبر |
| [06](evidence/06-lab.png) | reconnect بدون rearm |
| [07](evidence/07-mobile.png) | قطع گوشی نمونه |
| [08](evidence/08-tools.png) | ابزارهای مؤجل |

## موارد آزموده‌نشده و محدودیت عمدی

touch واقعی Android، viewport گوشی فیزیکی، screen reader، integration WinForms/MT5، restart/crash journal پایدار، هزینه/حجم واقعی broker، source→binary و account protection آزموده نشده‌اند. swipe classifier و جهت‌ها unit-tested هستند؛ این به معنی آزمایش انگشت روی گوشی نیست. ژورنال prototype حافظه‌ای است؛ UI انتخاب‌های فرم را پس از تعویض صفحه از نو می‌سازد، mode در حافظه حفظ می‌شود. production نیاز به حفظ draft تأییدنشده با هش و expiry دارد.

همه صفحه‌ها منتظر تأیید جداگانه مالک‌اند. این مجموعه مجوز نصب یا اثبات آمادگی معامله نیست؛ مرز stageC یک proof-of-concept غیرمتصل است.
