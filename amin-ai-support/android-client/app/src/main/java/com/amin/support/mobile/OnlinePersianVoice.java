package com.amin.support.mobile;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Build;
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
    private int preferredMode = VoiceModePolicy.ONLINE;
    private int activeMode = VoiceModePolicy.UNAVAILABLE;
    private boolean enabled = false;
    private boolean listening = false;
    private boolean awaitingReply = false;
    private boolean speaking = false;
    private boolean foreground = true;
    private int retries = 0;
    private int generation = 0;
    private final Runnable listenAgain = this::listen;
    private final Runnable responseTimeout = () -> {
        if (enabled && awaitingReply) {
            requestUnavailable("درخواست صوتی در مهلت مقرر پاسخ نگرفت؛ پاسخ ChatGPT تأیید نشده است.");
        }
    };

    public OnlinePersianVoice(Context context, Events events) {
        app = context.getApplicationContext();
        this.events = events;
    }

    public boolean isEnabled() { return enabled; }
    public boolean isUsingDeviceRecognition() {
        return enabled && activeMode == VoiceModePolicy.DEVICE_OFFLINE;
    }

    /** May only be set while idle; never infer offline support from UI labels. */
    public void setPreferredMode(int requested) {
        if (enabled) throw new IllegalStateException("Stop listening before changing voice mode");
        if (requested != VoiceModePolicy.ONLINE &&
                requested != VoiceModePolicy.DEVICE_OFFLINE &&
                requested != VoiceModePolicy.AUTOMATIC) {
            throw new IllegalArgumentException("Unrecognized voice mode");
        }
        preferredMode = requested;
    }

    public void start() {
        boolean remoteAvailable = SpeechRecognizer.isRecognitionAvailable(app);
        boolean localAvailable = Build.VERSION.SDK_INT >= 31
                && SpeechRecognizer.isOnDeviceRecognitionAvailable(app);
        activeMode = VoiceModePolicy.effectiveRecognition(
                preferredMode, remoteAvailable, localAvailable);
        if (activeMode == VoiceModePolicy.UNAVAILABLE) {
            events.onFailure(preferredMode == VoiceModePolicy.DEVICE_OFFLINE
                    ? "موتور تشخیص فارسی آفلاین در گوشی نصب نیست؛ هیچ دانلود خودکاری انجام نمی‌شود."
                    : "سرویس تشخیص گفتار روی این گوشی در دسترس نیست.");
            return;
        }
        enabled = true;
        foreground = true;
        awaitingReply = false;
        speaking = false;
        retries = 0;
        if (recognizer == null) {
            try {
                recognizer = activeMode == VoiceModePolicy.DEVICE_OFFLINE
                        ? SpeechRecognizer.createOnDeviceSpeechRecognizer(app)
                        : SpeechRecognizer.createSpeechRecognizer(app);
                recognizer.setRecognitionListener(this);
            } catch (RuntimeException problem) {
                enabled = false;
                activeMode = VoiceModePolicy.UNAVAILABLE;
                events.onFailure("راه‌اندازی موتور گفتار ممکن نشد: "
                        + problem.getClass().getSimpleName());
                return;
            }
        }
        events.onState(activeMode == VoiceModePolicy.DEVICE_OFFLINE
                ? "میکروفون با موتور تشخیص آفلاین اندروید فعال شد؛ پاسخ هوشمند همچنان آنلاین است."
                : "میکروفون فارسی با سرویس گفتار اندروید فعال شد.");
        listen();
    }

    public void stop() {
        generation++;
        enabled = false;
        listening = false;
        awaitingReply = false;
        speaking = false;
        activeMode = VoiceModePolicy.UNAVAILABLE;
        main.removeCallbacks(listenAgain);
        main.removeCallbacks(responseTimeout);
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
        main.removeCallbacks(responseTimeout);
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
        main.removeCallbacks(responseTimeout);
        if (recognizer != null) recognizer.cancel();
        events.onState("در حال پخش پاسخ فارسی");
    }

    /** TTS onDone or onError both release the next microphone turn. */
    public void replyFinished() {
        // A stale callback from an older TTS utterance must not cancel a newer
        // remote request or restart the microphone while waiting for that reply.
        if (!enabled || !speaking) return;
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
        main.removeCallbacks(responseTimeout);
        events.onFailure(why);
        schedule(1200);
    }

    private void schedule(long delay) {
        if (!enabled || !foreground || awaitingReply || speaking) return;
        main.removeCallbacks(listenAgain);
        main.postDelayed(listenAgain, delay);
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
        intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE,
                activeMode == VoiceModePolicy.DEVICE_OFFLINE);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        intent.putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 900L);
        try {
            listening = true;
            recognizer.startListening(intent);
            events.onState(activeMode == VoiceModePolicy.DEVICE_OFFLINE
                    ? "در حال شنیدن با سرویس آفلاین گوشی؛ پس از سکوت متن ارسال می‌شود"
                    : "در حال شنیدن فارسی؛ پس از سکوت درخواست آنلاین ارسال می‌شود");
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
        main.removeCallbacks(responseTimeout);
        main.postDelayed(responseTimeout, 90_000L);
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
        } else if (activeMode == VoiceModePolicy.DEVICE_OFFLINE) {
            events.onFailure("تشخیص فارسی آفلاین روی این گوشی برای این زبان کار نمی‌کند؛ "
                    + "برنامه به‌صورت پنهانی از اینترنت استفاده نکرد.");
        } else if (error == SpeechRecognizer.ERROR_NETWORK
                || error == SpeechRecognizer.ERROR_NETWORK_TIMEOUT) {
            events.onFailure("تشخیص گفتار آنلاین به اینترنت دسترسی ندارد");
        } else {
            events.onFailure("سرویس تشخیص فارسی خطا داد: " + error);
        }
        stop();
    }
}
