package com.amin.support.mobile;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONObject;
import org.vosk.Model;
import org.vosk.Recognizer;
import org.vosk.android.RecognitionListener;
import org.vosk.android.SpeechService;
import org.vosk.android.StorageService;

/** Genuine on-device fa-IR speech recognition. No network or API key. */
public final class OfflinePersianRecognizer implements RecognitionListener {
    public interface Listener {
        void onReady();
        void onTranscript(String transcript);
        void onError(String reason);
    }

    private final Context app;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Listener listener;
    private Model model;
    private SpeechService service;
    private boolean preparing = false;
    private boolean running = false;
    private boolean stopped = false;
    private boolean destroyed = false;

    public OfflinePersianRecognizer(Context context, Listener listener) {
        this.app = context.getApplicationContext();
        this.listener = listener;
    }

    public void prepare() {
        if (destroyed || preparing || model != null) return;
        preparing = true;
        StorageService.unpack(app, "offline_voice/model-fa", "amin-vosk-fa-v1",
                ready -> {
                    if (destroyed) {
                        ready.close();
                        return;
                    }
                    model = ready;
                    preparing = false;
                    listener.onReady();
                },
                failure -> {
                    preparing = false;
                    listener.onError("مدل تشخیص فارسی داخل گوشی آماده نشد: "
                            + failure.getClass().getSimpleName());
                });
    }

    public boolean isReady() { return model != null; }
    public boolean isListening() { return running; }

    public void start() {
        if (destroyed || model == null) {
            listener.onError("تشخیص گفتار آفلاین هنوز آماده نیست");
            return;
        }
        if (running) return;
        try {
            stopped = false;
            Recognizer recognizer = new Recognizer(model, 16000.0f);
            service = new SpeechService(recognizer, 16000.0f);
            service.startListening(this);
            running = true;
        } catch (Exception error) {
            running = false;
            listener.onError("میکروفون آفلاین فعال نشد: " + error.getClass().getSimpleName());
        }
    }

    public void stop() {
        stopped = true;
        running = false;
        if (service != null) {
            service.stop();
            service.shutdown();
            service = null;
        }
    }

    @Override public void onResult(String hypothesis) {
        if (stopped || destroyed) return;
        try {
            String text = new JSONObject(hypothesis).optString("text", "").trim();
            if (!text.isEmpty()) {
                stop();
                main.post(() -> {
                    if (!destroyed) listener.onTranscript(text);
                });
            }
        } catch (Exception ignored) {}
    }

    @Override public void onFinalResult(String hypothesis) {
        // onResult handles a completed utterance before stopping the service.
        // Never deliver a second copy of the same utterance here.
    }
    @Override public void onPartialResult(String hypothesis) {}
    @Override public void onError(Exception error) {
        running = false;
        if (!stopped && !destroyed) {
            main.post(() -> listener.onError("خطای تشخیص آفلاین: "
                    + error.getClass().getSimpleName()));
        }
    }
    @Override public void onTimeout() {
        running = false;
    }

    public void release() {
        destroyed = true;
        stop();
        if (model != null) {
            model.close();
            model = null;
        }
    }
}
