package com.amin.support.mobile;

public final class LiveEndpointPolicyTest {
    private static int passed = 0;
    static void ok(boolean value) {
        if (!value) throw new AssertionError("Live endpoint policy failed");
        passed++;
    }
    static void deny(String raw) {
        try {
            LiveEndpointPolicy.requireWss(raw);
            throw new AssertionError("Unsafe URL accepted: " + raw);
        } catch (IllegalArgumentException expected) {
            passed++;
        }
    }
    public static void main(String[] ignored) {
        ok(LiveEndpointPolicy.requireWss("wss://example.com:8766")
                .equals("wss://example.com:8766/"));
        ok(LiveEndpointPolicy.project("support").equals("support"));
        ok(LiveEndpointPolicy.jobId("a".repeat(32)).length() == 32);
        for (String raw : new String[]{"ws://example.com:8766",
                "ws://127.0.0.1:8766", "https://example.com",
                "wss://someone:password@example.com", "wss://example.com/path",
                "wss://example.com/?token=secret", "wss://example.com/#fragment",
                "wss://example.com:0", ""}) deny(raw);
        System.out.println("Live WSS policy passed: " + passed);
    }
}
