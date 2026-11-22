package com.amin.support.mobile;

/** Host-JVM tests: no Android emulator and no network. */
public final class VoiceModePolicyTest {
    private static void eq(int expected, int actual) {
        if (expected != actual) throw new AssertionError("expected " + expected + " actual " + actual);
    }
    public static void main(String[] args) {
        eq(VoiceModePolicy.ONLINE,
                VoiceModePolicy.effectiveRecognition(VoiceModePolicy.ONLINE, true, true));
        eq(VoiceModePolicy.UNAVAILABLE,
                VoiceModePolicy.effectiveRecognition(VoiceModePolicy.ONLINE, false, true));
        eq(VoiceModePolicy.DEVICE_OFFLINE,
                VoiceModePolicy.effectiveRecognition(VoiceModePolicy.DEVICE_OFFLINE, true, true));
        eq(VoiceModePolicy.UNAVAILABLE,
                VoiceModePolicy.effectiveRecognition(VoiceModePolicy.DEVICE_OFFLINE, true, false));
        eq(VoiceModePolicy.DEVICE_OFFLINE,
                VoiceModePolicy.effectiveRecognition(VoiceModePolicy.AUTOMATIC, true, true));
        eq(VoiceModePolicy.ONLINE,
                VoiceModePolicy.effectiveRecognition(VoiceModePolicy.AUTOMATIC, true, false));
        eq(VoiceModePolicy.UNAVAILABLE,
                VoiceModePolicy.effectiveRecognition(VoiceModePolicy.AUTOMATIC, false, false));
        eq(VoiceModePolicy.UNAVAILABLE,
                VoiceModePolicy.effectiveRecognition(99, true, true));
        if (!VoiceModePolicy.requiresLocalVoice(VoiceModePolicy.DEVICE_OFFLINE)) {
            throw new AssertionError("Offline speech must not accept cloud TTS");
        }
        if (VoiceModePolicy.requiresLocalVoice(VoiceModePolicy.ONLINE)) {
            throw new AssertionError("Online mode should allow approved network voice");
        }
        if (!OfflineVoiceCommands.respond("راهنما", false).contains("فرمان‌های آفلاین")) {
            throw new AssertionError("Local Persian fixed help command missing");
        }
        if (!OfflineVoiceCommands.respond("پاسخ قبلی را بخوان", true)
                .equals("__READ_LAST_ANSWER__")) {
            throw new AssertionError("Read-previous-answer command not routed");
        }
        if (!OfflineVoiceCommands.respond("اخبار طلا امروز چیست؟", false).isEmpty()) {
            throw new AssertionError("Offline commands must not invent AI answers");
        }
        System.out.println("PASS: bounded voice mode routing and fixed Persian commands; no fake AI");
    }
}
