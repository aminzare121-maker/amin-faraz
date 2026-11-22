package com.amin.support.mobile;

public final class DeliveryPolicyTest {
    static int count=0;
    static void ok(boolean success) {count++; if(!success)throw new AssertionError("failed");}
    static void deny(String candidate) {
        try { DeliveryPolicy.releaseUrl(candidate); throw new AssertionError(candidate); }
        catch (IllegalArgumentException expected) {count++;}
    }
    public static void main(String[] args) {
        String sha="a".repeat(64);
        ok(DeliveryPolicy.sha256(sha).equals(sha));
        ok(DeliveryPolicy.releaseUrl("https://github.com/owner/app/releases/download/v1/amin.apk")
                .endsWith("/amin.apk"));
        for(String url:new String[]{
                "http://github.com/a/b/releases/download/v1/app.apk",
                "https://evil.com/a/b/releases/download/v1/app.apk",
                "https://github.com/a/b/actions/runs/123",
                "https://github.com/a/b/releases/download/v1/../evil.apk",
                "https://github.com/a/b/releases/download/v1/app.apk?token=x",
                "https://user:pass@github.com/a/b/releases/download/v1/app.apk",
                "https://github.com/a/b/releases/download/v1/%61pp.apk"})deny(url);
        DeliveryPolicy.verifyRedirect("https://release-assets.githubusercontent.com/file");
        try {DeliveryPolicy.verifyRedirect("https://attacker.example/file");throw new AssertionError();}
        catch(IllegalArgumentException expected){count++;}
        System.out.println("Delivery policy tests passed: "+count);
    }
}
