# فراز — ممیزی مستقل فهرست فاصله‌ها — ۶ نوامبر ۲۰۲۶

- changed_files: gap_csv_guard.py, test_gap_csv_guard.py, REPORT_FA.md
- tests: ۸ آزمون با داده مصنوعی در محیط مستقل ChatGPT PASS، صفر شکست. آزمون روی GitHub Actions یا ویندوز اجرا نشده است.
- known_issues: تاریخچه کامل یک‌ساله و منشأ قطعی ۲۶۰ فاصله هنوز تأیید نشده؛ زمان خام بروکر UTC فرض نشده؛ فایل‌های واقعی محلی در دسترس این اجرا نیستند. PR34 ابزار M5 مستقل دارد؛ این ابزار فقط پیش‌ممیزی CSV فاصله‌هاست و جایگزین آن نیست.
- next_actions: Codex در صورت صلاحدید این کنترل را قبل از خواندن gap-csv در ابزار PR34 ادغام کند و آزمون‌های خودش را اجرا کند. داده خام خصوصی بماند.
- approval_needed: هیچ معامله، نصب، Merge یا تغییر main/ربات اصلی/جارویس مجاز نیست.
- run: python -m unittest -v test_gap_csv_guard.py
- result: reject overlapping ranges, duplicate IDs, off-grid M15 timestamps, timezone-bearing labels, invalid dates and counts.
- status: RESEARCH_ONLY; no data recovery or profitability claim.
