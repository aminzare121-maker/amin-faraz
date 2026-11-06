# بازتولید ممیزی مستقل PR37

نسخهٔ نخست و نتایج آن تغییر نمی‌کنند. این پوشه فقط ممیز آفلاین، اصلاح آماریِ مستقل و guard خروجی دارد. ابتدا REPORT_FA.md و AUDIT_POLICY.json را بخوانید. ورودی واقعی خصوصی باقی می‌ماند؛ از دادهٔ تازه یا MT5استفاده نمی‌شود.

از ریشهٔ مخزن با Python موجود و بدون نصب:

```powershell
python -m unittest discover -s research/faraz-pr37-audit-20261106 -p test_audit.py -v
python research/faraz-pr37-audit-20261106/pr37_audit.py --csv "PRIVATE_EXISTING_CSV" --reference research/faraz-local-lab/faraz_offline_lab.py --first-result research/faraz-local-lab/run-20261106/aggregate-result.json --policy research/faraz-pr37-audit-20261106/AUDIT_POLICY.json --private-dir "PRIVATE_TRACE_DIRECTORY" --out "LOCAL_AGGREGATE_JSON" --policy-commit be6d1eb44d9b9c127da8c273a7d1a3efc636d08d
```

فقط مسیر واقعی CSV را محلی تعیین کنید؛ در GitHub منتشر نکنید. traceداخل private-dir حاوی زمان/قیمت/شناسهٔ محلی است و نباید بارگذاری شود. خروجی outفقط aggregateاست. آزمون‌ها از نسخهٔ قفل‌شدهٔ siblingاستفاده می‌کنند؛ برای checkoutمحلی متفاوت می‌توان متغیر فرایندیFARAZ_PR37_REFERENCEرا به همان sourceباhashمطابق داد. تغییرline-endingیا حتیcommentنیز hashبایت‌محور قفل را تغییر می‌دهد؛ ممیز در این حالت عمداً متوقف می‌شود،نه اینکه sourceدیگری را بی‌صدا بپذیرد.

15تست جدید شامل ضدنمونهٔ صفر اقتصادی، عدم تبدیلNoneبه0،hardlink/same-path/دوخروجیalias،نوشتنatomic،بازگردانیcostcontext،cohortورودثابت،فقدان آینده،تفکیکgap/sample-end،DDقطعه‌ای،گپ‌زیان‌زا و هم‌ارزیstopBid/Askباspreadثابت‌اند. این‌ها تست نرم‌افزارند،نه اثبات سودآوری یا نمونه‌های مستقل بازار. اجرای نخست7تست داشت و در این شمار جدید دوباره شمرده نشده است.

هش policy/addendum/source/نتیجهٔ نخست و dataقبل از اجرا بررسی می‌شود. unknownها هیچ‌وقت0نمی‌شوند و annualnetنداریم. هیچ فراخوانی شبکه،SDKیا سفارش در ممیز نیست. نتیجهٔ اجرای ثبت‌شده درaudit-aggregate.jsonو اثر اصلاح عددی در هر6family/costصفر است.
