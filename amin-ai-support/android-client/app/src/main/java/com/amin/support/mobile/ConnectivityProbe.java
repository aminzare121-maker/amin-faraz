package com.amin.support.mobile;

import org.json.JSONObject;

import java.net.InetAddress;
import java.net.URL;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

/**
 * On-device network diagnostics WITHOUT ANY bearer token, question, repository
 * name or unique device identifier. Run only after the user presses Diagnose.
 */
public final class ConnectivityProbe {
    private static final int TIMEOUT_MS = 6500;

    private ConnectivityProbe() {}

    public static JSONObject github() {
        JSONObject result = new JSONObject();
        try {
            HttpsURLConnection conn = (HttpsURLConnection)
                    new URL("https://api.github.com/").openConnection();
            conn.setConnectTimeout(TIMEOUT_MS);
            conn.setReadTimeout(TIMEOUT_MS);
            conn.setInstanceFollowRedirects(false);
            conn.setRequestProperty("Accept", "application/vnd.github+json");
            conn.setRequestProperty("User-Agent", "AminLiveConnectivityCheck/0.1");
            try {
                int code = conn.getResponseCode();
                result.put("reachable", code > 0);
                result.put("http_status", code);
                result.put("tls_verified", true);
            } finally {
                conn.disconnect();
            }
        } catch (Exception failure) {
            try {
                result.put("reachable", false);
                result.put("tls_verified", false);
                result.put("error_type", failure.getClass().getSimpleName());
            } catch (Exception ignored) { /* JSONObject in-memory; no external call */ }
        }
        return result;
    }

    public static JSONObject liveTls(String rawEndpoint) {
        JSONObject result = new JSONObject();
        try {
            String endpoint = LiveEndpointPolicy.requireWss(rawEndpoint);
            java.net.URI uri = java.net.URI.create(endpoint);
            String host = uri.getHost();
            int port = uri.getPort() == -1 ? 443 : uri.getPort();
            // Require platform TLS validation AND hostname verification.
            SSLSocketFactory factory = (SSLSocketFactory) SSLSocketFactory.getDefault();
            try (SSLSocket socket = (SSLSocket) factory.createSocket()) {
                socket.connect(new java.net.InetSocketAddress(host, port), TIMEOUT_MS);
                socket.setSoTimeout(TIMEOUT_MS);
                SSLParameters params = socket.getSSLParameters();
                params.setEndpointIdentificationAlgorithm("HTTPS");
                socket.setSSLParameters(params);
                socket.startHandshake();
                result.put("reachable", true);
                result.put("tls_verified", true);
                result.put("tls_protocol", socket.getSession().getProtocol());
            }
        } catch (Exception failure) {
            try {
                result.put("reachable", false);
                result.put("tls_verified", false);
                result.put("error_type", failure.getClass().getSimpleName());
            } catch (Exception ignored) { /* JSONObject in-memory */ }
        }
        return result;
    }

    public static String explain(String source, JSONObject result) {
        if (result.optBoolean("reachable")) {
            String status = result.has("http_status")
                    ? "، پاسخ HTTP " + result.optInt("http_status") : "";
            return source + ": اتصال و TLS موفق" + status;
        }
        String reason = result.optString("error_type", "UnknownError");
        return source + ": ناموفق (" + reason + ")";
    }
}
