# کنترل‌کننده گزارش و دستور بعدی امین — نسخه ۱

## قابلیت واقعی
GitHub Issue شماره ۶۸ کانال مشترک است. وقتی حساب مالک کامنتی با ساختار دقیق AMIN_REPORT_V1 بگذارد، GitHub Actions آن را بررسی می‌کند و با قواعد از پیش تعیین‌شده، یک کامنت AMIN_DIRECTIVE_V1 حاوی دستور پیشنهادی بعدی ثبت می‌کند.

این کنترل‌کننده **مدل هوش مصنوعی نیست**. دستورها از policy.json می‌آیند. GitHub به شکل خودکار همه پیام‌های ChatGPT را نمی‌بیند؛ ChatGPT باید در هر نوبت مربوط با ابزار GitHub گزارش بدهد، سپس پاسخ Issue را بخواند. این الزام در متن گفتگوی ChatGPT به شکل افزونه سراسری نصب نمی‌شود و اجرای اجباری در همه گفتگوها قابل تضمین نیست.

## نمونه پیام گزارش

    AMIN_REPORT_V1
    {
      "report_id": "support-cycle-20261122-0001",
      "project": "support",
      "phase": "knowledge",
      "status": "in_progress",
      "summary": "حافظه پروژه و شواهد GitHub توسعه یافت؛ هنوز آزمون کاربران واقعی انجام نشده است."
    }

- project یکی از support، faraz، artin، v5، cabin، iran-strategy است.
- phase یکی از inventory، knowledge، intelligence، diagnostics، support_quality، deployment است.
- status یکی از in_progress، failed، blocked، passed است.
- برای passed، commit_sha و ci_run_id باید با اجرای واقعاً موفق GitHub Actions در همین مخزن و همان commit تطابق داشته باشند. در غیراین‌صورت دستور VERIFY برمی‌گردد. **CI موفق به معنی تأیید کیفیت واقعی محصول نیست.**
- GitHub در پاسخ، next_phase، next_action_fa، reason_fa و project_guard_fa را می‌فرستد. approved_for_production همیشه false است.
- failed و blocked باعث عبور از مرحله نمی‌شوند؛ passed صرفاً مرحله بعد را به عنوان نامزد بررسی معرفی می‌کند.

## گردش‌کار
رویداد issue_comment.created → احراز نویسنده مالک و شماره Issue → اعتبارسنجی JSON → بررسی CI از API GitHub در صورت لزوم → انتخاب دستور ثابت مخصوص پروژه → ثبت پاسخ در همان Issue.

کامنت‌های نامرتبط، کاربران غیرمالک، PRها، شناسه‌های نامعتبر و ورودی‌های نامعتبر نباید دستور تولید کنند.

## امنیت، هزینه و محدودیت
- فایل‌ها فقط در amin-ai-support/control و Workflow جدا هستند؛ موتورهای معاملاتی تغییر نمی‌کنند.
- GitHub Actions و REST API لازم‌اند؛ با محدودیت سهمیه/شبکه ممکن است کار متوقف شود. این یک سرویس پردازش ۲۴ ساعته نیست.
- هیچ مدل پولی و خرید اجباری وجود ندارد.
- Issue در مخزن عمومی دیده می‌شود: هیچ داده شخصی، توکن، رمز، صورت‌حساب یا جزئیات محرمانه ارسال نشود.
- ارسال گزارش از ChatGPT خودکار و سراسری نیست؛ خواندن پاسخ در این گفتگو نیازمند اجرای ابزار GitHub توسط ChatGPT است.
- دستور پیشنهادی به معنای اجرای خودکار تغییرات نیست؛ این کار به عامل اجرایی جدا و مجوز مشخص نیاز دارد.

## آزمون

    python -m unittest discover -s amin-ai-support/control/tests -v

آزمون واحد یا خروجی ساختگی جایگزین آزمایش واقعی زنجیره کامنت → Actions → پاسخ GitHub نیست.
