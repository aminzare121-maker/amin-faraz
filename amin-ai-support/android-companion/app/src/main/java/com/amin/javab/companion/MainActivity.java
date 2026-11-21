package com.amin.javab.companion;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.amin.javab.screen.JavabActivationState;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * A native, installable and deliberately limited companion for "برنامه جواب".
 *
 * It checks OPEN JAVAB_TASK_V1 issues in the publicly visible owner's repo.
 * An open issue is a persisted active TASK, not proof of live computation.
 * Window flags apply only while THIS Activity is in the foreground.
 * It cannot affect the ChatGPT app window or revive a manually locked screen.
 *
 * No device-owner rights, accessibility permissions, overlay windows, rooted
 * commands, VPN or GitHub credentials. No secret is written to the device.
 */
public final class MainActivity extends Activity {
    private static final String API =
            "https://api.github.com/repos/aminzare121-maker/amin-faraz/issues"
            + "?state=open&per_page=100";
    private static final String REPO_LINK =
            "https://github.com/aminzare121-maker/amin-faraz/issues";
    // Public unauthenticated GitHub APIs have rate limits. About 30 reads/hour.
    private static final int POLL_SECONDS = 120;

    private final Handler ui = new Handler(Looper.getMainLooper());
    private final JavabActivationState tasks = new JavabActivationState();
    private ScheduledExecutorService worker;
    private TextView status;
    private TextView listing;
    private boolean resumed;
    private int generation;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setTitle("برنامه جواب امین");
        setContentView(makeView());
    }

    private View makeView() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(px(20), px(32), px(20), px(24));
        scroll.addView(content);

        TextView title = new TextView(this);
        title.setText("برنامه جواب امین");
        title.setTextSize(24);
        title.setGravity(Gravity.RIGHT);
        content.addView(title);

        status = new TextView(this);
        status.setText("هنوز وضعیت GitHub بررسی نشده است.");
        status.setTextSize(20);
        status.setGravity(Gravity.RIGHT);
        status.setPadding(0, px(18), 0, px(8));
        content.addView(status);

        listing = new TextView(this);
        listing.setText("فقط پرونده‌های باز و تأییدشده برنامه جواب بررسی می‌شوند.");
        listing.setTextSize(16);
        listing.setGravity(Gravity.RIGHT);
        listing.setTextIsSelectable(true);
        content.addView(listing);

        Button refresh = new Button(this);
        refresh.setText("بررسی مجدد پرونده‌ها");
        refresh.setOnClickListener(v -> requestRefresh());
        content.addView(refresh);

        Button github = new Button(this);
        github.setText("مشاهده پرونده‌ها در GitHub");
        github.setOnClickListener(v -> startActivity(
                new Intent(Intent.ACTION_VIEW, Uri.parse(REPO_LINK))));
        content.addView(github);

        TextView warning = new TextView(this);
        warning.setText(
                "\nمحدودیت مهم:\n"
                + "• تنها وقتی همین صفحه برنامه جلوی چشم است، در صورت وجود پرونده "
                + "فعال، از خاموشی خودکار نمایشگر جلوگیری می‌شود.\n"
                + "• این برنامه صفحه جداگانه ChatGPT را روشن نگه نمی‌دارد "
                + "و صفحه‌ای را که با دکمه پاور قفل شده باز نمی‌کند.\n"
                + "• پرونده باز، به معنی ادامه داشتن کار ثبت‌شده است؛ "
                + "نه اثبات اجرای زنده مدل هوش مصنوعی.\n"
                + "• هنگام توقف آخرین کار یا خروج از این صفحه، "
                + "حالت معمول نمایشگر بازمی‌گردد.\n"
                + "• قطع اینترنت یا فیلتر بودن GitHub باعث می‌شود "
                + "روشن‌ماندن صفحه فعال نشود.\n"
                + "• باز بودن طولانی نمایشگر مصرف باتری را افزایش می‌دهد.\n"
                + "• این نسخه آزمایشی است؛ هیچ کلید GitHub یا اطلاعات شخصی نمی‌گیرد."
        );
        warning.setGravity(Gravity.RIGHT);
        warning.setTextSize(15);
        content.addView(warning);

        return scroll;
    }

    private int px(int dp) {
        return Math.round(dp * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onResume() {
        super.onResume();
        resumed = true;
        ++generation;
        tasks.setForeground(true);
        syncScreen();
        startPolling();
    }

    @Override
    protected void onPause() {
        ++generation; // Ignore responses arriving after the Activity is hidden.
        resumed = false;
        stopPolling();
        tasks.setForeground(false);
        syncScreen(); // Explicitly release Android window flags on background.
        super.onPause();
    }

    private void startPolling() {
        stopPolling();
        worker = Executors.newSingleThreadScheduledExecutor();
        final int expectedGeneration = generation;
        worker.scheduleWithFixedDelay(
                () -> fetchAndDisplay(expectedGeneration),
                0, POLL_SECONDS, TimeUnit.SECONDS);
    }

    private void stopPolling() {
        if (worker != null) {
            worker.shutdownNow();
            worker = null;
        }
    }

    private void requestRefresh() {
        if (worker == null) return;
        final int expectedGeneration = generation;
        worker.execute(() -> fetchAndDisplay(expectedGeneration));
    }

    private void fetchAndDisplay(int expectedGeneration) {
        try {
            Snapshot snap = fetchOpenTasks();
            ui.post(() -> {
                if (!resumed || generation != expectedGeneration) return;
                // Each refresh is an authoritative snapshot. A single stopped
                // task does not cancel other active task IDs.
                tasks.syncVerifiedTasks(snap.ids);
                syncScreen();
                status.setText(snap.ids.isEmpty()
                        ? "برنامه جواب: هیچ کار بازی ثبت نشده است"
                        : "برنامه جواب: " + snap.ids.size() + " کار باز");
                listing.setText(snap.labels.isEmpty()
                        ? "پس از فرمان «برنامه جواب فعال کن» و ثبت موفق در GitHub، "
                          + "کار اینجا نمایش داده می‌شود."
                        : String.join("\n", snap.labels));
            });
        } catch (Exception failure) {
            ui.post(() -> {
                if (!resumed || generation != expectedGeneration) return;
                // Fail closed: an unverified or stale task cannot force screen on.
                tasks.syncVerifiedTasks(new HashSet<>());
                syncScreen();
                status.setText("اتصال یا بررسی GitHub ناموفق بود");
                listing.setText("نوع خطا: " + failure.getClass().getSimpleName()
                        + "\nبدون دریافت وضعیت معتبر، نمایشگر در حالت معمول می‌ماند."
                        + "\nبرای ادامه، اتصال اینترنت و GitHub را بررسی کنید.");
            });
        }
    }

    private Snapshot fetchOpenTasks() throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(API).openConnection();
        conn.setConnectTimeout(8000);
        conn.setReadTimeout(8000);
        conn.setRequestMethod("GET");
        conn.setRequestProperty("Accept", "application/vnd.github+json");
        conn.setRequestProperty("User-Agent", "AminJavabAndroidCompanion/0.1");
        conn.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
        try {
            int code = conn.getResponseCode();
            if (code != 200) throw new IllegalStateException("GitHub API status " + code);
            StringBuilder data = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    data.append(line);
                    if (data.length() > 1000000) {
                        throw new IllegalStateException("GitHub response exceeds size limit");
                    }
                }
            }
            JSONArray issues = new JSONArray(data.toString());
            // Never silently ignore active tasks beyond the first API page.
            if (issues.length() == 100) {
                throw new IllegalStateException("Too many open issues to verify");
            }
            Snapshot snap = new Snapshot();
            for (int i = 0; i < issues.length(); i++) {
                JSONObject issue = issues.getJSONObject(i);
                if (issue.has("pull_request")) continue;
                if (!"open".equals(issue.optString("state"))) continue;
                if (!issue.optString("title").startsWith("برنامه جواب | ")) continue;
                JSONObject author = issue.optJSONObject("user");
                if (author == null ||
                    !"aminzare121-maker".equals(author.optString("login"))) continue;
                String body = issue.optString("body", "");
                if (!body.startsWith("JAVAB_TASK_V1\n")) continue;
                JSONObject task;
                try {
                    task = new JSONObject(body.substring("JAVAB_TASK_V1\n".length()));
                } catch (JSONException ignored) {
                    continue;
                }
                int number = issue.optInt("number", -1);
                if (number < 1 || task.optInt("task_id", -2) != number) continue;
                String goal = task.optString("goal", "");
                if (goal.isEmpty() || task.optString("success_criteria").isEmpty()) continue;
                snap.ids.add(Integer.toString(number));
                snap.labels.add("• #" + number + " — "
                    + issue.optString("title").replace("برنامه جواب | ", ""));
            }
            return snap;
        } finally {
            conn.disconnect();
        }
    }

    private void syncScreen() {
        final boolean activeAndVisible = resumed && tasks.shouldKeepScreenAwake();
        if (activeAndVisible) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                setTurnScreenOn(true);
            }
        } else {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                setTurnScreenOn(false);
            }
        }
    }

    private static final class Snapshot {
        final Set<String> ids = new HashSet<>();
        final java.util.List<String> labels = new java.util.ArrayList<>();
    }
}
