package com.amin.support.mobile;

import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;

import javax.net.ssl.HttpsURLConnection;

/** User-approved environment adapter: download, verify bytes, invoke system installer.
 * No remote code execution, shell commands, stealth installation, or model-issued auto-install.
 */
public final class AndroidDelivery {
    private static final long MAX_APK = 150L * 1024 * 1024;
    private AndroidDelivery() {}

    public static File downloadVerified(Context context, String release, String sha256) throws Exception {
        String url = DeliveryPolicy.releaseUrl(release);
        String expected = DeliveryPolicy.sha256(sha256);
        File folder = new File(context.getCacheDir(), "verified-apk-deliveries");
        if (!folder.exists() && !folder.mkdirs()) throw new IllegalStateException("ساخت محل فایل ناموفق بود");
        File destination = new File(folder, expected + ".apk");
        if (destination.exists() && verify(destination, expected)) return destination;
        File staged = new File(folder, expected + ".downloading");
        if (staged.exists()) staged.delete();
        try {
            URL target = new URL(url);
            for (int redirects = 0; redirects < 5; redirects++) {
                HttpsURLConnection connection = (HttpsURLConnection) target.openConnection();
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(12000);
                connection.setReadTimeout(25000);
                connection.setRequestProperty("User-Agent", "AminSupportDelivery/0.1");
                try {
                    int status = connection.getResponseCode();
                    if (status == 301 || status == 302 || status == 303 || status == 307 || status == 308) {
                        String location = connection.getHeaderField("Location");
                        if (location == null) throw new IllegalStateException("نشانی انتقال فایل موجود نیست");
                        URL redirect = new URL(target, location);
                        DeliveryPolicy.verifyRedirect(redirect.toString());
                        target = redirect;
                        continue;
                    }
                    if (status != 200) throw new IllegalStateException("دریافت فایل ناموفق: " + status);
                    long length = connection.getContentLengthLong();
                    if (length > MAX_APK) throw new IllegalStateException("فایل بیش از حد بزرگ است");
                    MessageDigest hash = MessageDigest.getInstance("SHA-256");
                    try (InputStream input = connection.getInputStream();
                         FileOutputStream output = new FileOutputStream(staged)) {
                        byte[] buffer = new byte[32 * 1024];
                        long received = 0;
                        for (int n; (n = input.read(buffer)) != -1;) {
                            received += n;
                            if (received > MAX_APK) throw new IllegalStateException("حجم بیش از حد مجاز است");
                            output.write(buffer, 0, n);
                            hash.update(buffer, 0, n);
                        }
                        output.getFD().sync();
                    }
                    if (!hex(hash.digest()).equals(expected)) {
                        throw new SecurityException("SHA-256 فایل با اطلاعات انتشار مطابقت ندارد؛ نصب مسدود شد");
                    }
                    if (!staged.renameTo(destination))
                        throw new IllegalStateException("انتقال فایل بررسی‌شده به مقصد ناموفق بود");
                    return destination;
                } finally {
                    connection.disconnect();
                }
            }
            throw new IllegalStateException("تغییر مسیرهای دانلود بیش از حد است");
        } finally {
            if (staged.exists()) staged.delete();
        }
    }

    private static boolean verify(File file, String sha) {
        try (java.io.FileInputStream input = new java.io.FileInputStream(file)) {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[16384];
            for (int n; (n=input.read(buffer)) != -1;) digest.update(buffer, 0, n);
            return hex(digest.digest()).equals(sha);
        } catch (Exception problem) { return false; }
    }

    private static String hex(byte[] data) {
        StringBuilder result = new StringBuilder();
        for (byte b : data) result.append(String.format(Locale.ROOT, "%02x", b & 255));
        return result.toString();
    }

    public static boolean canRequestInstall(Context context) {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.O
                || context.getPackageManager().canRequestPackageInstalls();
    }

    public static void askInstallPermission(Context context) {
        Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:" + context.getPackageName()));
        settings.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(settings);
    }

    public static void launchSystemInstaller(Context context, File verifiedApk) {
        if (!verifiedApk.isFile() || !verifiedApk.getName().matches("[a-f0-9]{64}\\.apk")) {
            throw new IllegalArgumentException("فایل APK تأیید شده موجود نیست");
        }
        Uri fileUri = FileProvider.getUriForFile(context,
                context.getPackageName() + ".verifiedfiles", verifiedApk);
        Intent install = new Intent(Intent.ACTION_VIEW);
        install.setDataAndType(fileUri, "application/vnd.android.package-archive");
        install.setFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(install);
        // Only Android's system installer can finalize the user's explicit install approval.
    }
}
