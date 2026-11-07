# آمادگی پژوهش فراز — بسته محدود Issue19

A، B و C صرفاً مصنوعی/قراردادی اجرا شده‌اند. این خروجی استراتژی، موتور معاملاتی یا نتیجه سودآوری نیست. هزینه‌های واقعی، مجوز داده، holdout مستقل و سیاست۳٪/۶٪ هنوز حل نشده‌اند. هیچ CSV قدیمی، قیمت واقعی، حساب، MT5 یا SDK در این مأموریت استفاده نشده است.

- [مرحله صفر و حذف دوباره‌کاری](STAGE0_REUSE_FA.md)
- [پروتکل منجمد A](AI_EVALUATION_PROTOCOL_FA.md) و protocol-lock.json
- [بازاستفاده B و نتایج عددی](RISK_PATH_REUSE_FA.md)
- [قرارداد C و شاخه‌های پاسخ Eplanet](FEED_READINESS_FA.md)
- [گزارش نهایی](RESULTS_FA.md)

با Python موجود و standard library، بدون نصب dependency:

```
python -B run_a.py
python -B run_b_matrix.py
python -B run_c.py
cd vendor/resilience
python -B tools/run_resilience_tests.py
```

run_a/b/c گزارش خود را در همین بسته می‌نویسند. run_resilience_tests فقط childهای آزمایشگاهی خودش و پوشه آزمایش را به کار می‌برد؛ داده حساب/تاریخچه ورودی ندارد. تمام vendor از commit ثابت کپی و با SHA تطبیق داده شده؛ به نصب اصلی import نمی‌کند. گزارش‌های baseline vendor تاریخی‌اند؛ گزارش تازه ۲۱۸ تست فقط زیر reports/resilience-lab است.

شاخه research/readiness-v1، DraftPR22، بدون merge/main. گام بعد بازبینی ChatGPT؛ پاسخ Eplanet به‌تنهایی مجوز خودکار دانلود یا معامله نمی‌شود. آرتین Issue20 صرفاً مسیر اسنادی کم‌اولویت مستقل است و موتور دوم ایجاد نمی‌کند؛ کابین Issue16 در PR21 مستقل باقی است.
