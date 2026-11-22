package com.amin.support.mobile;

/** No Android device/emulator is simulated: validates only pure packet rules. */
public final class NeuralAudioPolicyTest {
    private static void ok(boolean condition, String error) {
        if (!condition) throw new AssertionError(error);
    }

    private static boolean allow(String expected, String given, int idx, int count,
                                 boolean last, int speaker, int rate) {
        return NeuralAudioPolicy.allowed(expected, given,
                "amin-persian-neural-v1", "pcm_s16le_base64", rate, 1,
                speaker, idx, count, last);
    }

    public static void main(String[] args) {
        ok(allow("a1", "a1", 0, 2, false, 2, 22050), "valid part 0");
        ok(allow("a1", "a1", 1, 2, true, 2, 22050), "valid final part");
        ok(!allow("a1", "a2", 0, 1, true, 2, 22050), "other user reply blocked");
        ok(!allow("a1", "a1", 1, 2, false, 2, 22050), "missing final flag blocked");
        ok(!allow("a1", "a1", -1, 1, true, 2, 22050), "negative index blocked");
        ok(!allow("a1", "a1", 0, 8, false, 2, 22050), "oversized stream blocked");
        ok(!allow("a1", "a1", 0, 1, true, 8, 22050), "unlicensed speaker blocked");
        ok(!allow("a1", "a1", 0, 1, true, 2, 16000), "sample rate mismatch blocked");
        ok(!NeuralAudioPolicy.allowed("a1","a1","fake","pcm_s16le_base64",
                22050,1,2,0,1,true), "wrong speaker/model identity blocked");
        ok(!NeuralAudioPolicy.allowed("a1","a1","amin-persian-neural-v1",
                "mp3",22050,1,2,0,1,true), "unsupported codec blocked");
        byte[] pcm = new byte[44100];
        pcm[0] = 21;
        ok(NeuralAudioPolicy.allowedPcm(pcm), "valid PCM");
        ok(!NeuralAudioPolicy.allowedPcm(new byte[20]), "too short");
        ok(!NeuralAudioPolicy.allowedPcm(new byte[650002]), "too large");
        ok(!NeuralAudioPolicy.allowedPcm(new byte[44101]), "unaligned");
        ok(NeuralAudioPolicy.sha256(pcm).matches("[a-f0-9]{64}"), "digest format");
        ok(!NeuralAudioPolicy.sha256(pcm).equals(
                NeuralAudioPolicy.sha256(new byte[44100])), "detect corruption");
        System.out.println("PASS: neural PCM bounds, digest, owner request ID and sequenced voice frames");
    }
}
