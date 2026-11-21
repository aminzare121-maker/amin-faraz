# کنترل خودکار نمایشگر با فرمان فعال/متوقف «برنامه جواب»

## خواسته قطعی مالک

**«برنامه جواب فعال کن»** باید هم‌زمان و بدون یک کلید جداگانه، قابلیت روشن‌ماندن صفحه را **در کلاینت بومی نصب‌شده اندروید** فعال کند.

**«برنامه جواب متوقف کن»** باید با تأیید توقف، این قابلیت را غیرفعال کند. اگر چند کار مجزای «جواب» فعال‌اند، توقف یک کار نباید مدیریت صفحه کارهای فعال دیگر را از بین ببرد. با توقف آخرین کار، پرچم‌های نمایشگر آزاد می‌شوند.

این قابلیت ساعت‌محور نیست؛ فقط وضعیت واقعی کارهای فعال «جواب» و وضعیت نمایش اپ روی گوشی آن را تعیین می‌کند.

## بخش‌های ساخته‌شده در کد

- `JavabActivationState.java`: منطق مستقل وضعیت فرمان‌ها؛ فعال‌سازی، توقف یک کار، توقف همه، بازیابی فهرست کارهای واقعاً فعال، مدیریت چندکار هم‌زمان و غیرفعال‌شدن در پس‌زمینه
- `ScreenAwakeSession.kt`: اتصال این وضعیت به `FLAG_KEEP_SCREEN_ON` و در شرایط مجاز `Activity.setTurnScreenOn`
- `tests/JavabActivationStateTest.java`: آزمون اجرایی با `javac` و `java` برای وضعیت و جداسازی کارها

کلاینت واقعی پس از **تأیید دریافت فرمان و ایجاد کار** باید `controller.onActivated(taskId)` را فراخوانی کند؛ پس از **تأیید دستور توقف**، `controller.onStopped(taskId)` و اگر توقف همه درخواست شده `controller.onAllStopped()` را اجرا کند. این فراخوانی‌ها نباید فقط بر اساس متن غیرقابل اعتماد چت انجام شوند؛ وضعیت باید از کانال معتبر همان کلاینت تأیید شود.

نمونه پیوند در Activity:

```kotlin
private lateinit var controller: JavabScreenController

override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    controller = JavabScreenController(this)
}
override fun onResume() {
    super.onResume()
    controller.onResume()
}
override fun onPause() {
    controller.onPause()
    super.onPause()
}

// Only after Javab activation is confirmed:
fun javabTaskStarted(verifiedTaskId: String) = controller.onActivated(verifiedTaskId)

// Only after the requested Javab stop is confirmed:
fun javabTaskStopped(verifiedTaskId: String) = controller.onStopped(verifiedTaskId)

// Only after the owner requested and confirmed stopping all tasks:
fun allJavabTasksStopped() = controller.onAllStopped()
```

در شروع مجدد Activity، اطلاعات کارهای فعال باید از سامانه معتبر بازیابی و با `syncVerifiedActiveTasks(ids)` به‌روز شود؛ ادعای وجود یک سرویس همگام‌سازی بومی در این نسخه نداریم.

## محدوده واقعی و وضعیت

**مدیریت نمایشگر به فرمان‌های فعال‌سازی/توقف در کد وصل است، ولی به گوشی کاربر یا اپ ChatGPT وصل نشده است.** هنوز APK این بخش ساخته/نصب نشده و آزمون واقعی اندروید انجام نشده است.

- امکان جلوگیری از خاموش‌شدن خودکار، هنگام بازبودن Activity و فعال بودن کار وجود دارد.
- روشن‌کردن قطعی صفحه پس از زدن پاور، قفل دستی یا وقتی برنامه در پس‌زمینه است **پیاده‌سازی نشده و تضمین‌شده نیست**.
- دورزدن قفل گوشی یا روشن‌کردن نمایشگر از یک پیام GitHub بدون عامل بومی نصب‌شده مجاز یا ممکن نیست.
- مدیریت خودکار صفحه باعث مصرف باتری می‌شود؛ با توقف کار یا خروج Activity، پرچم‌های مربوط حذف می‌شوند.

**قبولی عملی باقی‌مانده:** ساخت APK، اتصال به رویدادهای معتبر شروع/توقف برنامه جواب، نصب روی اندروید واقعی، آزمون آغاز و توقف هم‌زمان چندکار، آزمون خاموشی و قفل دستی، و اندازه‌گیری اثر روی باتری.

مستندات اندروید: https://developer.android.com/develop/background-work/background-tasks/awake/screen-on
