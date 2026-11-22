package com.amin.support.mobile;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;

import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * PCM speech over the EXISTING authenticated TLS/WSS connection.
 *
 * No ONNX weights, neural model, provider token or paid API in the APK.
 * Enforces stream ID, speaker, exact audio digest, sample rate, packet count,
 * in-order chunks, bounded memory and cancellation-before-playback.
 */
public final class NeuralVoicePlayer {
    public interface Callbacks {
        void onFirstAudio();
        void onFinished();
        void onFailure(String reason, boolean playedSomeAudio);
    }

    private static final int RATE = 22050;
    private static final int MAX_PACKET_BYTES = 650_000;
    private static final int MAX_PARTS = 7;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final AtomicInteger generation = new AtomicInteger();

    private volatile AudioTrack currentTrack;
    private volatile boolean closed = false;
    private String requestId = "";
    private int nextPart = 0;
    private int expectedParts = 0;
    private long expectedFrames = 0;
    private boolean heardFirst = false;
    private Callbacks callbacks;

    public NeuralVoicePlayer(Context context) {
        // Never retain Activity, authorization tokens or transcript.
    }

    /** Called only on Activity's main thread before submitting a spoken ask. */
    public void begin(String id, Callbacks cb) {
        stop();
        if (id == null || !id.matches("[A-Za-z0-9_-]{1,64}") || cb == null)
            throw new IllegalArgumentException("Invalid voice stream identity");
        if (closed) throw new IllegalStateException("Voice playback closed");
        requestId = id;
        callbacks = cb;
    }

    /** Non-blocking delivery from Activity main thread; actual PCM is played off-main. */
    public void accept(JSONObject event) {
        if (closed || event == null) return;
        String id = event.optString("id", "");
        if (!id.equals(requestId) || id.isEmpty()) return; // never mix requests
        final int sequence = generation.get();
        final Callbacks callback = callbacks;
        if (callback == null) return;

        // Validate signed/hashed framing BEFORE sound can reach the speaker.
        final byte[] pcm;
        final int index, total;
        try {
            index = event.getInt("part_index");
            total = event.getInt("part_count");
            if (!NeuralAudioPolicy.allowed(requestId, id,
                    event.optString("voice_id", ""), event.optString("encoding", ""),
                    event.optInt("sample_rate", -1), event.optInt("channels", -1),
                    event.optInt("speaker", -1), index, total, event.optBoolean("final"))) {
                throw new IllegalArgumentException("Invalid neural voice identity or sequence");
            }
            String b64 = event.getString("data");
            String checksum = event.getString("sha256");
            if (b64.length() > 900_000 || !checksum.matches("[a-f0-9]{64}"))
                throw new IllegalArgumentException("Oversized/invalid neural audio packet");
            pcm = Base64.decode(b64, Base64.NO_WRAP);
            if (!NeuralAudioPolicy.allowedPcm(pcm))
                throw new IllegalArgumentException("Invalid PCM length");
            if (!checksum.equals(NeuralAudioPolicy.sha256(pcm)))
                throw new IllegalArgumentException("Neural audio digest mismatch");
        } catch (Exception error) {
            failIfCurrent(sequence, "بستهٔ صوت عصبی معتبر نیست.", callback);
            return;
        }

        worker.execute(() -> {
            if (closed || generation.get() != sequence) return;
            try {
                if (index != nextPart || (nextPart != 0 && total != expectedParts))
                    throw new IllegalStateException("Out of order neural audio");
                if (nextPart == 0) {
                    expectedParts = total;
                    expectedFrames = 0;
                    heardFirst = true;
                    AudioTrack track = makeTrack();
                    currentTrack = track;
                    track.play();
                    main.post(() -> {
                        if (generation.get() == sequence && !closed)
                            callback.onFirstAudio();
                    });
                }
                AudioTrack playing = currentTrack;
                if (playing == null) throw new IllegalStateException("No playback output");
                nextPart++;
                int offset = 0;
                while (offset < pcm.length && !closed && generation.get() == sequence) {
                    int wrote = playing.write(pcm, offset, pcm.length - offset,
                                              AudioTrack.WRITE_BLOCKING);
                    if (wrote <= 0) throw new IllegalStateException("Audio playback write failed");
                    offset += wrote;
                }
                if (closed || generation.get() != sequence) return;
                expectedFrames += pcm.length / 2L;
                if (index == total - 1) {
                    // WRITE_BLOCKING enqueues audio, but doesn't mean the user
                    // heard the tail. Wait for the hardware playback head.
                    long deadline = System.currentTimeMillis() +
                            Math.min(40_000L, 2000 + (expectedFrames * 1000 / RATE));
                    while (generation.get() == sequence && !closed &&
                           System.currentTimeMillis() < deadline) {
                        long played = playing.getPlaybackHeadPosition() & 0xffffffffL;
                        if (played >= expectedFrames) break;
                        Thread.sleep(50);
                    }
                    if (generation.get() == sequence && !closed) {
                        releaseTrack();
                        requestId = "";
                        callbacks = null;
                        main.post(() -> {
                            if (generation.get() == sequence && !closed)
                                callback.onFinished();
                        });
                    }
                }
            } catch (Exception error) {
                failIfCurrent(sequence, "پخش صدای عصبی فارسی ممکن نشد.", callback);
            }
        });
    }

    public void remoteFailure(String id, String reason) {
        if (id == null || !id.equals(requestId) || callbacks == null) return;
        failIfCurrent(generation.get(), reason, callbacks);
    }

    private void failIfCurrent(int sequence, String reason, Callbacks callback) {
        if (closed || generation.get() != sequence) return;
        boolean partial = heardFirst;
        stop();
        main.post(() -> {
            if (!closed) callback.onFailure(reason, partial);
        });
    }

    private AudioTrack makeTrack() {
        int min = AudioTrack.getMinBufferSize(
                RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT);
        if (min < 0) throw new IllegalStateException("Audio device not available");
        AudioTrack track = new AudioTrack.Builder()
                .setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                .setAudioFormat(new AudioFormat.Builder()
                        .setSampleRate(RATE)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                .setTransferMode(AudioTrack.MODE_STREAM)
                .setBufferSizeInBytes(Math.max(min * 3, 16384)).build();
        if (track.getState() != AudioTrack.STATE_INITIALIZED) {
            track.release();
            throw new IllegalStateException("Neural audio output is unavailable");
        }
        return track;
    }

    private void releaseTrack() {
        AudioTrack track = currentTrack;
        currentTrack = null;
        if (track == null) return;
        try { track.pause(); track.flush(); } catch (Exception ignored) {}
        try { track.release(); } catch (Exception ignored) {}
    }

    public void stop() {
        generation.incrementAndGet();
        requestId = "";
        callbacks = null;
        nextPart = 0;
        expectedParts = 0;
        expectedFrames = 0;
        heardFirst = false;
        AudioTrack track = currentTrack;
        if (track != null) {
            try { track.pause(); track.flush(); } catch (Exception ignored) {}
        }
        // Serializes release with the worker's playback loop.
        if (!closed) worker.execute(this::releaseTrack);
    }

    public void close() {
        stop();
        closed = true;
        worker.shutdown();
    }
}
