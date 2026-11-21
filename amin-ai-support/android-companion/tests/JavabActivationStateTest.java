package com.amin.javab.screen;

import java.util.Set;

/** Real JVM executable tests, no Android emulator and no extra dependencies. */
public final class JavabActivationStateTest {
    private static int tests = 0;

    private static void check(boolean condition, String explanation) {
        tests++;
        if (!condition) throw new AssertionError(explanation);
    }

    private static void rejectsBadId(JavabActivationState state, String bad) {
        boolean refused = false;
        try {
            state.activate(bad);
        } catch (IllegalArgumentException expected) {
            refused = true;
        }
        check(refused, "unsafe task ID must be rejected: " + bad);
    }

    public static void main(String[] args) {
        JavabActivationState state = new JavabActivationState();
        check(!state.shouldKeepScreenAwake(), "no task means screen flags must be off");

        state.setForeground(true);
        check(!state.shouldKeepScreenAwake(), "foreground alone cannot wake screen");

        // "برنامه جواب فعال کن": activation itself enables display management.
        state.activate("73");
        check(state.shouldKeepScreenAwake(), "activation enables screen policy automatically");
        check(state.activeTaskCount() == 1, "first task tracked");

        // Idempotent repeated command does not introduce duplicate tasks.
        state.activate("73");
        check(state.activeTaskCount() == 1, "repeated activation idempotent");

        // "برنامه جواب" supports multiple independent tasks.
        state.activate("80");
        check(state.activeTaskCount() == 2, "separate active tasks tracked");
        state.stop("73");
        check(state.shouldKeepScreenAwake(), "stopping one task cannot stop another");
        check(state.activeTaskCount() == 1, "only named task stopped");

        state.stop("80");
        check(!state.shouldKeepScreenAwake(), "last stop turns policy off immediately");

        state.activate("81");
        state.setForeground(false);
        check(!state.shouldKeepScreenAwake(), "background cannot hold screen on");
        state.setForeground(true);
        check(state.shouldKeepScreenAwake(), "foreground resumes only with verified active task");

        state.syncVerifiedTasks(Set.of("200", "201"));
        check(state.activeTaskCount() == 2, "refresh uses only verified active tasks");
        state.stop("200");
        check(state.shouldKeepScreenAwake(), "other verified task persists");
        state.stopAll();
        check(!state.shouldKeepScreenAwake(), "explicit stop all releases screen");
        check(state.snapshot().isEmpty(), "no stale active tasks remain");

        // A failed or invalid command must not affect any valid task.
        rejectsBadId(state, "../bad");
        rejectsBadId(state, "");
        rejectsBadId(state, " ");
        rejectsBadId(state, "bad/name");
        rejectsBadId(state, null);

        state.activate("203");
        try {
            state.syncVerifiedTasks(Set.of("202", "bad/name"));
            throw new AssertionError("invalid restored task not rejected");
        } catch (IllegalArgumentException expected) {
            check(state.activeTaskCount() == 1, "invalid restore must not corrupt state");
        }
        state.stop("203");
        check(!state.shouldKeepScreenAwake(), "restore error did not prevent normal stop");

        System.out.println("JavabActivationState JVM checks passed: " + tests);
    }
}
