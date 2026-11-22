package com.amin.support.mobile;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;

import java.util.ArrayList;

/**
 * Lightweight hands-free Persian speech frontend, using an installed Android
 * speech service (usually network-dependent). No speech models in the APK.
 *
 * One listener instance runs only in the foreground; microphone access must
 * be granted separately. The voice turn is paused while awaiting a response
 * and while speaking to prevent feedback and duplicated remote requests.
 */
public final class OnlinePersianVoice implements RecognitionListener {
    public interface Events {
        void onTranscript(String words);
        void onState(String state);
        void onFailure(String reason);
    }

    private final Context app;
    private final Events events;
    private final Handler main = new Handler(Looper.getMainLooper());
    private SpeechRecognizer recognizer;
    private boolean enabled = false;
    private boolean listening = false;
    private boolean awaitingReply = false;
    private boolean speaking = false;
    private boolean foreground = true;
    private int retries = 0;
    private int generation = 0;
    private final Runnable listenAgain = this::listen;

    public OnlinePersianVoice(Context context, Events events) {
        app = context.getApplicationContext();
        this.events = events;
    }

    public boolean isEnabled() { return enabled; }

    public void start() {
        if (!SpeechRecognizer.isRecognitionAvailable(app)) {
            events.onFailure("سرویس تشخیص گفتار فارسی روی اندروید موجود نیست");
            return;
        }
        enabled = true;
        foreground = true;
        awaitingReply = false;
        speaking = false;
        retries = 0;
        if (recognizer == null) {
            recognizer = SpeechRecognizer.createSpeechRecognizer(app);
            recognizer.setRecognitionListener(this);
        }
        listen();
    }

    public void stop() {
        generation++;
        enabled = false;
        listening = false;
        awaitingReply = false;
        speaking = false;
        main.removeCallbacks(listenAgain);
        if (recognizer != null) {
            try { recognizer.cancel(); } catch (Exception ignored) {}
            recognizer.destroy();
            recognizer = null;
        }
        events.onState("گفت‌وگوی صوتی متوقف شد");
    }

    public void pauseForBackground() {
        foreground = false;
        generation++;
        main.removeCallbacks(listenAgain);
        listening = false;
        if (recognizer != null) recognizer.cancel();
        events.onState("میکروفون در پس‌زمینه متوقف شد");
    }

    public void resumeForeground() {
        foreground = true;
        if (enabled && !awaitingReply && !speaking) schedule(300);
    }

    /** Call once the AI response is ready and will be spoken by Android TTS. */
    public void replySpeaking() {
        if (!enabled) return;
        speaking = true;
        awaitingReply = false;
        generation++;
        listening = false;
        main.removeCallbacks(listenAgain);
        if (recognizer != null) recognizer.cancel();
        events.onState("در حال پخش پاسخ فارسی");
    }

    /** TTS onDone or onError both release the next microphone turn. */
    public void replyFinished() {
        if (!enabled) return;
        speaking = false;
        awaitingReply = false;
        retries = 0;
        schedule(250);
    }

    /** No online backend reached: do not claim an AI reply. */
    public void requestUnavailable(String why) {
        if (!enabled) return;
        awaitingReply = false;
        speaking = false;
        events.onFailure(why);
        schedule(1200);
    }

    private void schedule(long delay) {
        if (!enabled || !foreground || awaitingReply || speaking) return;
        final int round = generation;
        main.removeCallbacks(listenAgain);
        main.postDelayed(() -> {
            if (generation == round) listen();
        }, delay);
    }

    private void listen() {
        if (!enabled || !foreground || awaitingReply || speaking || listening
                || recognizer == null) return;
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "fa-IR");
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "fa-IR");
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, false);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        intent.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 900L);
        try {
            listening = true;
            recognizer.startListening(intent);
            events.onState("در حال شنیدن فارسی؛ پس از سکوت درخواست ارسال می‌شود");
        } catch (RuntimeException error) {
            listening = false;
            events.onFailure("تشخیص گفتار اندروید قابل اجرا نیست: "
                    + error.getClass().getSimpleName());
            schedule(1300);
        }
    }

    @Override public void onReadyForSpeech(Bundle params) {}
    @Override public void onBeginningOfSpeech() { retries = 0; }
    @Override public void onRmsChanged(float rmsdB) {}
    @Override public void onBufferReceived(byte[] buffer) {}
    @Override public void onEndOfSpeech() {}
    @Override public void onPartialResults(Bundle partialResults) {}
    @Override public void onEvent(int eventType, Bundle params) {}

    @Override public void onResults(Bundle results) {
        listening = false;
        if (!enabled || !foreground || awaitingReply || speaking) return;
        ArrayList<String> values = results.getStringArrayList(
                SpeechRecognizer.RESULTS_RECOGNITION);
        if (values == null || values.isEmpty() || values.get(0).trim().isEmpty()) {
            schedule(250);
            return;
        }
        String transcript = values.get(0).trim();
        if (transcript.length() > 2500) transcript = transcript.substring(0, 2500);
        awaitingReply = true;
        retries = 0;
        events.onTranscript(transcript);
    }

    @Override public void onError(int error) {
        listening = false;
        if (!enabled || !foreground || awaitingReply || speaking) return;
        if (error == SpeechRecognizer.ERROR_NO_MATCH
                || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT
                || error == SpeechRecognizer.ERROR_CLIENT) {
            if (++retries < 5) {
                schedule(400L * retries);
            } else {
                events.onFailure("سرویس گفتار بعد از چند بار تلاش پاسخ نداد");
                stop();
            }
            return;
        }
        if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
            events.onFailure("مجوز میکروفون داده نشده است");
        } else if (error == SpeechRecognizer.ERROR_NETWORK
                || error == SpeechRecognizer.ERROR_NETWORK_TIMEOUT) {
            events.onFailure("تشخیص گفتار آنلاین به اینترنت دسترسی ندارد");
        } else {
            events.onFailure("سرویس تشخیص فارسی خطا داد: " + error);
        }
        stop();
    }
}
