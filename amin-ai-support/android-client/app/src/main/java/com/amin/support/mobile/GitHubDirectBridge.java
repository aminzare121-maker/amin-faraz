package com.amin.support.mobile;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import android.util.Base64;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Locale;

import javax.net.ssl.HttpsURLConnection;

/**
 * Optional serverless relay to the user's OWN PRIVATE GitHub repository.
 * This does NOT invoke a ChatGPT chat itself: the user's connected agent must
 * separately read the issue and write AMIN_CHAT_REPLY_V1 in a comment.
 * No GitHub access token is included in Issue content or URL.
 */
public final class GitHubDirectBridge {
    private static final String API = "https://api.github.com/repos/";
    private static final int MAX_REPLY = 256000;
    private final String repo;
    private final String token;

    public GitHubDirectBridge(String repo, String token) {
        this.repo = GitHubBridgePolicy.repo(repo);
        this.token = GitHubBridgePolicy.token(token);
    }

    private JSONObject call(String method, String path, JSONObject payload) throws Exception {
        URL url = new URL(API + repo + path);
        if (!"api.github.com".equals(url.getHost()) || !"https".equals(url.getProtocol())) {
            throw new IllegalArgumentException("نشانی GitHub نامعتبر است");
        }
        HttpsURLConnection conn = (HttpsURLConnection) url.openConnection();
        conn.setInstanceFollowRedirects(false);
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(20000);
        conn.setUseCaches(false);
        conn.setRequestProperty("Authorization", "Bearer " + token);
        conn.setRequestProperty("Accept", "application/vnd.github+json");
        conn.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
        conn.setRequestProperty("Cache-Control", "no-store");
        conn.setRequestProperty("User-Agent", "AminSupportPrivateMobile/0.2");
        try {
            conn.setRequestMethod(method);
            if (payload != null) {
                byte[] data = payload.toString().getBytes(StandardCharsets.UTF_8);
                if (data.length > 15000) throw new IllegalArgumentException("درخواست بیش از حد طولانی است");
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                conn.setFixedLengthStreamingMode(data.length);
                try (OutputStream out = conn.getOutputStream()) { out.write(data); }
            }
            int code = conn.getResponseCode();
            if (code == 301 || code == 302 || code == 303 || code == 307 || code == 308)
                throw new IllegalStateException("تغییر مسیر GitHub برای حفاظت از توکن رد شد");
            if (code == 401) throw new IllegalStateException("توکن GitHub نامعتبر یا منقضی است");
            if (code == 403) throw new IllegalStateException("دسترسی به مخزن یا سهمیه API مجاز نیست (403)");
            if (code == 404) throw new IllegalStateException("مخزن خصوصی یا درخواست موردنظر در دسترس نیست (404)");
            if (code != 200 && code != 201)
                throw new IllegalStateException("GitHub پاسخ معتبر نداد: " + code);
            try (InputStream in = conn.getInputStream();
                 ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
                byte[] chunk = new byte[4096];
                int n;
                while ((n = in.read(chunk)) != -1) {
                    if (buffer.size() + n > MAX_REPLY)
                        throw new IllegalStateException("پاسخ GitHub خیلی بزرگ است");
                    buffer.write(chunk, 0, n);
                }
                return new JSONObject(new String(buffer.toByteArray(), StandardCharsets.UTF_8));
            }
        } finally {
            conn.disconnect();
        }
    }

    private JSONArray callComments(int issue) throws Exception {
        // Do not parse unbounded comment history: a dedicated issue should be short.
        JSONObject wrapper = call("GET", "/issues/" + GitHubBridgePolicy.issue(issue), null);
        JSONArray result = new JSONArray();
        if (!wrapper.optString("body", "").startsWith("AMIN_CHAT_BRIDGE_V1\n"))
            throw new IllegalStateException("این Issue متعلق به کانال هوش امین نیست");
        return result; // use readComments below to fetch the true JSON array
    }

    private JSONArray readComments(int issue) throws Exception {
        URL url = new URL(API + repo + "/issues/" + GitHubBridgePolicy.issue(issue)
                + "/comments?per_page=100");
        HttpsURLConnection conn = (HttpsURLConnection) url.openConnection();
        conn.setInstanceFollowRedirects(false);
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(20000);
        conn.setRequestProperty("Authorization", "Bearer " + token);
        conn.setRequestProperty("Accept", "application/vnd.github+json");
        conn.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
        conn.setRequestProperty("Cache-Control", "no-store");
        conn.setRequestProperty("User-Agent", "AminSupportPrivateMobile/0.2");
        try {
            int code = conn.getResponseCode();
            if (code != 200) throw new IllegalStateException("خواندن پاسخ GitHub ناموفق: " + code);
            try (InputStream in = conn.getInputStream();
                 ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
                byte[] chunk = new byte[4096]; int n;
                while ((n = in.read(chunk)) != -1) {
                    if (buffer.size() + n > MAX_REPLY)
                        throw new IllegalStateException("پاسخ بیش از حد بزرگ است");
                    buffer.write(chunk, 0, n);
                }
                return new JSONArray(new String(buffer.toByteArray(), StandardCharsets.UTF_8));
            }
        } finally {
            conn.disconnect();
        }
    }

    public JSONObject verifyPrivate() throws Exception {
        JSONObject info = call("GET", "", null);
        if (!info.optBoolean("private", false))
            throw new IllegalStateException("این مخزن عمومی است؛ انتقال متن خصوصی مسدود شد");
        if (!repo.equalsIgnoreCase(info.optString("full_name", "")))
            throw new IllegalStateException("نام مخزن با حساب متصل مطابقت ندارد");
        if (!info.optBoolean("has_issues", true))
            throw new IllegalStateException("بخش Issues مخزن غیرفعال است");
        return info;
    }

    public JSONObject submit(String project, String question) throws Exception {
        GitHubBridgePolicy.project(project);
        if (question == null || question.trim().isEmpty() || question.length() > 2500)
            throw new IllegalArgumentException("درخواست باید بین ۱ تا ۲۵۰۰ نویسه باشد");
        // Fail closed before any private text is sent to GitHub.
        verifyPrivate();
        byte[] bytes = new byte[16];
        new SecureRandom().nextBytes(bytes);
        StringBuilder hex = new StringBuilder();
        for (byte b : bytes) hex.append(String.format(Locale.ROOT, "%02x", b & 255));
        String id = hex.toString();
        JSONObject envelope = new JSONObject();
        envelope.put("request_id", id);
        envelope.put("project", project);
        envelope.put("device", "android");
        envelope.put("question", question.trim());
        envelope.put("consent", true);
        envelope.put("result_required", "AMIN_CHAT_REPLY_V1");
        JSONObject issue = new JSONObject();
        issue.put("title", "[Amin private support] " + id.substring(0, 12));
        issue.put("body", "AMIN_CHAT_BRIDGE_V1\n" + envelope.toString());
        JSONObject created = call("POST", "/issues", issue);
        int number = created.optInt("number", 0);
        if (number <= 0) throw new IllegalStateException("Issue ایجاد شد اما شناسه دریافت نشد");
        JSONObject result = new JSONObject();
        result.put("request_id", id);
        result.put("issue_number", number);
        result.put("status", "submitted_to_private_github");
        result.put("chatgpt_invoked", false);
        return result;
    }

    /**
     * Create a PRIVATE GitHub Pull Request event supported by ChatGPT Work.
     * Does NOT call ChatGPT, use Codex, or send an OpenAI API key.
     * A separately configured ChatGPT Work event-triggered task is required.
     *
     * GitHub fine-grained PAT needs Issues:read, Contents:write, Pull requests:write.
     */
    public JSONObject triggerChatGPTWork(int issue, String requestId) throws Exception {
        GitHubBridgePolicy.issue(issue);
        GitHubBridgePolicy.requestId(requestId);
        JSONObject repository = verifyPrivate();
        JSONObject original = call("GET", "/issues/" + issue, null);
        String owner = repository.getJSONObject("owner").getString("login");
        JSONObject author = original.optJSONObject("user");
        if (original.has("pull_request") || author == null
                || !owner.equalsIgnoreCase(author.optString("login", "")))
            throw new IllegalStateException("فقط درخواست مالک مخزن خصوصی مجاز است");
        String raw = original.optString("body", "");
        String marker = "AMIN_CHAT_BRIDGE_V1\n";
        if (!raw.startsWith(marker))
            throw new IllegalStateException("قالب درخواست ChatGPT معتبر نیست");
        JSONObject details = new JSONObject(raw.substring(marker.length()));
        if (!requestId.equals(details.optString("request_id", ""))
                || !details.optBoolean("consent", false)
                || details.optBoolean("test_only", false))
            throw new IllegalStateException("رضایت کاربر یا شناسه درخواست معتبر نیست");
        String project = GitHubBridgePolicy.project(details.optString("project", ""));
        String base = repository.optString("default_branch", "main");
        if (!base.matches("[A-Za-z0-9_.-]{1,80}"))
            throw new IllegalStateException("نام شاخه اصلی مخزن پشتیبانی نمی‌شود");
        JSONObject baseline = call("GET", "/git/ref/heads/" + base, null);
        String sha = baseline.getJSONObject("object").getString("sha");
        if (!sha.matches("[a-fA-F0-9]{40}"))
            throw new IllegalStateException("SHA پایه مخزن معتبر نیست");

        String branch = "amin-chatgpt-work/" + requestId;
        JSONObject branchRequest = new JSONObject()
                .put("ref", "refs/heads/" + branch).put("sha", sha);
        call("POST", "/git/refs", branchRequest);

        // Deliberately keep the QUESTION in the private Issue only, not in
        // committed Git files or the PR body.
        JSONObject payload = new JSONObject()
                .put("protocol", "AMIN_CHATGPT_WORK_PR_V1")
                .put("request_id", requestId)
                .put("issue_number", issue)
                .put("project", project)
                .put("consent", true)
                .put("execution_authorized", false)
                .put("personal_chatgpt_invoked", false);
        String content = Base64.encodeToString(
                (payload.toString() + "\n").getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP);
        call("PUT", "/contents/.amin-chatgpt-work/requests/" + requestId + ".json",
                new JSONObject().put("message", "chore: request ChatGPT Work " + requestId.substring(0, 12))
                        .put("branch", branch).put("content", content));
        JSONObject prBody = new JSONObject()
                .put("request_id", requestId).put("issue_number", issue)
                .put("project", project).put("question_location", "private_issue")
                .put("permission", "read_and_respond_only")
                .put("execution_authorized", false);
        JSONObject pr = call("POST", "/pulls", new JSONObject()
                .put("title", "[Amin ChatGPT Work] " + requestId.substring(0, 12))
                .put("body", "AMIN_CHATGPT_WORK_PR_V1\n" + prBody.toString())
                .put("head", branch).put("base", base).put("draft", false));
        int prNumber = pr.optInt("number", 0);
        if (prNumber <= 0) throw new IllegalStateException("شماره Pull Request دریافت نشد");
        return new JSONObject()
                .put("pull_request_number", prNumber)
                .put("private_pr_event_created", true)
                .put("chatgpt_invoked", false)
                .put("chatgpt_task_configured", false)
                .put("reply_delivered", false);
    }

    public JSONObject approve(int issue, String requestId, String project) throws Exception {
        GitHubBridgePolicy.issue(issue);
        GitHubBridgePolicy.requestId(requestId);
        GitHubBridgePolicy.project(project);
        JSONObject state = status(issue, requestId);
        if (!"answered".equals(state.optString("status", "")))
            throw new IllegalStateException("فقط پاسخ دریافت‌شده قابل تأیید است");
        JSONObject source = call("GET", "/issues/" + issue, null);
        String body = source.optString("body", "");
        if (!body.startsWith("AMIN_CHAT_BRIDGE_V1\n"))
            throw new IllegalStateException("درخواست معتبر نیست");
        JSONObject envelope = new JSONObject(body.substring("AMIN_CHAT_BRIDGE_V1\n".length()));
        if (!project.equals(envelope.optString("project", "")))
            throw new IllegalStateException("پروژه درخواست مطابقت ندارد");
        String owner = verifyPrivate().getJSONObject("owner").getString("login");
        JSONArray comments = readComments(issue);
        for (int i = 0; i < comments.length(); i++) {
            JSONObject c = comments.optJSONObject(i);
            if (c == null || c.optJSONObject("user") == null) continue;
            if (!owner.equalsIgnoreCase(c.getJSONObject("user").optString("login", ""))) continue;
            String comment = c.optString("body", "");
            if (!comment.startsWith("AMIN_LESSON_APPROVED_V1\n")) continue;
            try {
                JSONObject approval = new JSONObject(comment.substring("AMIN_LESSON_APPROVED_V1\n".length()));
                if (requestId.equals(approval.optString("request_id"))
                        && project.equals(approval.optString("project"))) {
                    return new JSONObject().put("approved", true).put("already_approved", true);
                }
            } catch (org.json.JSONException malformed) { /* ignore malformed comments */ }
        }
        JSONObject approval = new JSONObject();
        approval.put("request_id", requestId);
        approval.put("project", project);
        approval.put("approved", true);
        call("POST", "/issues/" + issue + "/comments",
                new JSONObject().put("body", "AMIN_LESSON_APPROVED_V1\n" + approval.toString()));
        return new JSONObject().put("approved", true).put("already_approved", false);
    }

    public JSONObject status(int issue, String id) throws Exception {
        GitHubBridgePolicy.issue(issue);
        GitHubBridgePolicy.requestId(id);
        JSONObject repository = verifyPrivate();
        JSONObject original = call("GET", "/issues/" + issue, null);
        String body = original.optString("body", "");
        if (!body.startsWith("AMIN_CHAT_BRIDGE_V1\n"))
            throw new IllegalStateException("قالب درخواست معتبر نیست");
        JSONObject envelope = new JSONObject(body.substring("AMIN_CHAT_BRIDGE_V1\n".length()));
        if (!id.equals(envelope.optString("request_id", "")))
            throw new IllegalStateException("شناسه درخواست با حساب همخوان نیست");
        String expectedOwner = repository.getJSONObject("owner").getString("login");
        JSONArray comments = readComments(issue);
        for (int index = comments.length() - 1; index >= 0; index--) {
            JSONObject comment = comments.optJSONObject(index);
            if (comment == null) continue;
            JSONObject user = comment.optJSONObject("user");
            if (user == null) continue;
            String raw = comment.optString("body", "");
            if (!GitHubBridgePolicy.isTrustedReply(user.optString("login", ""), expectedOwner, raw, id))
                continue;
            try {
                JSONObject reply = new JSONObject(raw.substring("AMIN_CHAT_REPLY_V1\n".length()));
                if (!id.equals(reply.optString("request_id", ""))
                        || !"answered".equals(reply.optString("status", ""))) continue;
                String answer = reply.optString("answer", "");
                if (answer.isEmpty() || answer.length() > 4000) continue;
                JSONObject result = new JSONObject().put("status", "answered")
                        .put("answer", answer).put("issue_number", issue)
                        .put("request_id", id);
                JSONObject artifact = reply.optJSONObject("artifact");
                if (artifact != null && "android".equals(artifact.optString("environment", ""))) {
                    try {
                        String release = DeliveryPolicy.releaseUrl(artifact.optString("url", ""));
                        String digest = DeliveryPolicy.sha256(artifact.optString("sha256", ""));
                        result.put("artifact", new JSONObject()
                                .put("environment", "android")
                                .put("url", release).put("sha256", digest)
                                .put("user_approval_required", true)
                                .put("installed", false));
                    } catch (IllegalArgumentException invalid) {
                        // Ignore unsafe or incomplete delivery metadata.
                    }
                }
                return result;
            } catch (org.json.JSONException malformed) {
                // Untrusted comment is ignored.
            }
        }
        return new JSONObject().put("status", "pending")
                .put("issue_number", issue).put("request_id", id);
    }
}
