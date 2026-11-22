package com.amin.support.mobile;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;

import javax.net.ssl.HttpsURLConnection;

/** Read-only project listing and chat; scoped HTTPS tokens only. */
public final class SupportApi {
    private static final int MAX_REPLY = 1024 * 1024;
    private final String endpoint;
    private final String token;

    public SupportApi(String endpoint, String token) {
        this.endpoint = SupportEndpoint.normalize(endpoint);
        this.token = SupportEndpoint.validateToken(token);
    }

    public JSONObject projects() throws Exception {
        return exchange("/api/projects", null);
    }

    public JSONObject ask(String projectId, String question) throws Exception {
        return ask(projectId, question, false);
    }

    /** A model may receive the current question only after explicit user opt-in. */
    public JSONObject ask(String projectId, String question, boolean onlineConsent) throws Exception {
        if (projectId == null || !projectId.matches("[a-z][a-z0-9_-]{1,50}")) {
            throw new IllegalArgumentException("شناسه برنامه معتبر نیست.");
        }
        if (question == null || question.trim().isEmpty() || question.length() > 2500) {
            throw new IllegalArgumentException("سؤال باید بین ۱ تا ۲۵۰۰ نویسه باشد.");
        }
        JSONObject payload = new JSONObject();
        payload.put("project", projectId);
        payload.put("message", question.trim());
        // Never silently transmit private questions to Cloudflare's model.
        // The default overload keeps the historical opt-out semantics.
        payload.put("external_model_consent", onlineConsent);
        return exchange("/api/chat", payload);
    }

    /** Optional short-lived history, sent only when the user consented for Cloudflare. */
    public JSONObject ask(String projectId, String question, boolean onlineConsent,
                          java.util.List<ConversationMemory.Turn> previousTurns) throws Exception {
        if (projectId == null || !projectId.matches("[a-z][a-z0-9_-]{1,50}")
                || question == null || question.trim().isEmpty() || question.length() > 2500) {
            throw new IllegalArgumentException("درخواست گفت‌وگو معتبر نیست.");
        }
        JSONObject payload = new JSONObject();
        payload.put("project", projectId);
        payload.put("message", question.trim());
        payload.put("external_model_consent", onlineConsent);
        if (onlineConsent && previousTurns != null && !previousTurns.isEmpty()) {
            org.json.JSONArray context = new org.json.JSONArray();
            if (previousTurns.size() > 6) throw new IllegalArgumentException("تاریخچهٔ بیش از حد مجاز.");
            for (ConversationMemory.Turn turn : previousTurns) {
                JSONObject item = new JSONObject();
                item.put("role", turn.role);
                item.put("content", turn.content);
                context.put(item);
            }
            payload.put("history", context);
        }
        return exchange("/api/chat", payload);
    }

    public JSONObject handoff(String projectId, String question) throws Exception {
        if (projectId == null || !projectId.matches("[a-z][a-z0-9_-]{1,50}")
                || question == null || question.trim().isEmpty() || question.length() > 2500) {
            throw new IllegalArgumentException("درخواست ارجاع معتبر نیست.");
        }
        JSONObject payload = new JSONObject();
        payload.put("project", projectId);
        payload.put("message", question.trim());
        payload.put("consent", true);
        payload.put("external_model_consent", false);
        return exchange("/api/handoff", payload);
    }

    public JSONObject handoffStatus(String projectId, String requestId) throws Exception {
        if (projectId == null || !projectId.matches("[a-z][a-z0-9_-]{1,50}")
                || requestId == null || !requestId.matches("[a-f0-9]{32}")) {
            throw new IllegalArgumentException("شناسه پیگیری معتبر نیست.");
        }
        return exchange("/api/handoff", null, "?id=" + requestId + "&project=" + projectId);
    }

    private JSONObject exchange(String route, JSONObject payload) throws Exception {
        return exchange(route, payload, "");
    }

    private JSONObject exchange(String route, JSONObject payload, String query) throws Exception {
        URL target = new URL(SupportEndpoint.apiUrl(endpoint, route) + query);
        HttpsURLConnection conn = (HttpsURLConnection) target.openConnection();
        conn.setInstanceFollowRedirects(false); // Never forward a bearer token.
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(90000);
        conn.setUseCaches(false);
        conn.setRequestProperty("Authorization", "Bearer " + token);
        conn.setRequestProperty("Accept", "application/json");
        conn.setRequestProperty("Cache-Control", "no-store");
        conn.setRequestProperty("User-Agent", "AminSupportMobile/0.1");
        try {
            if (payload != null) {
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                byte[] data = payload.toString().getBytes(StandardCharsets.UTF_8);
                if (data.length > 16000) throw new IllegalArgumentException("سؤال بیش از حد طولانی است.");
                conn.setFixedLengthStreamingMode(data.length);
                try (OutputStream out = conn.getOutputStream()) { out.write(data); }
            } else {
                conn.setRequestMethod("GET");
            }
            int status = conn.getResponseCode();
            if (status >= 300 && status < 400) {
                throw new IllegalStateException("سرور تغییر مسیر داده؛ ارسال کلید به مقصد جدید مسدود شد.");
            }
            if (status == 401) throw new IllegalStateException("کلید دسترسی معتبر نیست یا لغو شده است.");
            if (status == 402) throw new IllegalStateException("اعتبار این مشتری تمام شده؛ افزایش سهمیه فقط از مالک برنامه.");
            if (status == 403) throw new IllegalStateException("این کلید اجازه دسترسی به این نرم‌افزار را ندارد.");
            if (status == 429) throw new IllegalStateException("تعداد درخواست‌ها بیش از حد مجاز است.");
            if (status == 503) throw new IllegalStateException("موتور پشتیبانی مشغول است؛ بعداً دوباره درخواست بدهید.");
            if (status != 200) throw new IllegalStateException("پاسخ سرور ناموفق است. کد: " + status);
            String type = conn.getContentType();
            if (type == null || !type.toLowerCase(java.util.Locale.ROOT).contains("json")) {
                throw new IllegalStateException("سرور پاسخ JSON نداد.");
            }
            try (InputStream in = conn.getInputStream();
                 ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
                byte[] chunk = new byte[4096];
                int read;
                while ((read = in.read(chunk)) != -1) {
                    if (buffer.size() + read > MAX_REPLY) {
                        throw new IllegalStateException("پاسخ سرور بیش از حد بزرگ است.");
                    }
                    buffer.write(chunk, 0, read);
                }
                return new JSONObject(new String(buffer.toByteArray(), StandardCharsets.UTF_8));
            }
        } finally {
            conn.disconnect();
        }
    }
}
