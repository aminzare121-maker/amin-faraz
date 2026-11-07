# پروتکل فریز سنجش AI — نسخه ۱، فقط طراحی و fixture مصنوعی

این پروتکل پیش از اجرای fixture تازه قفل می‌شود. داده واقعی، CSV قدیمی، fit یا بک‌تست بازار در این مرحله ممنوع‌اند. نتیجه قبلی PR11/12 edge را ثابت نکرد. هدف این بسته اعتبار ابزار سنجش است، نه سودآوری AI.

## فرضیه و معیار اصلی

تفاوت میانگین بازده خالص روزانه AI و شاهد تصادفی با بودجه مواجهه یکسان، روی روزهای مشترک با صفرها. معیار اصلی همراه CI جفتی زمانی گزارش می‌شود؛ net کمتر منفی با فعالیت کمتر برتری نیست. no-trade جدا با net=0/exposure=0 و نسبت‌های نامعین گزارش می‌شود.

معیارها: candidate و تعداد ورود/نسبت فعالیت، تعداد فرصت مستقل (بر اساس بلوک زمانی/خوشه وابستگی، نه تعداد کندل)، مدت در بازار، lot-hours، risk-USD-hours، notional-USD-hours، turnover lot و USD، net پس از هزینه، equity MTM و MaxDD USD/%، Sharpe روی بازده منظم زمانی (سالانه‌سازی فقط با session معتبر)، CI و نرخ veto/no-trade. نمونه کوچک/واریانس صفر → Sharpe undefined یا descriptive-only. در fixture جدید معاملات کاملاً non-overlap و دارای holding/risk ثابت‌اند؛ MaxDD از پایان گام‌های مصنوعی است، نه MTM واقعی بازار.

## کنترل منصفانه و علّی

PR12 بودجه پذیرش برآوردی past-C داشت، نه exposure تحقق‌یافته دقیقاً برابر. دوباره اجرا یا تنظیم نمی‌شود.

fixture این بسته: فرصت‌های برابر با ریسک۱۰دلار فرضی، زمان۹۰۰ثانیه و حجم۰٫۰۱، خروج زمانی ثابت. سهمیه k پیش از دیدن outcome قفل می‌شود؛ AI فرضی و random هر دو دقیقاً k از همان universe قابل مشاهده انتخاب می‌کنند. random فقط hash شناسه/seed و کد قرارداد می‌بیند؛ outcome ورودی selector نیست. همه seedهای 1729/2718/31415/42017/65537 منتشر شوند؛ برنده seed انتخاب نشود. سناریوی k=1 در برابر۱۰۰ ورود به‌عنوان عدم‌تعادل فعالیت گزارش و از استنتاج edge منع می‌شود. سهمیه‌ای که از تعداد معاملات آینده AI به دست آید ممنوع است.

در استفاده آینده با مدت خروج متغیر، برابری سقف risk-time/notional-time پیشینی لزوماً برابری exposure واقعی نیست. اختلاف واقعی گزارش شود؛ matching پسینی بر اساس P&L/مدت خروج ممنوع. اگر comparator با بودجه پیشینی معتبر قابل ساخت نیست، نتیجه «مقایسه هم‌مواجهه برقرار نشد»؛ division پسینی net/exposure تنها توصیفی است.

## split، علّیت و بودجه آزمون

داده آینده فقط پس از مجوز و قرارداد feed، با بازه‌های UTC صریح train→calibration→validation→holdout قفل شود. تاریخ‌های واقعی اکنون UNKNOWN؛ این یک gate توقف است. داده PR11/12 یا هر داده قبلاً دیده‌شده holdout جدید نیست. walk-forward با چهار پنجره تقویمی متوالی پیشنهادی و train گسترشی از پیش‌قفل‌شده؛ کفایت session قبل اجرا بررسی شود. بیشینه افق label/position و latency باید محدود و معلوم باشند؛ purge هر label که از مرز عبور می‌کند، embargo حداقل h_max+latency. ویژگی تنها از کندل بسته و available_at<=decision؛ H1/H4، pivot confirmation و gap جدا. scaling/imputation/feature selection فقط train، calibration بخش بعد و انتخاب threshold فقط validation؛ shuffle/random CV ممنوع.

بودجه حداکثر۱۲ pipeline، دو خانواده AI و پنج seed ثابت؛ همه شکست‌ها/trialها با hash config و timestamp ثبت شوند. primary comparison و secondaryها قبل holdout قفل؛ familywise alpha=.05 با Holm بر p-value معتبر (اگر محاسبه نشده claim significance ممنوع). block bootstrap جفتی روزهای مشترک با block1/5/10 و1000resample/seed1729 صرفاً diagnostic توسعه، برگرفته از module قبلی و بدون بازنویسی. حداقل۳۰ بلوک غیرهم‌پوشان برای گزارش استنباطی پیشنهادی؛ این حد اثبات توان نیست. minimum economic effect، power، بودجه ریسک و تاریخ holdout تا دریافت هزینه/سشن UNKNOWN و بنابراین قبولی نهایی BLOCKED.

هر تغییر بعد از دیدن holdout آن را به توسعه تبدیل می‌کند؛ نسخه تازه به داده آینده تازه نیاز دارد. CI یک‌نمونه‌ای، ۵seed یا آزمون مصنوعی سودآوری را ثابت نمی‌کنند. شرایط اقتصادی قبولی نهایی: net مثبت، کران پایین اختلاف با شاهد و no-trade مثبت پس از multiplicity، هزینه و risk budget مصوب، پایداری stress و نمونه کافی؛ این شروط در این مرحله آزموده نمی‌شوند.

## محدودیت جاری

۳٪/۶٪ تعارض باز؛ commission/tick-value/session/licence UNKNOWN. پارامترهای fixture فقط ساختگی‌اند. در تمام گزارش‌ها real_data_used=false، model_fit=false، order_authority=false. انجماد پروتکل با SHA256 در protocol-lock.json پیش از اجرای آزمون ثبت می‌شود.
