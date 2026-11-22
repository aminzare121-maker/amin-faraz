package com.amin.support.mobile;

public final class GitHubBridgePolicyTest {
    private static int passed = 0;
    private static void ok(boolean b, String message) {
        passed++; if (!b) throw new AssertionError(message);
    }
    private static void denyRepo(String repo) {
        try { GitHubBridgePolicy.repo(repo); throw new AssertionError("unsafe repo accepted"); }
        catch (IllegalArgumentException expected) { passed++; }
    }
    public static void main(String[] ignored) {
        ok(GitHubBridgePolicy.repo("owner/private").equals("owner/private"), "private route");
        ok(GitHubBridgePolicy.project("support").equals("support"), "program");
        ok(GitHubBridgePolicy.token("github_pat_" + "x".repeat(50)).startsWith("github_pat_"), "token");
        for (String repo : new String[]{"https://github.com/a/b", "owner/public/other",
                "../repo", "owner/..", "owner\\bad/repo", ""}) denyRepo(repo);
        String id = "a".repeat(32);
        ok(GitHubBridgePolicy.isTrustedReply("Owner", "owner",
                "AMIN_CHAT_REPLY_V1\n{}", id), "owner only");
        ok(GitHubBridgePolicy.isTrustedReply("github-actions[bot]", "owner",
                "AMIN_CHAT_REPLY_V1\n{}", id), "verified GitHub Actions bot");
        ok(!GitHubBridgePolicy.isTrustedReply("other", "owner",
                "AMIN_CHAT_REPLY_V1\n{}", id), "reject non-owner");
        ok(!GitHubBridgePolicy.isTrustedReply("owner", "owner",
                "not a reply", id), "reject text");
        System.out.println("Amin private GitHub policy checks passed: " + passed);
    }
}
