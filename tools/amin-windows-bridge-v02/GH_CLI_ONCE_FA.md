# اجرای یک‌بارهٔ همان پل قبلی با ورود رسمی GitHub CLI — بدون توکن در چت

این فایل متعلق به **همان bridge0.2 / PR41 / Issue38** است؛ پل تازه یا سرویس دائمی نیست. هدف فقط اثبات status رفت‌وبرگشت واقعی است. منبع V12، فیلم‌های آرتین و شاخه main دست‌نخورده می‌مانند.

## محدودیت کنونی

تا اینجا پل Windows با `exit=1` تمام شده و `AMIN-WIN-RESULT-v1` در Issue38 مشاهده نشده است. GitHub connector در ChatGPT، به برنامه Python اجراشده روی رایانه اعتبارنامه نمی‌دهد. اجرای همه تست‌های آفلاین، «اتصال زنده» را ثابت نمی‌کند.

## اجرا فقط روی کامپیوتر مالک، در ترمینال تعاملی واقعی

۱. در همان محیط Codex Windows، اول وجود `gh` را با `gh --version` بررسی کنید. **اگر موجود نیست**، تنها با اجازه مالک، GitHub CLI رسمی را با `winget install --id GitHub.cli -e --source winget` نصب کنید؛ بعد یک PowerShell/ترمینال تازه باز کنید. نه از سایت‌های غیررسمی و نه با نصب پنهانی.

۲. `gh auth status --hostname github.com` را بررسی کنید. اگر وارد نشده، در PowerShell قابل‌دیدنِ خود مالک اجرا کنید:
```powershell
gh auth login --hostname github.com --web --git-protocol https --scopes repo
```
ورود در مرورگر خود مالک انجام می‌شود. **مهم: دسترسی OAuth با scope `repo` می‌تواند همهٔ مخزن‌های خصوصی تحت دسترسی همان کاربر را پوشش دهد.** اگر مالک این سطح دسترسی را نمی‌پذیرد، این مرحله را انجام ندهید و به‌جای آن از روش موجود `local_secret_once.py` با توکن fine-grained فقط برای این مخزن و permission «Issues: Read and write» استفاده کنید؛ مقدار توکن فقط در prompt مخفی محلی وارد می‌شود.

۳. اگر کدهای پل موردبازبینی فعلی دقیقاً مطابق SHA ثابت مندرج در `gh_cli_once.py` هستند، در PowerShell همان پوشه اجرا شود:
```powershell
python .\gh_cli_once.py
```
این برنامه از GitHub CLI، توکن را فقط در حافظه می‌گیرد، همان میزبان `local_once_host.py` را به‌صورت یک‌باره اجرا می‌کند، کد پل و launcher را طبق SHA ثابت بررسی می‌کند و هیچ توکن، رمز یا لاگ حساس را منتشر نمی‌کند. فایل‌های پلِ اصلِ نصب‌شده در ویندوز را تغییر ندهید.

۴. کانال رسمی پاسخ: https://github.com/aminzare121-maker/amin-faraz/issues/38 . تنها پاسخ معتبر، کامنت **واقعی** `AMIN-WIN-RESULT-v1` برای درخواست قبلی `amin-bridge-first-handshake-20261106` است؛ پس از آن ChatGPT باید آن کامنت را مستقل بخواند و تأیید کند. خروج `0` اسکریپت یا `CHILD_EXITED` به‌تنهایی موفقیت اتصال نیست.

۵. اگر شکست خورد، فقط یکی از blockerهای غیرحساس را گزارش کنید: `GH_CLI_MISSING`، `GH_LOGIN_REQUIRED`، `GH_TOKEN_NOT_AVAILABLE`، `BLOCKED_CODE_CHANGED`، `BLOCKED_LAUNCHER_CHANGED`، `CHILD_EXITED/returncode`، `INFLIGHT_NEEDS_LOCAL_RECONCILIATION`، مشکل HTTP/شبکه در محدوده GitHub. **خروجی خام حاوی credential، متغیرهای محیطی، فایل‌های خصوصی یا screenshot ورود را منتشر نکنید.**

۶. در این مرحله فقط یک اجرای status انجام شود. راه‌اندازی watch/Startup/Task Scheduler، پورت عمومی، generic GitHub command، نصب CUDA، خرید سهمیه Actions یا تغییر موتور V12/معاملات **مجاز نیست**. جریان پردازش آرتین را متوقف نکنید.

## نکتهٔ فنی
نصب GitHub CLI یا ورود OAuth مستلزم اقدام واقعی روی کامپیوتر مالک است و از سمت connector GitHub در ChatGPT قابل اجرا نیست. این گزارش باید با وضعیت **NOT CONNECTED** باقی بماند تا رسید واقعی Issue38 مشاهده شود.
