# اجرای موقت V13 روی ویندوز — فیلم سوم آرتین

**وضعیت:** اسکریپت در GitHub ثبت شده؛ **هنوز در ویندوز اجرا و تأیید نشده**. اتصال GitHub Runner به ویندوز تنها برای آزمون status تأیید شده است؛ این بسته به همان Workflow یا guard دست نمی‌زند.

## مأموریت
از خشاب `artin-course-001` فیلم `video-q-0003-artin-clip-01` (لینک `https://my.uupload.ir/p/dxvmY5Gv`) را با نسخه اصلی ثابت و دادهٔ چت/تخته/گفتار پردازش کند. فیلم شماره ۱ و ۲ دوباره پردازش نمی‌شوند؛ فیلم ۴ فقط بعد از رسید واقعی و معتبر فیلم ۳.

## نصب/اجرای محلی با دسترسی مستقیم Codex Windows (نه GitHub-hosted Actions)
1. سورس از SHA ثابتِ بازبینی‌شده `780f30e0a056c991945cd0a46007724334f6693e` یا commit جدیدتر **پس از بازبینی تغییرات** در یک پوشهٔ تازه دریافت شود؛ فایل‌های V12 و checkpointهای پروژه‌های دیگر نباید تغییر کنند.
2. Python و FFmpeg/FFprobe بررسی شوند؛ در محیط Python جداگانه نصب محدود `Pillow`, `numpy`, `faster-whisper`, `paddlepaddle`, `paddleocr` مطابق فایل‌های مرجع انجام شود. هیچ نصب سیستمی، تغییر policy یا دریافت/انتشار credential بدون نیاز/مجوز انجام نشود.
3. پوشه خصوصی مثلا `C:\\AMIN_PRIVATE\\V13\\film3` **خارج از Git repository** انتخاب شود. اجرای مرحله‌ها توسط Codex:

```powershell
python experiments/video001-v13/windows/film3_local.py --out "C:\AMIN_PRIVATE\V13\film3" --phase preflight
python experiments/video001-v13/windows/film3_local.py --out "C:\AMIN_PRIVATE\V13\film3" --phase prepare
python experiments/video001-v13/windows/film3_local.py --out "C:\AMIN_PRIVATE\V13\film3" --phase asr
python experiments/video001-v13/windows/film3_local.py --out "C:\AMIN_PRIVATE\V13\film3" --phase ocr
python experiments/video001-v13/windows/film3_local.py --out "C:\AMIN_PRIVATE\V13\film3" --phase verify
```

`--phase all` تمام این کارها را پشت‌سرهم انجام می‌دهد، ولی تفکیک مراحل برای ثبت خطا و حفظ checkpoint بهتر است. اجرای تست‌های آفلاین:

```powershell
cd experiments/video001-v13/windows
python -m unittest discover -s . -p "test_film3_local.py"
```

## قیود صحت و اجرای واقعی
- SHA-256 فیلم باید **دقیقاً** `a2721fb01575f9ad4859f594e5c6fa6852e31dce353e31f70eed1a8edb3bbfbb` و حجم **۲۱۸٬۶۴۷٬۷۰۳ بایت** باشد؛ در غیر این صورت خطا/توقف. مدت ۵۱۵۷٫۱۹۸۳۶۷ ثانیه، ۱۸ بخش اصلی.
- خروجی‌ها در محل خصوصی باقی می‌مانند؛ اصل فیلم تغییر نمی‌کند. فایل `safe_result.json` فقط با موفقیت تمام مراحل تولید می‌شود، و تمام مفاهیم مدرس **نیازمند مرور مستقل** هستند.
- روی لپ‌تاپ، مدل Whisper از CPU/int8 و ۴ thread استفاده می‌کند؛ کارگران ۳۳تایی GitHub عیناً روی Windows تکرار نمی‌شوند. سرعت ۲۰–۲۵ دقیقه یا ۳ دقیقه **هیچ‌کدام برای Windows تأیید نشده‌اند**.
- چهار ابزار اضافی WhisperX/Qwen3-VL/VideoRAG/PaddleOCR در مفهوم V13 متفاوتند: این اجرای محدود از `faster-whisper` و `PaddleOCR` مسیر قبلی استفاده می‌کند، **نه اجرای کامل همه چهار ابزار**.
- اگر Python/FFmpeg/model نصب نیست، اگر منبع بارگذاری در دسترس نیست، اگر checksum/پردازش خطا می‌دهد یا اگر پردازشگر محلی مجوز ندارد: **به جای اعلام موفقیت، همان مانع را ثبت کن**.
- موفقیت اجرای `preflight` یا `prepare` به معنی استخراج کامل مدرس نیست. آزمایش معنی و Q&A و کاربرد معاملاتی همچنان جداگانه لازم است.
- هیچ اتصال به MT5، سفارش واقعی، تغییر داده حساب یا دسترسی عمومی remote shell مجاز نیست.

## گزارش اجرا
فقط SHA و حجمِ منبع، شماره فیلم، تعداد قطعات/فریم‌ها، مرحله و زمان واقعی، نوع خطا و وضعیت تأیید مستقل در Issue #58 گزارش شود. **متن کامل گفتار، عکس دانشجو، ویدئو و مشخصات حساب نباید به مخزن فرستاده شود.**

- [دستور اجرا برای Codex ویندوز](https://github.com/aminzare121-maker/amin-faraz/issues/58#issuecomment-6721688120)
- [ثبت V13 در مخزن ابزارها](https://github.com/aminzare121-maker/amin-faraz/blob/tools-makhzan-hub/tools-makhzan/VIDEO-001-V13_STATUS_FA.md)
