package com.amin.support.mobile;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Allow only GitHub-owned HTTPS release assets for explicit APK installation. */
public final class DeliveryPolicy {
    private DeliveryPolicy() {}

    public static String sha256(String digest) {
        if (digest == null || !digest.matches("[a-fA-F0-9]{64}"))
            throw new IllegalArgumentException("اثر انگشت SHA-256 فایل لازم است");
        return digest.toLowerCase(Locale.ROOT);
    }

    public static String releaseUrl(String value) {
        if (value == null || value.length() > 400)
            throw new IllegalArgumentException("نشانی فایل معتبر نیست");
        try {
            URI uri = new URI(value);
            String path = uri.getRawPath();
            if (!"https".equalsIgnoreCase(uri.getScheme())
                    || !"github.com".equalsIgnoreCase(uri.getHost())
                    || uri.getPort() != -1 || uri.getRawUserInfo() != null
                    || uri.getRawQuery() != null || uri.getRawFragment() != null
                    || path == null || path.contains("%") || path.contains("..")
                    || !path.matches("/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/releases/download/"
                        + "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\\.apk")) {
                throw new IllegalArgumentException("فقط APK انتشار رسمی GitHub با HTTPS مجاز است");
            }
            return uri.toASCIIString();
        } catch (URISyntaxException e) {
            throw new IllegalArgumentException("نشانی فایل معتبر نیست");
        }
    }

    public static void verifyRedirect(String value) {
        try {
            URI uri = new URI(value);
            String host = uri.getHost();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null
                    || !("release-assets.githubusercontent.com".equalsIgnoreCase(host)
                        || "objects.githubusercontent.com".equalsIgnoreCase(host))
                    || uri.getRawUserInfo() != null || uri.getPort() != -1) {
                throw new IllegalArgumentException("مقصد دانلود تأیید نشده است");
            }
        } catch (URISyntaxException e) {
            throw new IllegalArgumentException("نشانی انتقال نامعتبر است");
        }
    }
}
