package com.amin.support.mobile;

/** No Android dependencies: executable JVM security checks for endpoint policy. */
public final class MobileEndpointTest {
    private static int checked = 0;

    private static void ok(boolean condition, String description) {
        checked++;
        if (!condition) throw new AssertionError(description);
    }

    private static void denied(String value) {
        boolean blocked = false;
        try {
            SupportEndpoint.normalize(value);
        } catch (IllegalArgumentException expected) {
            blocked = true;
        }
        ok(blocked, "must reject URL " + value);
    }

    private static void badToken(String value) {
        boolean blocked = false;
        try {
            SupportEndpoint.validateToken(value);
        } catch (IllegalArgumentException expected) {
            blocked = true;
        }
        ok(blocked, "must reject inappropriate key");
    }

    public static void main(String[] ignored) {
        String domain = "https://support.example.org";
        ok(domain.equals(SupportEndpoint.normalize(domain)), "HTTPS domain");
        ok(domain.equals(SupportEndpoint.normalize(domain + "/")), "remove slash");
        ok(domain.equals(SupportEndpoint.normalize("HTTPS://SUPPORT.EXAMPLE.ORG")),
                "host canonical");
        ok("https://support.example.org:8443".equals(
                SupportEndpoint.normalize(domain + ":8443")), "HTTPS port");
        ok((domain + "/api/projects").equals(
                SupportEndpoint.apiUrl(domain, "/api/projects")), "projects route");
        ok((domain + "/api/chat").equals(
                SupportEndpoint.apiUrl(domain, "/api/chat")), "chat route");

        for (String url : new String[] {
            "", "http://support.example.org", "http://127.0.0.1:8765",
            "file:///tmp/file", "https://support.example.org/private",
            "https://support.example.org/?x=1",
            "https://support.example.org/#fragment",
            "https://login:password@support.example.org",
            "https://support.example.org:0",
            "https://support.example.org:99999",
            "https://support.example.org/a/../b",
            "https://support.example.org/%2e%2e",
            "https://support.example.org\\@evil.example",
        }) denied(url);

        String key = "amin_" + "ABCDEFGHIJKLMNOPQRSTUVabcdefghi1234567890ABCD";
        ok(key.equals(SupportEndpoint.validateToken(key)), "scoped key accepted");
        badToken("");
        badToken("ghp_1234");
        badToken("owner-master-key");
        badToken("amin_short");
        badToken("amin_" + "x".repeat(200));
        boolean unknownRoute = false;
        try {
            SupportEndpoint.apiUrl(domain, "/api/issue-access");
        } catch (IllegalArgumentException expected) {
            unknownRoute = true;
        }
        ok(unknownRoute, "client cannot invoke admin endpoints");
        System.out.println("Amin mobile endpoint JVM checks passed: " + checked);
    }
}
