package com.amin.support.mobile;

import java.net.URI;
import java.util.Locale;
import java.util.regex.Pattern;

/** Pure Java validation: server address must be HTTPS with a trustworthy TLS certificate. */
public final class SupportEndpoint {
    private static final Pattern TOKEN =
            Pattern.compile("amin_[A-Za-z0-9_-]{40,60}");

    private SupportEndpoint() {}

    public static String normalize(String value) {
        if (value == null || value.length() > 280) {
            throw new IllegalArgumentException("نشانی سرور معتبر نیست.");
        }
        try {
            URI uri = new URI(value.trim());
            if (!"https".equalsIgnoreCase(uri.getScheme())
                    || uri.getHost() == null
                    || uri.getHost().isEmpty()
                    || uri.getUserInfo() != null
                    || uri.getRawQuery() != null
                    || uri.getRawFragment() != null
                    || (uri.getRawPath() != null
                        && !uri.getRawPath().isEmpty()
                        && !"/".equals(uri.getRawPath()))
                    || uri.getPort() > 65535
                    || uri.getPort() == 0) {
                throw new IllegalArgumentException("نشانی باید HTTPS بدون رمز، مسیر اضافی یا پارامتر باشد.");
            }
            String authority = uri.getRawAuthority();
            if (authority == null || authority.contains("@")
                    || authority.contains("\\") || authority.contains("%")) {
                throw new IllegalArgumentException("نشانی سرور معتبر نیست.");
            }
            return "https://" + authority.toLowerCase(Locale.ROOT);
        } catch (java.net.URISyntaxException problem) {
            throw new IllegalArgumentException("نشانی سرور معتبر نیست.");
        }
    }

    /** Scoped customer credential, not a GitHub token or owner's master key. */
    public static String validateToken(String token) {
        if (token == null || !TOKEN.matcher(token.trim()).matches()) {
            throw new IllegalArgumentException("کلید دسترسی مخصوص همین نرم‌افزار لازم است.");
        }
        return token.trim();
    }

    public static String apiUrl(String endpoint, String route) {
        if (!"/api/projects".equals(route) && !"/api/chat".equals(route)) {
            throw new IllegalArgumentException("مسیر API مجاز نیست.");
        }
        return normalize(endpoint) + route;
    }
}
