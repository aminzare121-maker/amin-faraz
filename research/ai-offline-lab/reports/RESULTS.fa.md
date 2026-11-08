# نتیجهٔ واقعی آزمایش آفلاین AI — توسعهٔ گذشته‌نگر با فرض‌های پژوهشی

**نتیجه: مزیت سودده و قابل تأیید AI اثبات نشد؛ هیچ arm دارای معامله در سناریوهای اجراشده net مثبت نداشت.** مدل‌ها در بعضی شرایط کمتر معامله و کمتر زیان کردند؛ عدم معامله B0 نتیجه بهتری داشت. این آزمون، سود واقعی/کارایی حساب یا آزمون تأییدی مستقل نیست.

دو اجرای نهایی کامل نسخه۰٫۱٫۱ با کد/داده ثابت، هرکدام۴۵portfolio و۷۲fit مدل، به‌ترتیب 30.382 و 30.812ثانیه طول کشیدند. هر۷۲مدل در هر اجرا fit شدند؛ صفر خطای اجرایی یا foldِ فاقد مدل. ۳۴تست مصنوعی پاس شد. دو اجرای قبلی۰٫۱٫۰ حفظ شدند؛ پس از کشف و اصلاح bugمرزروزتهران، جفت اجرای نهایی تازه انجام شد. هیچ threshold/هزینه/مدل/سیاست به‌خاطر نتیجه انتخاب نشد. هر۴fold توسعه قبلاً دیده‌شده و تاریخ ارزیابی مشترک `2026-07-01..2026-11-03` است.

## جدول اصلی: strict/base

همهٔ دلارها فرضی‌اند: equityآغاز۱۰هزارUSD، contract100 فرضی، riskسفارش۰٫۲۵٪/DDروزانه۲٪/کل۸٪، TP2R/timeout4h. هزینه پایه spread.50USD/oz، commission10USD/lotرفت‌وبرگشت، slip.20هرطرف، swap0فرضی، latency15minپس ازclose. این‌ها specEplanet یا سیاست عملیاتی مالک نیستند؛ margin/liquidity مدل نشده‌اند.

| arm | سیگنال | معامله | setupبدون معامله | netUSD | expectancyUSD | PF | MDD% با MTM محافظه‌کارانه | بدترین روزUSD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | 0 | 0 | 0 | 0.00 | — | — | 0.000 | 0.00 |
| B1 | 207 | 89 | 118 | -602.15 | -6.77 | 0.432 | 6.271 | -42.72 |
| B2 | 178 | 113 | 65 | -428.36 | -3.79 | 0.656 | 5.594 | -68.73 |
| M1 | 207 | 6 | 201 | -73.00 | -12.17 | 0.096 | 0.830 | -24.12 |
| M2 | 207 | 4 | 203 | -10.18 | -2.55 | 0.446 | 0.428 | -15.96 |

ستون setupبدون معامله = سیگنال‌های arm منهای معاملات؛ شامل overlap/ریسک/آستانه/expiry است و همهٔ کندل‌های بدونsetup نیست. B0 اصلاً setupتولید نمی‌کند و در تمام کندل‌ها عدم معامله دارد؛ صفر این ستون به معنی عدم وجود تصمیم no-trade نیست. شمار eligibility/exclusion روی کل۲۹۲۳۴bar در JSON کامل آمده است.

M1/M2 فقط فیلتر ورود روی B1 هستند؛ جهت/SL/TP/خروج را یاد نگرفته‌اند. هر۴fold مدل trained غیرnull و calibrator جدا داشت؛ بنابراین کاهش فعالیت ناشی از آستانهٔ ثابت و داده است، نه fallbackمدل غایب. ۶ و۴معامله درbase برای ادعای expectancyپایدار کافی نیست. در کیفیت‌هایinclusive، مدل‌ها۰معامله دادند؛ این مساوی B0 است، نه شاهد سوددهی AI.

## net هر fold در strict/base

| arm | WF1 | WF2 | WF3 | WF4 |
|---|---:|---:|---:|---:|
| B0 | 0.00 | 0.00 | 0.00 | 0.00 |
| B1 | -215.44 | -96.65 | -75.21 | -214.85 |
| B2 | -99.09 | 41.62 | -214.65 | -156.24 |
| M1 | 0.00 | -73.00 | 0.00 | 0.00 |
| M2 | 0.00 | -10.48 | 0.30 | 0.00 |

## تمام حساسیت‌های ازپیش‌ثبت‌شده

base/high_cost/delayed همگی هزینه‌دارند؛ دو کیفیتinclusive نیز در جدول هستند و نتیجه‌ای انتخاب/پنهان نشده است. در high_cost،spread/fee/slip دوبرابر وswapفرضی۵USD/lot/night است؛delayed تأخیر۳۰دقیقه وswap۵ دارد. تغییر کیفیت، تقویم واقعیsession را تأیید نمی‌کند.

| کیفیت | هزینه | arm | معاملات | netUSD | MDD% |
|---|---|---|---:|---:|---:|
| strict | base | B0 | 0 | 0.00 | 0.000 |
| strict | base | B1 | 89 | -602.15 | 6.271 |
| strict | base | B2 | 113 | -428.36 | 5.594 |
| strict | base | M1 | 6 | -73.00 | 0.830 |
| strict | base | M2 | 4 | -10.18 | 0.428 |
| strict | high_cost | B0 | 0 | 0.00 | 0.000 |
| strict | high_cost | B1 | 86 | -702.59 | 7.129 |
| strict | high_cost | B2 | 110 | -570.36 | 6.545 |
| strict | high_cost | M1 | 6 | -83.13 | 0.902 |
| strict | high_cost | M2 | 7 | -60.55 | 0.910 |
| strict | delayed | B0 | 0 | 0.00 | 0.000 |
| strict | delayed | B1 | 82 | -644.93 | 6.494 |
| strict | delayed | B2 | 100 | -262.42 | 4.363 |
| strict | delayed | M1 | 0 | 0.00 | 0.000 |
| strict | delayed | M2 | 9 | -94.81 | 1.101 |
| flat_inclusive_weekdays | base | B0 | 0 | 0.00 | 0.000 |
| flat_inclusive_weekdays | base | B1 | 338 | -557.76 | 7.995 |
| flat_inclusive_weekdays | base | B2 | 329 | -644.26 | 7.992 |
| flat_inclusive_weekdays | base | M1 | 0 | 0.00 | 0.000 |
| flat_inclusive_weekdays | base | M2 | 0 | 0.00 | 0.000 |
| flat_inclusive_weekdays | high_cost | B0 | 0 | 0.00 | 0.000 |
| flat_inclusive_weekdays | high_cost | B1 | 196 | -601.64 | 7.978 |
| flat_inclusive_weekdays | high_cost | B2 | 280 | -700.87 | 7.980 |
| flat_inclusive_weekdays | high_cost | M1 | 0 | 0.00 | 0.000 |
| flat_inclusive_weekdays | high_cost | M2 | 0 | 0.00 | 0.000 |
| flat_inclusive_weekdays | delayed | B0 | 0 | 0.00 | 0.000 |
| flat_inclusive_weekdays | delayed | B1 | 204 | -717.07 | 7.999 |
| flat_inclusive_weekdays | delayed | B2 | 294 | -726.22 | 7.983 |
| flat_inclusive_weekdays | delayed | M1 | 0 | 0.00 | 0.000 |
| flat_inclusive_weekdays | delayed | M2 | 0 | 0.00 | 0.000 |
| inclusive_irregular | base | B0 | 0 | 0.00 | 0.000 |
| inclusive_irregular | base | B1 | 267 | -543.05 | 8.000 |
| inclusive_irregular | base | B2 | 308 | -627.19 | 7.992 |
| inclusive_irregular | base | M1 | 0 | 0.00 | 0.000 |
| inclusive_irregular | base | M2 | 0 | 0.00 | 0.000 |
| inclusive_irregular | high_cost | B0 | 0 | 0.00 | 0.000 |
| inclusive_irregular | high_cost | B1 | 191 | -589.95 | 7.991 |
| inclusive_irregular | high_cost | B2 | 240 | -674.75 | 7.998 |
| inclusive_irregular | high_cost | M1 | 0 | 0.00 | 0.000 |
| inclusive_irregular | high_cost | M2 | 0 | 0.00 | 0.000 |
| inclusive_irregular | delayed | B0 | 0 | 0.00 | 0.000 |
| inclusive_irregular | delayed | B1 | 210 | -716.87 | 7.997 |
| inclusive_irregular | delayed | B2 | 305 | -725.36 | 7.974 |
| inclusive_irregular | delayed | M1 | 0 | 0.00 | 0.000 |
| inclusive_irregular | delayed | M2 | 0 | 0.00 | 0.000 |

## اختلاف با B1 و عدم قطعیت

bootstrap جفت‌شده بر۱۲۵روز تقویمی مشترک با zero-days، بلوک۱/۵/۱۰روز و۱۰۰۰تکرار انجام شد. برای بلوک۵روز:

| arm strict/base | اختلاف net با B1،USD | CI95% اکتشافی اختلاف کل،USD |
|---|---:|---:|
| M1 | 529.15 | [197.42, 861.00] |
| M2 | 591.97 | [253.54, 923.51] |

CIاختلاف مثبت با B1زیان‌ده، اثبات سود مثبت مدل یا برتری بر B0 نیست. قدرت/حداقلاثر آزمون تأییدی تازه قفل نشده؛ ۶/۴معاملهٔ مدل و دادهٔ قبلاً دیده‌شده، تفسیر تأییدی را نمی‌پذیرند. net همهٔ۴۵case با period_net برابر بود و post_end_pnl=0؛ اختلاف CI با همان جریان روزانه سازگار است.

## کیفیت، بازتولید و محدودیت

strict از۲۹۲۳۴bar تنها۷۳۴۵bar واجد شرایط داشت:۱۶۷۶۰به‌خاطرflat درگذشته۶۴bar،۳۴۰۲gap،۱۶۶۴proxyآخرهفتهUTC و۶۳warmup رد شدند. این ردها در مشتق/منطق causalاست؛ هیچ ردیف اصل حذف/پر/بازنویسی نشد. inclusive-weekdays۲۴۱۰۵ وinclusive-irregular۲۹۱۷۱bar واجدشرایط داشتند. کیفیت واقعی session درهرسه نامعلوم است.

اصلCSVهمچنان SHA256 `8a0ecb9bf47096541bd581b5c21c3cc355930f8a110cad21cc64f6235fe13cdd` دارد؛ بازه364روزتقویمیِ شبکه و فاقدvolume/Ask/spreadاست. منبع/حق/session تأییدنشده‌اند. source/contract در حین دو اجرا تغییر نکردند و socket/process audit guard فعال بود. هیچ داده جدید،dependency،حساب،MT5،Vault،سفارش یاpromotion به موتور استفاده نشد.

هش بازتولید دو اجرا: `31c89702382cefdbf8502fa01a0d9b68d62e1554361c7e12b142badd4389ea9c`.

خطای آموزش/اجرا۰؛ در ساخت آزمون مصنوعی اولیه۲assert به‌دلیلfixtureاشتباه DD failedشد:fixtureحجم.1فرض‌می‌کرد ولیsizingحجم.05می‌داد؛ fixtureباافت intrabarکافی اصلاح شد، نهimplementationبرایpass. سپس۳۳تست قبل از داده پاس شد. پس از دو اجرای۰٫۱٫۰، اشکال مستقل resetguardدرتصمیمی‌که‌دقیقاًنیمه‌شب‌تهران‌است پیدا و با regression۳۴ام اصلاح شد؛ دو اجرای تازه با منطق ثابت۰٫۱٫۱ انجام شدند. نسخه‌های قبلی حذف نشدند؛ هیچ threshold/هزینه/سیاست برای بهترکردنP&Lعوض نشد.

[خلاصهٔ عددی کامل، hashمدل‌ها،C/V/E metrics،همهtrialها](aggregate-results.json) · [لاگ تست](synthetic-tests.log) · [اجرای نهایی اول](run-003.log) · [تکرار نهایی](run-004.log) · [قبلی۱](run-001.log) · [قبلی۲](run-002.log). مدل/وزن وtrade/privatepathمنتشرنشده‌اند. بازتولید نیازمندCSVمجاز جداگانه است.

**نتیجهٔ اجرایی:** در این نسخه و فرض‌ها، پیشنهاد ارتقا یااتصال دمو نداریم. مسیر بعد رفع provenance/specو بررسی فرض‌های داده/label/هزینه در بازبینی است؛ تغییر آستانه برای زیبا کردن همیننتیجه انجام نشد. فرض سوددهیِ این دو فیلتر در این آزمایش تأیید نشد؛ این، حکم ناممکن‌بودن همهAIها نیست.
