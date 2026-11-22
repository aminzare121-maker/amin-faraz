package com.amin.support.mobile;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/** Pure Java gate shared by the Android audio player and CI JVM tests. */
public final class NeuralAudioPolicy {
    public static final String VOICE_ID = "amin-persian-neural-v1";
    public static final int RATE = 22050;
    public static final int MAX_PARTS = 7;
    public static final int MAX_PCM = 650000;

    private NeuralAudioPolicy() {}

    public static boolean allowed(
            String expectedId, String receivedId, String voiceId,
            String encoding, int rate, int channels, int speaker,
            int index, int count, boolean isFinal) {
        return expectedId != null && !expectedId.isEmpty() &&
                expectedId.equals(receivedId) && VOICE_ID.equals(voiceId) &&
                "pcm_s16le_base64".equals(encoding) &&
                rate == RATE && channels == 1 &&
                speaker >= 0 && speaker < 7 &&
                count >= 1 && count <= MAX_PARTS &&
                index >= 0 && index < count &&
                isFinal == (index == count - 1);
    }

    public static boolean allowedPcm(byte[] raw) {
        return raw != null && raw.length >= 1024 &&
                raw.length <= MAX_PCM && raw.length % 2 == 0;
    }

    public static String sha256(byte[] raw) {
        if (raw == null) throw new IllegalArgumentException("Missing audio data");
        try {
            byte[] sha = MessageDigest.getInstance("SHA-256").digest(raw);
            char[] hex = new char[sha.length * 2];
            char[] alphabet = "0123456789abcdef".toCharArray();
            for (int i = 0; i < sha.length; i++) {
                hex[2 * i] = alphabet[(sha[i] >> 4) & 0xf];
                hex[2 * i + 1] = alphabet[sha[i] & 0xf];
            }
            return new String(hex);
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("Android SHA-256 unavailable", impossible);
        }
    }
}
