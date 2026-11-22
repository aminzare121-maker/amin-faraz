package com.amin.support.mobile;

/** Pure policy: choosing on-device audio NEVER silently switches to cloud. */
public final class VoiceModePolicy {
    private VoiceModePolicy() {}
    public static final int ONLINE = 0;
    public static final int DEVICE_OFFLINE = 1;
    public static final int AUTOMATIC = 2;
    public static final int UNAVAILABLE = -1;

    /**
     * Returns effective service mode, or UNAVAILABLE.
     * Offline mode only indicates local recognition. The ChatGPT answer still
     * needs a real online connection; no local language model is bundled.
     */
    public static int effectiveRecognition(
            int preference, boolean onlineAvailable, boolean offlineAvailable) {
        if (preference == DEVICE_OFFLINE) {
            return offlineAvailable ? DEVICE_OFFLINE : UNAVAILABLE;
        }
        if (preference == AUTOMATIC) {
            if (offlineAvailable) return DEVICE_OFFLINE;
            return onlineAvailable ? ONLINE : UNAVAILABLE;
        }
        if (preference == ONLINE) return onlineAvailable ? ONLINE : UNAVAILABLE;
        return UNAVAILABLE;
    }

    public static boolean requiresLocalVoice(int preference) {
        return preference == DEVICE_OFFLINE;
    }
}
