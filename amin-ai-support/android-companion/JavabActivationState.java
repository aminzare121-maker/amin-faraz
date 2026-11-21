package com.amin.javab.screen;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * Pure-Java task state used by the Android bridge.
 *
 * Successful "برنامه جواب را فعال کن" for a real task invokes activate();
 * "برنامه جواب متوقف کن" invokes stop() (or stopAll() if requested).
 * No clock, periodic job, separate screen feature switch, background wake,
 * cross-task global cancellation, or device admin privileges.
 *
 * This class can be compiled and unit tested without Android dependencies.
 */
public final class JavabActivationState {
    private final Set<String> activeTaskIds = new HashSet<>();
    private boolean foreground = false;

    private static String checkedId(String taskId) {
        if (taskId == null || !taskId.matches("[A-Za-z0-9._-]{1,80}")) {
            throw new IllegalArgumentException("Invalid verified Javab task id");
        }
        return taskId;
    }

    /** Call only AFTER the trusted app confirms the Javab activation succeeded. */
    public synchronized void activate(String taskId) {
        activeTaskIds.add(checkedId(taskId));
    }

    /** Stop only the specified task, preserving other independent tasks. */
    public synchronized void stop(String taskId) {
        activeTaskIds.remove(checkedId(taskId));
    }

    /** A confirmed owner command to stop all Javab tasks. */
    public synchronized void stopAll() {
        activeTaskIds.clear();
    }

    public synchronized void setForeground(boolean isForeground) {
        foreground = isForeground;
    }

    /** Rehydrate only from previously verified task states, not untrusted text. */
    public synchronized void syncVerifiedTasks(Set<String> taskIds) {
        if (taskIds == null) throw new IllegalArgumentException("Task ids missing");
        Set<String> checked = new HashSet<>();
        for (String id : taskIds) checked.add(checkedId(id));
        activeTaskIds.clear();
        activeTaskIds.addAll(checked);
    }

    public synchronized boolean shouldKeepScreenAwake() {
        return foreground && !activeTaskIds.isEmpty();
    }

    public synchronized int activeTaskCount() {
        return activeTaskIds.size();
    }

    public synchronized Set<String> snapshot() {
        return Collections.unmodifiableSet(new HashSet<>(activeTaskIds));
    }
}
