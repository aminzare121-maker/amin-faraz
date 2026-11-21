package com.amin.javab.screen

import android.app.Activity
import android.os.Build
import android.view.WindowManager

/**
 * Native Android screen adapter. A Javab activation command itself opts in
 * to foreground screen management. No second switch is necessary.
 *
 * This is NOT a background wake-up service, does not bypass the lock screen,
 * and does not grant an ordinary ChatGPT conversation access to the device.
 *
 * Compile/integration on an Android device: NOT YET VERIFIED.
 */
object ScreenAwakeSession {
    fun sync(activity: Activity, isJavabTaskActive: Boolean, isForeground: Boolean) {
        val keepAwake = isJavabTaskActive && isForeground
        if (keepAwake) {
            activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                // Only when Android permits this Activity to resume.
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

/**
 * Attach one instance to the Android Activity implementing the Javab UI.
 * Invoke onActivated only after a task was accepted, onStopped only after
 * the stop was confirmed, and onResume/onPause from Activity lifecycle.
 * The app must authenticate its task source; this class does NOT do that.
 */
class JavabScreenController(private val activity: Activity) {
    private val state = JavabActivationState()

    fun onActivated(taskId: String) {
        state.activate(taskId)
        refresh()
    }

    fun onStopped(taskId: String) {
        state.stop(taskId)
        refresh()
    }

    fun onAllStopped() {
        state.stopAll()
        refresh()
    }

    fun syncVerifiedActiveTasks(ids: Set<String>) {
        state.syncVerifiedTasks(ids)
        refresh()
    }

    fun onResume() {
        state.setForeground(true)
        refresh()
    }

    fun onPause() {
        state.setForeground(false)
        refresh()
    }

    private fun refresh() {
        // Calls must occur on the UI thread. Safe to post from a network callback.
        activity.runOnUiThread {
            ScreenAwakeSession.sync(
                activity = activity,
                isJavabTaskActive = state.activeTaskCount() > 0,
                isForeground = state.shouldKeepScreenAwake()
            )
        }
    }
}
