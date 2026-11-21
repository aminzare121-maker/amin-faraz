package com.amin.javab.screen

import android.app.Activity
import android.os.Build
import android.view.WindowManager

/**
 * Opt-in Android foreground screen management for a Javab-capable client.
 *
 * Host application must invoke sync() on the UI thread in onResume(), when
 * active task / opt-in state changes, and in onPause() with isForeground=false.
 * This does NOT wake a locked device from an arbitrary background event.
 * It does NOT bypass authentication, and it does not start a background agent.
 *
 * Tested on actual Samsung/Android hardware: NO.
 */
object ScreenAwakeSession {
    fun sync(
        activity: Activity,
        isJavabTaskActive: Boolean,
        ownerOptedIn: Boolean,
        isForeground: Boolean
    ) {
        val shouldKeepAwake = isJavabTaskActive && ownerOptedIn && isForeground
        if (shouldKeepAwake) {
            activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                // Effective only when Android permits this activity to resume
                // and become visible. Not an unrestricted background wake-up.
                activity.setTurnScreenOn(true)
            }
        } else {
            activity.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                activity.setTurnScreenOn(false)
            }
        }
    }
}
