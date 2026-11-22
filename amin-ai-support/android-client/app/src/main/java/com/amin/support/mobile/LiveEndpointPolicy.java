package com.amin.support.mobile;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Remote live sockets must use trustworthy WSS, not plaintext WS. */
public final class LiveEndpointPolicy {
    private LiveEndpointPolicy() {}

    public static String requireWss(String input) {
        if (input == null || input.trim().length() > 300)
            throw new IllegalArgumentException("نشانی کانال زنده نامعتبر است");
        try {
            URI parsed = new URI(input.trim());
            if (!"wss".equalsIgnoreCase(parsed.getScheme())
                    || parsed.getHost() == null
                    || parsed.getRawUserInfo() != null
                    || parsed.getRawQuery() != null
                    || parsed.getRawFragment() != null
                    || (parsed.getRawPath() != null && !parsed.getRawPath().isEmpty()
                        && !"/".equals(parsed.getRawPath()))
                    || parsed.getPort() == 0
                    || parsed.getPort() > 65535
                    || parsed.getRawAuthority().contains("%")
                    || parsed.getRawAuthority().contains("\\"))
                throw new IllegalArgumentException("کانال زنده باید WSS امن بدون پارامتر یا مسیر اضافی باشد");
            return "wss://" + parsed.getRawAuthority().toLowerCase(Locale.ROOT) + "/";
        } catch (URISyntaxException error) {
            throw new IllegalArgumentException("نشانی WSS معتبر نیست");
        }
    }

    public static String project(String input) {
        if (input == null || !input.matches("[a-z][a-z0-9_-]{1,60}"))
            throw new IllegalArgumentException("شناسه نرم‌افزار نامعتبر است");
        return input;
    }

    public static String jobId(String input) {
        if (input == null || !input.matches("[a-f0-9]{32}"))
            throw new IllegalArgumentException("شناسه کار معتبر نیست");
        return input;
    }
}
