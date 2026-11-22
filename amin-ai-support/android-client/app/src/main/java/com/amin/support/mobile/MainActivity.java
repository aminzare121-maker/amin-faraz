package com.amin.support.mobile;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.net.UnknownHostException;
import java.util.ArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import javax.net.ssl.SSLException;

/**
 * A native mobile interface to the SAME multi-software support engine used on
 * Windows. Inference runs on the owner's configured backend, NOT on the phone.
 *
 * Only HTTPS, per-program scoped access, Keystore-protected bearer token.
 * No customer questions/transcripts are persisted on this device.
 * No paid external model, VPN, Google account, microphone, or GitHub token.
 */
public final class MainActivity extends Activity {
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService background = Executors.newSingleThreadExecutor();
    private final ArrayList<String> projectIds = new ArrayList<>();
    private final ArrayList<String> projectLabels = new ArrayList<>();
    private EditText server;
    private EditText token;
    private EditText question;
    private Spinner projects;
    private TextView status;
    private TextView answer;
    private Button connect;
    private Button send;
    private String latestAnswer = "";
    private ScrollView scroll;
    private boolean active = true;
    private int version = 0;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setTitle("هوش پشتیبان امین");
        setContentView(createContent());
        String existing = TokenVault.endpoint(this);
        if (!existing.isEmpty()) server.setText(existing);
        token.setHint(TokenVault.hasToken(this)
                ? "کلید دسترسی امن ذخیره شده است؛ برای تغییر، کلید تازه وارد کن"
                : "کلید دسترسی اختصاصی از مدیر نرم‌افزار");
        status.setText(TokenVault.hasToken(this)
                ? "کلید رمزگذاری‌شده موجود است. برای دریافت فهرست نرم‌افزارها اتصال را بزن."
                : "برای آغاز، نشانی HTTPS موتور و کلید دسترسی نرم‌افزار را ثبت کن.");
    }

    private View createContent() {
        scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        root.setPadding(dp(18), dp(20), dp(18), dp(36));
        scroll.addView(root);

        TextView head = text("هوش پشتیبان امین", 25, true);
        root.addView(head);
        root.addView(text("پشتیبانی نرم‌افزارهای مختلف با دانش مشترک بین ویندوز و گوشی",
                15, false));

        root.addView(section("اتصال به موتور هوش"));
        server = edit("https://your-support-server.example", false);
        server.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_VARIATION_URI);
        server.setSingleLine(true);
        root.addView(server);

        token = edit("کلید مخصوص این نرم‌افزار", false);
        token.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        token.setSingleLine(true);
        root.addView(token);

        connect = button("ذخیره و دریافت نرم‌افزارها");
        connect.setOnClickListener(v -> connect());
        root.addView(connect);

        Button clear = button("پاک‌کردن اتصال و کلید");
        clear.setOnClickListener(v -> clearConnection());
        root.addView(clear);

        status = text("", 14, false);
        status.setTextIsSelectable(true);
        root.addView(status);

        root.addView(section("گفت‌وگو با پشتیبان"));
        projects = new Spinner(this);
        projects.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        root.addView(projects);
        setProjects();

        question = edit("مشکل نرم‌افزاری را به فارسی بنویس ...", true);
        question.setMinLines(3);
        question.setMaxLines(5);
        root.addView(question);

        send = button("پرسش از هوش پشتیبان");
        send.setEnabled(false);
        send.setOnClickListener(v -> ask());
        root.addView(send);

        answer = text("پس از اتصال، پاسخ و منابع آن اینجا نمایش داده می‌شوند.",
                16, false);
        answer.setTextIsSelectable(true);
        root.addView(answer);

        Button copy = button("کپی پاسخ");
        copy.setOnClickListener(v -> {
            if (latestAnswer.isEmpty()) return;
            ClipboardManager clipboard =
                    (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            clipboard.setPrimaryClip(ClipData.newPlainText("Amin Support Answer", latestAnswer));
            setStatus("پاسخ در کلیپ‌بورد کپی شد؛ هنگام اشتراک‌گذاری مراقب اطلاعات خصوصی باش.");
        });
        root.addView(copy);

        root.addView(section("محدودیت نسخه آزمایشی"));
        root.addView(text(
                "این اپ خودش مدل زبانی دانلود یا اجرا نمی‌کند. پاسخ از همان موتور "
                + "پشتیبانی تنظیم‌شده روی رایانه یا سرور دریافت می‌شود. "
                + "بدون اتصال HTTPS معتبر و روشن‌بودن موتور، گفت‌وگوی هوشمند کار نمی‌کند.\n"
                + "هیچ سرویس هوش مصنوعی پولی از طرف این اپ فعال نمی‌شود. "
                + "پاسخ‌ها در حافظه دائمی گوشی ذخیره نمی‌شوند و کلید دسترسی با "
                + "Android Keystore رمزگذاری می‌شود.\n"
                + "دسترسی با اینترنت ملی، کیفیت مدل و سرعت پاسخ روی دستگاه واقعی "
                + "هنوز باید جداگانه آزموده شوند.", 14, false));

        return scroll;
    }

    private TextView section(String title) {
        TextView view = text("\n" + title, 18, true);
        view.setPadding(0, dp(8), 0, dp(4));
        return view;
    }

    private TextView text(String value, int sp, boolean strong) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setGravity(Gravity.RIGHT);
        view.setPadding(0, dp(6), 0, dp(8));
        if (strong) view.setTypeface(null, Typeface.BOLD);
        return view;
    }

    private EditText edit(String hint, boolean multiline) {
        EditText view = new EditText(this);
        view.setHint(hint);
        view.setTextSize(16);
        view.setGravity(Gravity.RIGHT);
        view.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        if (multiline) {
            view.setInputType(InputType.TYPE_CLASS_TEXT
                    | InputType.TYPE_TEXT_FLAG_MULTI_LINE
                    | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        }
        return view;
    }

    private Button button(String title) {
        Button b = new Button(this);
        b.setText(title);
        b.setAllCaps(false);
        return b;
    }

    private int dp(int x) {
        return Math.round(x * getResources().getDisplayMetrics().density);
    }

    private void setStatus(String message) {
        if (active) status.setText(message);
    }

    private void setProjects() {
        ArrayList<String> labels = new ArrayList<>();
        labels.add("ابتدا اتصال را برقرار کن");
        labels.addAll(projectLabels);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, labels);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        projects.setAdapter(adapter);
    }

    private void connect() {
        final String address;
        final String secret;
        try {
            address = SupportEndpoint.normalize(server.getText().toString());
            String entered = token.getText().toString().trim();
            String previous = TokenVault.endpoint(this);
            if (entered.isEmpty()) {
                // Critical: do not send a saved token to a NEW endpoint.
                if (!previous.equals(address)) {
                    throw new IllegalArgumentException(
                            "برای تغییر نشانی سرور، کلید مخصوص همان سرور را دوباره وارد کن.");
                }
                secret = SupportEndpoint.validateToken(TokenVault.token(this));
            } else {
                secret = SupportEndpoint.validateToken(entered);
            }
            TokenVault.save(this, address, secret);
            token.setText("");
            token.setHint("کلید امن ذخیره شد؛ نیازی به ورود دوباره نیست");
        } catch (Exception issue) {
            setStatus("تنظیمات اتصال نامعتبر: " + issue.getMessage());
            return;
        }

        connect.setEnabled(false);
        send.setEnabled(false);
        setStatus("در حال بررسی امن اتصال به موتور و دریافت فهرست نرم‌افزارها ...");
        int id = ++version;
        background.execute(() -> {
            try {
                SupportApi api = new SupportApi(address, secret);
                JSONObject response = api.projects();
                JSONArray entries = response.optJSONArray("projects");
                if (entries == null) throw new IllegalStateException("فهرست نرم‌افزارها دریافت نشد.");
                ArrayList<String> ids = new ArrayList<>();
                ArrayList<String> names = new ArrayList<>();
                for (int index = 0; index < entries.length(); index++) {
                    JSONObject project = entries.getJSONObject(index);
                    String ident = project.optString("id", "");
                    if (!ident.matches("[a-z][a-z0-9_-]{1,50}")) continue;
                    ids.add(ident);
                    names.add(project.optString("name", ident));
                }
                ui.post(() -> {
                    if (!active || id != version) return;
                    projectIds.clear();
                    projectIds.addAll(ids);
                    projectLabels.clear();
                    projectLabels.addAll(names);
                    setProjects();
                    connect.setEnabled(true);
                    send.setEnabled(!ids.isEmpty());
                    setStatus(ids.isEmpty()
                            ? "اتصال برقرار شد، اما این کلید به هیچ نرم‌افزاری دسترسی ندارد."
                            : "اتصال امن برقرار شد. تعداد نرم‌افزارهای مجاز: " + ids.size());
                });
            } catch (Exception error) {
                ui.post(() -> {
                    if (!active || id != version) return;
                    projectIds.clear();
                    projectLabels.clear();
                    setProjects();
                    connect.setEnabled(true);
                    send.setEnabled(false);
                    setStatus(explain(error));
                });
            }
        });
    }

    private void ask() {
        int selection = projects.getSelectedItemPosition() - 1;
        if (selection < 0 || selection >= projectIds.size()) {
            setStatus("ابتدا نرم‌افزار موردنظر را انتخاب کن.");
            return;
        }
        String message = question.getText().toString().trim();
        if (message.isEmpty() || message.length() > 2500) {
            setStatus("سؤال باید بین ۱ تا ۲۵۰۰ نویسه باشد.");
            return;
        }
        final String address = TokenVault.endpoint(this);
        final String secret;
        try {
            secret = TokenVault.token(this);
        } catch (Exception error) {
            setStatus("خواندن کلید رمزگذاری‌شده ناموفق است. کلید تازه وارد کن.");
            return;
        }
        String selectedProject = projectIds.get(selection);
        int id = ++version;
        send.setEnabled(false);
        answer.setText("در حال دریافت پاسخ از موتور پشتیبان ...");
        setStatus("در حال پردازش سؤال؛ اطلاعات فقط به سرور HTTPS تنظیم‌شده فرستاده می‌شود.");
        background.execute(() -> {
            try {
                JSONObject reply = new SupportApi(address, secret).ask(selectedProject, message);
                String response = reply.optString("answer", "");
                if (response.trim().isEmpty()) throw new IllegalStateException("پاسخ معتبر دریافت نشد.");
                boolean usedModel = reply.optBoolean("model_used", false);
                boolean human = reply.optBoolean("needs_human", false);
                StringBuilder text = new StringBuilder(response);
                text.append("\n\n");
                text.append(usedModel
                        ? "روش پاسخ: مدل هوش مصنوعی با منابع پروژه"
                        : "روش پاسخ: متن مستندات / راهنمای جایگزین؛ مدل استفاده نشده");
                if (human) text.append("\nاین سؤال به بررسی انسانی نیاز دارد.");
                JSONArray sources = reply.optJSONArray("sources");
                if (sources != null && sources.length() > 0) {
                    text.append("\n\nمنابع:");
                    for (int i = 0; i < Math.min(8, sources.length()); i++) {
                        JSONObject item = sources.optJSONObject(i);
                        if (item != null) {
                            text.append("\n[").append(i + 1).append("] ")
                                    .append(item.optString("path", ""))
                                    .append(" — بخش ").append(item.optInt("section", 0));
                        }
                    }
                }
                String formatted = text.toString();
                ui.post(() -> {
                    if (!active || id != version) return;
                    latestAnswer = formatted;
                    answer.setText(formatted);
                    send.setEnabled(true);
                    setStatus("پاسخ دریافت شد. بدون ذخیره دائمی مکالمه در این گوشی.");
                    scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
                });
            } catch (Exception failure) {
                ui.post(() -> {
                    if (!active || id != version) return;
                    latestAnswer = "";
                    answer.setText("هنوز پاسخی دریافت نشده است.");
                    send.setEnabled(true);
                    setStatus(explain(failure));
                });
            }
        });
    }

    private void clearConnection() {
        try {
            TokenVault.clear(this);
            ++version;
            server.setText("");
            token.setText("");
            projectIds.clear();
            projectLabels.clear();
            setProjects();
            send.setEnabled(false);
            answer.setText("");
            latestAnswer = "";
            setStatus("تنظیمات و کلید دسترسی این گوشی پاک شد.");
        } catch (Exception error) {
            setStatus("پاک‌کردن کلید با خطا روبه‌رو شد؛ دوباره تلاش کن.");
        }
    }

    private static String explain(Exception error) {
        if (error instanceof SSLException) {
            return "گواهی HTTPS سرور مورد اعتماد اندروید نیست؛ اتصال ناامن برقرار نشد.";
        }
        if (error instanceof UnknownHostException) {
            return "نام سرور پیدا نشد. اتصال اینترنت یا دسترسی به آدرس را بررسی کن.";
        }
        if (error instanceof java.net.SocketTimeoutException) {
            return "زمان پاسخ سرور تمام شد؛ ممکن است موتور خاموش یا مشغول باشد.";
        }
        if (error instanceof java.net.ConnectException) {
            return "موتور در آدرس تنظیم‌شده پاسخ نمی‌دهد.";
        }
        String reason = error.getMessage();
        if (reason != null && !reason.isEmpty()) {
            return "اتصال/پرسش ناموفق: " + reason;
        }
        return "در ارتباط با موتور پشتیبان خطایی رخ داد: "
                + error.getClass().getSimpleName();
    }

    @Override
    protected void onDestroy() {
        active = false;
        ++version;
        background.shutdownNow();
        super.onDestroy();
    }
}
