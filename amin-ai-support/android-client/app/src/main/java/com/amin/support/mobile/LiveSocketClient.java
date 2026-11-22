package com.amin.support.mobile;

import java.net.URI;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

import org.json.JSONObject;

/** Authenticated full-duplex WSS. Credentials are sent in the FIRST TLS frame, never URLs. */
public final class LiveSocketClient {
    public interface Listener {
        void onMessage(JSONObject event);
        void onClosed(String description);
    }

    private final OkHttpClient transport;
    private final WebSocket socket;
    private final Listener listener;
    private final AtomicLong ids = new AtomicLong();
    private volatile boolean ready = false;

    public LiveSocketClient(String wss, String scopedToken, Listener listener) {
        String url = LiveEndpointPolicy.requireWss(wss);
        String safeToken = SupportEndpoint.validateToken(scopedToken);
        this.listener = listener;
        transport = new OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .pingInterval(20, TimeUnit.SECONDS)
                // Redirects must never send a saved scoped token to a new host.
                .followRedirects(false)
                .followSslRedirects(false)
                .build();
        socket = transport.newWebSocket(new Request.Builder().url(url)
                .header("Cache-Control", "no-store").build(), new WebSocketListener() {
            @Override public void onOpen(WebSocket ws, Response response) {
                // Fail closed if a server or intermediary changed the authenticated target.
                URI expected = URI.create(url);
                String host = response.request().url().host();
                int port = response.request().url().port();
                int expectedPort = expected.getPort() == -1 ? 443 : expected.getPort();
                if (!expected.getHost().equalsIgnoreCase(host) || port != expectedPort
                        || !"https".equals(response.request().url().scheme())) {
                    ws.cancel();
                    listener.onClosed("مقصد کانال زنده تغییر کرده؛ کلید ارسال نشد.");
                    return;
                }
                // The server authenticates after WSS negotiation. No credential in URL.
                JSONObject payload = new JSONObject();
                try {
                    payload.put("type", "auth");
                    payload.put("token", safeToken);
                    ws.send(payload.toString());
                } catch (Exception error) {
                    ws.close(1008, "Authentication unavailable");
                }
            }
            @Override public void onMessage(WebSocket ws, String text) {
                try {
                    JSONObject event = new JSONObject(text);
                    if ("ready".equals(event.optString("type"))) ready = true;
                    listener.onMessage(event);
                } catch (Exception ignored) {
                    // Drop malformed frames; never execute server-supplied source code.
                }
            }
            @Override public void onClosing(WebSocket ws, int code, String reason) {
                ready = false;
                ws.close(1000, "closed");
            }
            @Override public void onClosed(WebSocket ws, int code, String reason) {
                ready = false;
                listener.onClosed("کانال زنده قطع شد (" + code + ")");
            }
            @Override public void onFailure(WebSocket ws, Throwable error, Response response) {
                ready = false;
                // Do not reveal endpoint credentials or request content in diagnostics.
                listener.onClosed("اتصال WSS برقرار نشد: " + error.getClass().getSimpleName());
            }
        });
    }

    public boolean isReady() { return ready; }

    private String send(String type, String project, String message, String jobId) throws Exception {
        if (!ready) throw new IllegalStateException("کانال زنده هنوز احراز هویت نشده است");
        String ident = "a" + ids.incrementAndGet();
        JSONObject event = new JSONObject();
        event.put("type", type);
        event.put("id", ident);
        event.put("project", LiveEndpointPolicy.project(project));
        if (message != null) event.put("message", message);
        if ("work".equals(type)) event.put("consent", true);
        if (jobId != null) event.put("job_id", LiveEndpointPolicy.jobId(jobId));
        if (!socket.send(event.toString()))
            throw new IllegalStateException("ارسال زنده در صف قرار نگرفت");
        return ident;
    }

    public String ask(String project, String message) throws Exception {
        return ask(project, message, false, 0);
    }

    /** Audio never carries credentials or the user's microphone recording. */
    public String ask(String project, String message, boolean neuralVoice, int voiceStyle)
            throws Exception {
        requireText(message);
        if (voiceStyle != 0 && voiceStyle != 1)
            throw new IllegalArgumentException("Invalid Persian voice style");
        if (!ready) throw new IllegalStateException("WSS is not authenticated");
        String ident = "a" + ids.incrementAndGet();
        JSONObject event = new JSONObject();
        event.put("type", "ask");
        event.put("id", ident);
        event.put("project", LiveEndpointPolicy.project(project));
        event.put("message", message);
        event.put("neural_voice", neuralVoice);
        event.put("voice_style", voiceStyle);
        if (!socket.send(event.toString()))
            throw new IllegalStateException("Voice-enabled question could not be queued");
        return ident;
    }

    public String work(String project, String message) throws Exception {
        return work(project, message, "none", "answer");
    }

    public String work(String project, String message, String target,
                       String operation) throws Exception {
        return work(project, message, target, operation, false);
    }

    public String work(String project, String message, String target,
                       String operation, boolean chatgptWorkEvent) throws Exception {
        return work(project, message, target, operation, chatgptWorkEvent, false, false);
    }

    public String work(String project, String message, String target,
                       String operation, boolean chatgptWorkEvent,
                       boolean allowGithubWrite, boolean allowPublicRepo) throws Exception {
        requireText(message);
        if (!("none".equals(target) || "android".equals(target) || "windows".equals(target)
                || "web".equals(target) || "github".equals(target))) {
            throw new IllegalArgumentException("محیط مقصد معتبر نیست");
        }
        if (!("answer".equals(operation) || "build".equals(operation)
                || "repair".equals(operation) || "analyze".equals(operation)
                || "release".equals(operation))) {
            throw new IllegalArgumentException("نوع عملیات معتبر نیست");
        }
        if (!ready) throw new IllegalStateException("کانال زنده هنوز آماده نیست");
        String ident = "a" + ids.incrementAndGet();
        JSONObject event = new JSONObject();
        event.put("type", "work");
        event.put("id", ident);
        event.put("project", LiveEndpointPolicy.project(project));
        event.put("message", message);
        event.put("consent", true);
        event.put("target_environment", target);
        event.put("requested_operation", operation);
        // Stable for this submission; a network retry can safely reuse it.
        // Android sends a unique 128-bit key, never an incremental socket id.
        event.put("request_key", java.util.UUID.randomUUID().toString().replace("-", ""));
        // Explicit opt-in: one request may create a private Issue and PR event.
        // The PR event does NOT prove ChatGPT Work has run.
        event.put("chatgpt_work_event", chatgptWorkEvent);
        event.put("authorize_github_write", allowGithubWrite);
        event.put("authorize_public_repo", allowPublicRepo);
        if (!socket.send(event.toString()))
            throw new IllegalStateException("ارسال درخواست در کانال زنده ناموفق بود");
        return ident;
    }

    public String resume(String project, String jobId) throws Exception {
        return send("resume", project, null, jobId);
    }

    private static void requireText(String text) {
        if (text == null || text.trim().isEmpty() || text.length() > 2500)
            throw new IllegalArgumentException("درخواست باید بین ۱ و ۲۵۰۰ نویسه باشد");
    }

    public void close() {
        ready = false;
        socket.close(1000, "user closed");
        transport.dispatcher().executorService().shutdown();
        transport.connectionPool().evictAll();
    }
}
