# نتایج واقعی آزمون

- `node --test tests/model.test.cjs`: ۴۷ PASS، صفر FAIL/SKIP؛ log کامل test-results.txt.
- هشت صفحه در دسکتاپ و قاب باریک باز شد؛ همه pending owner approval. فایل browser-layout-results.json شامل clientWidth/scrollWidth برابر (گوشی ۳۰۶ یا ۳۲۲، همگی کمتر از ۳۷۵؛ دسکتاپ ۱۲۶۵) است. قاب اسمی ۳۲۰ با نوار پیمایش داخلی است؛ snapshot ابزار یک نمونه عرض متفاوت ثبت کرد، بنابراین ادعای دستگاه ثابت نداریم.
- ناوبری پایین گوشی صفحه۸→۱ موفق، position=fixed؛ دو قاب مستقل‌اند.
- ArrowLeft:۷→۸؛ ArrowRight:۸→۷. کاهش حرکت واقعی در مرورگر animationName=none.
- disconnect→reconnect→reconcile: eligible=false، DISARMED؛ guardian=UNKNOWN باقی ماند.
- درخواست و تکرار آن: رد، یک ردیف ژورنال، ordersSent=0.
- حسابگر فرضی ۰٫۰۱: gross=10، cost=.38، net=9.62، realized=0. نرخ واقعی بروکر نیست.
- قطع گوشی وضعیت موتور/محافظ نمونه را تغییر نداد.
- شواهد تعامل در browser-interaction-results.json.
- source/CSP: connect-src none، بدون fetch/WebSocket/SDK، بدون CDN فونت/دارایی؛ تست import و URL انجام شد. این بررسی معادل packet capture کل ویندوز نیست.
- تست واقعی دستگاه لمسی/swipe و OS prefers-reduced-motion: SKIP (دستگاه در این آزمون در دسترس نبود). جهت/آستانه/حرکت عمودی swipe در pure tests موفق؛ checkbox کاهش حرکت واقعاً آزموده شد.
- MT5/broker/trade/real data: اجرا نشده و خارج دامنه.

آزمون‌های pure موفق، اثبات محافظ واقعی یا موتور نصب‌شده نیستند.
