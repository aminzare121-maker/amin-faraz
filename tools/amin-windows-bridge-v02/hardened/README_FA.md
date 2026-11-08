# پل محدود امین — نسخهٔ سخت‌سازی‌شدهٔ۰٫۲، آمادهٔ آزمون handshake

نسخهٔ اصلیPR39درpr39-originalدست‌نخورده است. این نسخه مستقل فقط باکتابخانهٔ استاندارد وPythonموجود آزموده شد؛هیچ نصب،سرویس،Startup،MT5،ربات یا تغییر شبکه در این کار انجام نشد.

## مرز حالت زنده

CLIبه‌صورت پیش‌فرضCONFIG_ONLYاست:نهauthlookup،نهشبکه،نهqueue. حالت --live-handshakeفقطrepoثابتaminzare121-maker/amin-faraz،Issue38،ownerثابت،**همانcomment6688143796وIDamin-bridge-first-handshake-20261106**را باaction=statusمی‌پذیرد. درخواست جدیدی ساخته نمی‌شود. genericliveازجملهfile/test/MT5/ربات فعال نیست. توابع کتابخانهٔfile/testفقط باmockوworkspaceمصنوعی آزموده شده‌اند؛run_unittestهنوزکدپروژهٔمورداعتمادرااجرامی‌کند وsandboxنیست.

مالک باید workspaceجدا را انتخاب/تأیید کرده باشد. START_ONCE_WINDOWS.batفقطهمانworkspaceرا به‌عنوانتنهاآرگومان می‌گیرد؛همراهPythonازپیش‌موجودAMIN_BRIDGE_PYTHON(یاPATH)وtokenمحلیِموقتAMIN_BRIDGE_GH_TOKEN. هیچ tokenدرargv،فایل یا خروجی لازم نیست. bridgeنهcredentialstoreمی‌خواند،نهgh/gitاجرامی‌کند،نهgetpassیاورود تعاملی دارد. میزبانِمحلیِتأییدشده می‌توانداحراز هویتِازپیش‌موجودرا فقطدرenvdictفرزند بدهد؛این فایل آن را پیدا یا ذخیره نمی‌کند. START_WATCH_WINDOWS.batعمداًexit2است؛حالتwatch/سرویس ایجاد نشده است.

## اصلاح‌های واقعیِ آزموده‌شده

- redirectHTTPغیرفعال؛originHTTPS،repository،Issue،method،endpointوqueryمحدودند. پاسخ به2MiBدرهرpageو10pageمحدوداست؛URLنهایی هم بایدهمانURLدرخواست باشد. توکنبهredirectforwardنمی‌شود.
- decoderبرایactionلیست/شیء وIDغیررشته‌ایfailclosedمی‌شود. protocolIDحتی باcommentIDجدیددوباره اجرا نمی‌شود؛تغییرpayloadباهمانIDهم مجوزجدید نیست.
- stateبهrepo/issue/owner/workspacecanonical/حالت اجراscopeمی‌شود؛زیرworkspaceتأییدشده می‌ماند،نهPath.home. lockانحصاریازدوworkerهم‌زمانجلوگیری می‌کند؛stateatomicوفایلhardlink/reparseردمی‌شود.
- رزروinflightقبل ازactionذخیره می‌شود. crashدرمرز نامعلوم نیازمندreconciliationمحلیاست وactionخودکار دوباره اجرا نمی‌شود. pendingresultبدوناجرایمجددقابلارسالاست،اماlivehandshakeفقطنتیجهٔثابتstatusِهمانID/commentراretryمی‌کند. موفقیتpostوقطعقبلstatecommitممکن استresultتکراریبسازد؛**exactly-onceیاat-most-onceپایدارِهمه‌جانبه ادعا نمی‌شود**.
- traversal/drive/ADS،symlinkوreparseparent،فایلhardlink،تغییرidentityفایل ومحدودیتbytesکنترل می‌شوند. syntax_checkهرمسیر راقبل ازخواندن دوباره اعتبارسنجی می‌کند؛scandirبه1000entry،128directory،depth8و75fileمحدوداست،نهsorted(rglobکل‌درخت).

## آزمون واقعی این نسخه، بدون شبکه

13تست اصلی بدونتغییرروی نسخهٔ۰٫۲:12PASSو1SKIP(native symlinkروی اینWindowsدردسترس نبود).22تست تازهٔmock/مصنوعی:22PASS. مجموع35تست،34PASS،1SKIP،صفرFAIL/ERROR. mockreparseparent،hardlinkواقعیtemp،redirectheaderforwardِbaselineوپسازاصلاح،duplicateID،inflightcrash،scope،responsebounds،boundedwalkوhandshakeدقیق پوشش داده شدند. junction/reparseواقعی رویWindowsساخته/مشاهده نشد؛آن شاخه باfixtureشبیه‌سازی شد. skipبه‌عنوانPASSشمرده نشد.

این تست‌ها اثبات اتصال زنده،امنیت مطلق،sandboxیا خواندن مستقیم حساب نیستند. اجرای واقعی handshakeوproofنتیجه درIssue38 وظیفهٔ میزبانِدارایمجوز است؛این ممیز هیچ شبکه،احراز هویت واقعی،فرمان زنده یاcredentiallookupاجرا نکرد. محدودیت‌هایlocalfilesystemrace،کدمورداعتمادunittestوstateخراب/قدیمی نیازمندبازبینی محلی باقی‌اند؛genericliveبرایهمینفعال نیست.
