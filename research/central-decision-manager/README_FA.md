# هوش مدیریتی مرکزی — نسخه پژوهشی ۰٫۱
مرجع: Issue #121، پژوهش ۲۰ اکسپرت طلا. این بسته موتور چهارم سیگنال‌دهی نیست؛ تصمیم واحد از سه موتور موجود می‌سازد. اجرای واقعی سفارش ندارد.

## اجرا
Node.js 20 یا جدیدتر، بدون وابستگی خارجی:
- `node research/central-decision-manager/selftest.mjs`
- `node research/central-decision-manager/run.mjs input.json`

manager.mjs تابع decide را صادر می‌کند. run.mjs یک تصمیم JSON برمی‌گرداند. ۲۲ آزمون منطقی مصنوعی هنگام ساخت در محیط JavaScript اجرا شدند. این آزمون‌ها بک‌تست یا اثبات سودآوری نیستند.

## قرارداد ورودی (همه زمان‌ها Unix milliseconds؛ تمام مبالغ USD)
- now, symbol, opportunityId: زمان قابل مشاهده، نماد، شناسه مشترک فرصت.
- registry: دقیقاً سه موتور با id, version, family (خانواده همبسته). تعیین خانواده بر عهده ارزیابی واقعی، نه نام‌گذاری فرضی.
- signals: برای هر موتور engineId, version, symbol, opportunityId, signalId, side (BUY/SELL/NEUTRAL), confirmed, knownAt, expiresAt.
- history: نتایج سایه هر سیگنال، حتی ردشده‌ها، شامل engineId, version, symbol, signalId, regime, side, signalAt, closedAt, netUsd, initialRiskUsd, verified, shadow, costsVerified. این رکوردها باید از بازپخش واقعی تولید شوند. فقط معاملات بسته‌شده پیش از تصمیم، همان نسخه/سمت/وضعیت بازار و هزینه تأییدشده استفاده می‌شوند.
- ledger: symbol, opportunityId, state؛ برای فرصت رزروشده/ارسال‌شده/باز/بسته جلوگیری از تکرار. یکپارچگی رزرو اتمی هنوز پیاده نشده و قبل از اتصال واقعی الزامی است.
- market: symbol, asOf, bid, ask, newsKnown, newsBlocked, sessionOpen, bars (حداقل ۲۴ کندل بسته‌شده و مرتب با closedAt, high, low, close). طبقه‌بندی آزمایشی روند/رنج/نوسان شدید و ساختار شکست از کندل بسته‌شده.
- account: verified, asOf, equity, freeMargin, openRisk, openPositions, pendingPositions.
- policy: minSamples, maxAgeMs, maxHistoryAgeMs, penalty, minEdgeR, minGapR, minFamilies, maxRiskFraction, maxSpread, minMarginLevel, minFreeMargin, maxPositions. همه باید صریحاً تنظیم شوند؛ اعداد selftest صرفاً داده مصنوعی‌اند و پیشنهاد عملیاتی مالک نیستند.
- preflight: نامزدهای حجم و حد ضرر از محاسبات واقعی بروکر، با symbol, opportunityId, side, verified, costsVerified, orderCheckPassed, checkedAt, expiresAt, lot, entry, stop, maxLossUsd (برآورد ریسک همراه هزینه، نه سقف تضمینی), costUsd, expectedGrossUsd, freeMarginAfter, marginLevelAfter. سود مورد انتظار باید بر اساس مدل مستقل معتبر باشد، نه عدد دلخواه. فلگ verified خود به خود سند نیست.

## منطق
امتیاز هر موتور از میانگین سود خالص نسبت به ریسک اولیه (R) منهای جریمه پراکندگی نمونه گرفته می‌شود؛ یک امتیاز پژوهشی، نه احتمال برد کالیبره‌شده. موتورهای هم‌خانواده فقط یک مشارکت خالص دارند. با نبود برتری معتبر، داده قدیمی، خبر نامشخص، اسپرد غیرمجاز، ریسک یا مارجین ناکافی و تکرار فرصت، خروجی NO_TRADE است. در غیر این صورت یک نامزد BUY/SELL در حالت SHADOW_ONLY برمی‌گردد. این هسته از قیمت یا هزینه ساختگی برای سفارش استفاده نمی‌کند و به MT5 یا API سفارش متصل نیست.

## وضعیت و مانع
پیش‌نمایش کابین موجود در مخزن (commit 605f5ea955e4b472e934eb6a9a1a8b016356a759) صراحتاً آفلاین است. نسخه واقعی سه موتور نصب‌شده و رابط‌های آن‌ها در بررسی فعلی بازیابی نشد؛ نام یا منطق موتورهای واقعی جعل نشده است. همچنین آرشیو کامل تیک ای‌پلنت و هزینه واقعی قابل استفاده فعلاً تأیید نشده است.

برای ادامه: آداپتور سه موتور واقعی، موتور بازپخش Bid/Ask و ثبت نتایج سایه، کنترل یکپارچه مسیر ارسال سفارش با رزرو اتمی، مدیریت خروج/قفل سود، و اعتبارسنجی walk-forward خارج از نمونه با تمامی هزینه‌های بروکر را پیاده‌سازی کن. فیلتر شکست/ATR و وزن‌ها باید پیش از فعال‌سازی اعتبارسنجی شوند؛ پژوهش قبلی هر ۲۰ سناریو زیان‌ده بود. هیچ قابلیت کابین حذف نشود. بدون تأیید مالک هیچ سفارش واقعی، خرید یا ادغام عملیاتی صورت نگیرد.
