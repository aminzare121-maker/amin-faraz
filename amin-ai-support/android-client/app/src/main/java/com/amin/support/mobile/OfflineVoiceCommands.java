package com.amin.support.mobile;

/** Small deterministic commands usable with no server and no AI inference. */
public final class OfflineVoiceCommands {
    private OfflineVoiceCommands() {}

    public static final String NOT_AN_AI = "حالت آفلاین فقط فرمان‌های ثابت را اجرا می‌کند. "
            + "برای پرسش و پاسخ هوشمند باید موتور آنلاین وصل باشد.";

    public static String respond(String heard, boolean answerExists) {
        if (heard == null) return "";
        String t = heard.trim().replace("ي", "ی").replace("ك", "ک")
                .replace("‌", "").replace(" ", "");
        if (t.equals("راهنما") || t.equals("دستورها") || t.equals("راهنمایصوتی")) {
            return "فرمان‌های آفلاین: راهنما، وضعیت اتصال، خواندن پاسخ قبلی. "
                    + "پرسش هوشمند تازه نیاز به اینترنت دارد.";
        }
        if (t.equals("وضعیتاتصال") || t.equals("اینترنتموصله")
                || t.equals("آفلاینی")) {
            return "این پاسخ از فهرست فرمان‌های ثابت آفلاین است، "
                    + "نه تأیید اتصال واقعی به اینترنت یا ChatGPT.";
        }
        if (t.equals("خواندنپاسخقبلی") || t.equals("پاسخقبلیرابخوان")) {
            return answerExists ? "__READ_LAST_ANSWER__"
                    : "هنوز پاسخی برای خواندن در این صفحه موجود نیست.";
        }
        return "";
    }
}
