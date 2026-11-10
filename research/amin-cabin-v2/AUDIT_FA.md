# مرحله A — ممیزی شکاف کابین ۰٫۴٫۳٫۷

۵ نوامبر ۲۰۲۶. این ممیزی static و مشاهده تصاویر آرشیوی است، نه اجرای مجدد برنامه. مرجع frozen: [ed4591a](https://github.com/aminzare121-maker/amin-mt5-review/tree/ed4591a22349621ce2ac70fbb4554ce4f402f2b5). تصاویر: [بسته ۴۶ تصویر](https://github.com/aminzare121-maker/amin-mt5-review/tree/d03597d8e5839f24d86fcb92630988d9061a7dfe/evidence/amin-0437-20261104). سه تصویر 02،05،34 پاک‌سازی‌شده مستقیماً بازبینی شدند. بقیه ارجاع‌ها بر اساس ماتریس قبلی‌اند، نه ادعای بازبینی تک‌تک عکس‌ها در این نوبت.

| خواسته | کد/تابع در snapshot | شاهد ظاهر | وضعیت و شکاف |
|---|---|---|---|
| ناوبری و نمای کلی | ui-reference/clients/windows-native/Workspace.cs:BuildWorkspace | 02-main-overview.png | موجود؛ UI روشن و دوطرفه، نه طرح تیره ورق‌زدنی |
| نمودار MT5 واقعی | NativeTerminalPanel.cs:AttachAsync/Detach و Workspace.cs | 34-native-mt5.REDACTED.png | موجود با شاهد چارت؛ همزمان API خطا دارد؛ سلامت engine از نمودار قابل استنتاج نیست |
| سرمایه/P&L | OwnerForm.cs:RefreshData خطوط۱۸۲–۲۲۸، Workspace.dashboardValues | 02 | ناقص در حالت خطا؛ مقادیر اولیه «در حال دریافت» باقی‌اند. درخواست connection سپس status می‌تواند زنجیره را متوقف کند؛ علت شبکه دقیق نامعلوم |
| تازگی داده | TerminalSummary.cs:NetNumber/Render/Check | نوار پایین34 مقدار — | کنترل کدی موجود؛ کارت‌های RefreshData کنترل مشترک مشابهی ندارند؛ حفظ عدد قبلی پس از خطا یک ریسک مستند است نه خرابی بازتولیدشده امروز |
| حفاظت دستی | ManualProtectionPanel؛ OwnerFeatures.CapitalBannerText | 05-manual-risk-protection.png | ناقص؛ متن «وضعیت حفاظت دریافت نشد». active بودن یا موفقیت تغییر حد تأیید نمی‌شود |
| خودکار دمو | DemoAutonomyPanel و engine-configured/amin_mt5/demo_autonomy.py | ارجاع ماتریس06 | کد موجود؛ هیچ فعال‌سازی یا عملکرد زنده این نوبت آزموده نشد |
| سه حالت | OwnerForm/Workspace صفحات دستی و auto | selector کامل در ممیزی پیشین یافت نشد | ناقص؛ طرح جدید mode + scope + approval لازم دارد |
| سود/خروج پله‌ای | development-reference/net_profit_lock, profit_ladder, hybrid_profit_lock؛ release/adaptive_exit | شاهد جاری کافی نیست | فقط نمونه/جزئی؛ مسیر staged به معنی نصب و اجرا نیست |
| سقف زیان | engine-configured/amin_mt5/model.py:25 max_daily_drawdown=0.06 | سیاست هدف مالک۳٪ | تعارض باز؛ انتخاب و مهاجرت اجرا نشده |
| مرکز AI | strategy/runtime + StrategyReviewPanel | ماتریس39–41 | منطق/فهرست وجود دارد؛ مدل معتبر و edge اثبات نشده. PR11/12 نتیجه منفی مستقل از طراحی UI |
| انتظار بی‌پاسخ | Workspace/OwnerForm و مسیر sources | ارجاع18/38/42–44 | loading/خطای منابع؛ timeout، retry محدود، آخرین موفقیت و علت لازم است؛ علت ریشه‌ای نامعلوم |
| Android | ui-reference/.../DashboardActivity.java، OwnerExternalApps.java | گزارش UI audit | کلاینت موجود؛ engine_included=false و full parity تأیید نشده. دستگاه امروز بررسی نشده |
| برنامه‌ها/شخصیت‌ها | محدود به launch اپ رسمی MT5 در OwnerExternalApps | ماتریس | ناقص/نیازمند توسعه مستقل؛ خصوصی پیش‌فرض، ACL سرور و افزودن بدون سقف دلخواه |
| ملودی | Issue8 و چهار عنوان تأییدشده | فایل رسانه بررسی نشده | فقط نیازمندی؛ مجوز نسخه واقعی و پخش‌کننده لازم است |
| لوگو و ۱۲ اندیکاتور | Issue10؛ کاتالوگ راهبرد | لوگوی واقعی در بسته نیست | نامعلوم؛ ۱۳ راهبرد معادل۱۲ انتخاب نیست |

## منابع خوانده‌شده و مرز اعتماد

[خواسته و واقعیت](https://github.com/aminzare121-maker/amin-mt5-review/blob/ed4591a22349621ce2ac70fbb4554ce4f402f2b5/docs/REQUIREMENTS_AND_REALITY_FA.md)، [ممیزی UI](https://github.com/aminzare121-maker/amin-mt5-review/blob/ed4591a22349621ce2ac70fbb4554ce4f402f2b5/docs/UI_AUDIT_FA.md)، ماتریس_FEATURE و Issueهای۵،۷،۸،۹،۱۰ خوانده شدند. پنجره زنده ۰٫۴٫۳٫۷ باز/اجرا نشد و فایل نصب و منطق اصلی دست‌نخورده‌اند. تطبیق کامل source→binary هنوز unknown است.

جست‌وجوی محدود Downloads/Desktop و پوشه‌های پژوهش مرتبط، faraz_ui_concepts.html، پوستر رابط و Hamrah_Amin_approved_logo را پیدا نکرد؛ این جست‌وجوی کل دستگاه یا Library نیست. نمونه از مشخصات متنی طرح۱ ساخته شد و تصویر نادیده را مرجع استفاده‌شده معرفی نمی‌کند.

## تصمیم طراحی ناشی از ممیزی

چرخه ناوبری و نقش NativeTerminalPanel موجود حفظ شود، اما state/freshness نمایش از یک قرارداد مشترک تغذیه شود. pending بیش از deadline به timeout صریح تبدیل شود؛ اطلاعات قدیمی با زمان و برچسب stale از داده جاری جدا شود. ریسک در UNKNOWN رد می‌کند. no connection نباید «صفر معامله»، «سود صفر» یا «محافظ روشن» نمایش داده شود. عکس، کد، تست mock و سلامت نصب چهار ادعای جدا هستند.
