package com.amin.support.mobile;

import java.util.Locale;
import java.util.regex.Pattern;

/** Pure-JVM policy for a per-user GitHub PRIVATE repo, not an open source issue queue. */
public final class GitHubBridgePolicy {
    private static final Pattern PART = Pattern.compile("[A-Za-z0-9][A-Za-z0-9_.-]{0,99}");
    private static final Pattern TOKEN = Pattern.compile("(github_pat_|ghp_|gho_)[A-Za-z0-9_-]{20,240}");
    private static final Pattern IDENT = Pattern.compile("[a-f0-9]{32}");

    private GitHubBridgePolicy() {}

    public static String repo(String raw) {
        if (raw == null || raw.length() > 201) throw new IllegalArgumentException("نشانی مخزن معتبر نیست");
        String[] parts = raw.trim().split("/", -1);
        if (parts.length != 2 || !PART.matcher(parts[0]).matches() || !PART.matcher(parts[1]).matches()
                || parts[0].equals(".") || parts[0].equals("..")
                || parts[1].equals(".") || parts[1].equals(".."))
            throw new IllegalArgumentException("مخزن را به شکل owner/repo وارد کن");
        return parts[0] + "/" + parts[1];
    }

    public static String token(String raw) {
        if (raw == null || !TOKEN.matcher(raw.trim()).matches())
            throw new IllegalArgumentException("توکن محدود GitHub موردنیاز است");
        return raw.trim();
    }

    public static String project(String raw) {
        if (raw == null || !raw.matches("[a-z][a-z0-9_-]{1,50}"))
            throw new IllegalArgumentException("شناسه نرم‌افزار معتبر نیست");
        return raw;
    }

    public static String requestId(String raw) {
        if (raw == null || !IDENT.matcher(raw).matches()) throw new IllegalArgumentException("شناسه درخواست معتبر نیست");
        return raw;
    }

    public static int issue(int value) {
        if (value < 1) throw new IllegalArgumentException("شماره درخواست معتبر نیست");
        return value;
    }

    public static boolean isTrustedReply(String author, String expectedOwner, String body,
                                         String requestId) {
        if (author == null || expectedOwner == null || body == null || requestId == null) return false;
        String sender = author.toLowerCase(Locale.ROOT);
        String owner = expectedOwner.toLowerCase(Locale.ROOT);
        if (!sender.equals(owner) && !sender.equals("github-actions[bot]")) return false;
        return body.startsWith("AMIN_CHAT_REPLY_V1\n") && requestId.matches("[a-f0-9]{32}");
    }
}
