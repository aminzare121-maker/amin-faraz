package com.amin.support.mobile;

import android.app.Activity;
import android.app.AlertDialog;
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
import android.widget.CheckBox;
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
    private EditText ghRepo;
    private EditText ghToken;
    private EditText ghProject;
    private Button ghCheck;
    private int ghIssueNumber = 0;
    private String ghRequestId = "";
    private Spinner projects;
    private TextView status;
    private TextView answer;
    private Button connect;
    private Button send;
    private CheckBox autoHandoff;
    private Button checkHandoff;
    private String latestHandoffId = "";
    private String latestHandoffProject = "";
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
        latestHandoffId = getPreferences(MODE_PRIVATE).getString("handoff_id", "");
        latestHandoffProject = getPreferences(MODE_PRIVATE).getString("handoff_project", "");
        if (checkHandoff != null) checkHandoff.setEnabled(!latestHandoffId.isEmpty());
        ghRepo.setText(GitHubDirectVault.repo(this));
        ghProject.setText(getPreferences(MODE_PRIVATE).getString("direct_gh_project", "support"));
        ghIssueNumber = getPreferences(MODE_PRIVATE).getInt("direct_gh_issue", 0);
        ghRequestId = getPreferences(MODE_PRIVATE).getString("direct_gh_request_id", "");
        ghCheck.setEnabled(ghIssueNumber > 0 && ghRequestId.matches("[a-f0-9]{32}"));
        ghToken.setHint(GitHubDirectVault.available(this)
                ? "توکن قبلی رمزگذاری شده؛ در صورت عدم تغییر مخزن خالی بگذار"
                : "توکن محدود GitHub مخصوص مخزن خصوصی");

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

        root.addView(section("ارجاع به هوش مرکزی و پیگیری درخواست"));
        root.addView(text("اگر پاسخی قطعی یا ابزار لازم موجود نباشد، درخواست با رضایت تو "
                + "در موتور خصوصی ثبت می‌شود. GitHub عمومی فقط شناسه بی‌نام می‌بیند؛ "
                + "ارسال به ChatGPT فعلاً خودکار نیست و به عامل مجاز نیاز دارد.", 14, false));
        autoHandoff = new CheckBox(this);
        autoHandoff.setText("وقتی موتور شواهد کافی ندارد، با رضایت من خودکار به صف ارجاع بده"
                + " (ممکن است از سهمیه تیکت کم شود)");
        autoHandoff.setChecked(false);
        root.addView(autoHandoff);
        Button forward = button("ارجاع این درخواست با تأیید من");
        forward.setOnClickListener(v -> confirmHandoff());
        root.addView(forward);
        checkHandoff = button("بررسی نتیجه آخرین درخواست");
        checkHandoff.setEnabled(false);
        checkHandoff.setOnClickListener(v -> checkHandoff());
        root.addView(checkHandoff);

        root.addView(section("پل مستقیم GitHub خصوصی — بدون نیاز به روشن بودن لپ‌تاپ"));
        root.addView(text("برای هر کاربر یک مخزن خصوصی GitHub و کلید دسترسی محدود همان مخزن لازم است. "
                + "متن سؤال در Issue خصوصی ذخیره می‌شود و برای همکاران مجاز آن مخزن قابل مشاهده است. "
                + "اتصال خودکار به چت شخصی ChatGPT صرفاً با نصب این اپ انجام نمی‌شود.", 14, false));
        ghRepo = edit("owner/private-repository", false);
        ghRepo.setSingleLine(true);
        root.addView(ghRepo);
        ghToken = edit("توکن GitHub با مجوز Issues", false);
        ghToken.setSingleLine(true);
        ghToken.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        root.addView(ghToken);
        ghProject = edit("شناسه نرم‌افزار، مثلاً support", false);
        ghProject.setSingleLine(true);
        root.addView(ghProject);
        Button ghConnect = button("تأیید خصوصی بودن مخزن و اتصال");
        ghConnect.setOnClickListener(v -> connectDirectGitHub());
        root.addView(ghConnect);
        Button ghSend = button("ارسال سؤال به صف GitHub خصوصی");
        ghSend.setOnClickListener(v -> confirmDirectGitHub());
        root.addView(ghSend);
        ghCheck = button("دریافت پاسخ از GitHub خصوصی");
        ghCheck.setEnabled(false);
        ghCheck.setOnClickListener(v -> checkDirectGitHub());
        root.addView(ghCheck);
        Button ghClear = button("حذف کلید اتصال GitHub از گوشی");
        ghClear.setOnClickListener(v -> clearDirectGitHub());
        root.addView(ghClear);

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
                    if (human && autoHandoff.isChecked()) {
                        submitHandoff(selectedProject, message);
                    }
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

    private void confirmHandoff() {
        int selection = projects.getSelectedItemPosition() - 1;
        if (selection < 0 || selection >= projectIds.size()) {
            setStatus("ابتدا اتصال و نرم‌افزار را انتخاب کن.");
            return;
        }
        String message = question.getText().toString().trim();
        if (message.isEmpty() || message.length() > 2500) {
            setStatus("متن درخواست باید بین ۱ تا ۲۵۰۰ نویسه باشد.");
            return;
        }
        String project = projectIds.get(selection);
        new AlertDialog.Builder(this)
                .setTitle("اجازه ثبت و ارجاع درخواست")
                .setMessage("متن درخواست در حافظه خصوصی موتور ذخیره می‌شود. "
                        + "در مخزن عمومی GitHub فقط شناسه بی‌نام ثبت می‌شود. "
                        + "ارسال خودکار متن به ChatGPT فعال نیست. "
                        + "این درخواست ممکن است از سهمیه تیکت کم کند. تأیید می‌کنی؟")
                .setNegativeButton("انصراف", (d, w) -> {})
                .setPositiveButton("تأیید و ارسال", (d, w) -> submitHandoff(project, message))
                .show();
    }

    private void submitHandoff(String project, String message) {
        final String address = TokenVault.endpoint(this);
        final String secret;
        try {
            secret = TokenVault.token(this);
        } catch (Exception e) {
            setStatus("کلید اتصال در دسترس نیست.");
            return;
        }
        setStatus("در حال ثبت درخواست در صف خصوصی...");
        int id = ++version;
        background.execute(() -> {
            try {
                JSONObject reply = new SupportApi(address, secret).handoff(project, message);
                String requestId = reply.optString("id", "");
                if (!requestId.matches("[a-f0-9]{32}")) {
                    throw new IllegalStateException("شناسه معتبر ارجاع دریافت نشد.");
                }
                String githubState = reply.optString("github_state", "not_configured");
                ui.post(() -> {
                    if (!active || id != version) return;
                    latestHandoffId = requestId;
                    latestHandoffProject = project;
                    getPreferences(MODE_PRIVATE).edit()
                            .putString("handoff_id", requestId)
                            .putString("handoff_project", project).apply();
                    checkHandoff.setEnabled(true);
                    setStatus("درخواست ثبت شد: " + requestId.substring(0, 12)
                            + " | وضعیت GitHub: " + githubState
                            + ". پاسخ هنوز توسط هوش مرکزی بررسی نشده است.");
                });
            } catch (Exception error) {
                ui.post(() -> { if (active && id == version) setStatus(explain(error)); });
            }
        });
    }

    private void checkHandoff() {
        if (latestHandoffId.isEmpty() || latestHandoffProject.isEmpty()) {
            setStatus("درخواست ثبت‌شده‌ای برای پیگیری وجود ندارد.");
            return;
        }
        final String address = TokenVault.endpoint(this);
        final String secret;
        try {
            secret = TokenVault.token(this);
        } catch (Exception e) {
            setStatus("ابتدا اتصال امن را دوباره تنظیم کن.");
            return;
        }
        final String requestId = latestHandoffId;
        final String project = latestHandoffProject;
        setStatus("در حال بررسی وضعیت درخواست...");
        int id = ++version;
        background.execute(() -> {
            try {
                JSONObject result = new SupportApi(address, secret).handoffStatus(project, requestId);
                ui.post(() -> {
                    if (!active || id != version) return;
                    String state = result.optString("status", "pending");
                    if ("answered".equals(state)) {
                        String reviewedAnswer = result.optString("answer", "");
                        latestAnswer = reviewedAnswer;
                        answer.setText(reviewedAnswer);
                        setStatus("پاسخ بررسی‌شده برای درخواست " + requestId.substring(0, 12)
                                + " دریافت شد. افزودن به حافظه نیازمند تأیید جداگانه است.");
                    } else {
                        setStatus("درخواست " + requestId.substring(0, 12)
                                + " هنوز در صف بررسی است؛ این وضعیت به معنی اجرای ChatGPT نیست.");
                    }
                });
            } catch (Exception error) {
                ui.post(() -> { if (active && id == version) setStatus(explain(error)); });
            }
        });
    }

    private void connectDirectGitHub() {
        final String repository;
        final String credential;
        try {
            repository = GitHubBridgePolicy.repo(ghRepo.getText().toString());
            String entered = ghToken.getText().toString().trim();
            if (entered.isEmpty()) {
                if (!repository.equalsIgnoreCase(GitHubDirectVault.repo(this))) {
                    setStatus("برای تغییر مخزن باید توکن اختصاصی جدید وارد کنی.");
                    return;
                }
                credential = GitHubDirectVault.token(this);
            } else {
                credential = entered;
            }
            GitHubBridgePolicy.token(credential);
        } catch (Exception failure) {
            setStatus("تنظیمات GitHub معتبر نیست: " + failure.getMessage());
            return;
        }
        setStatus("در حال بررسی خصوصی بودن مخزن و دسترسی...");
        int requestVersion = ++version;
        background.execute(() -> {
            try {
                GitHubDirectBridge client = new GitHubDirectBridge(repository, credential);
                client.verifyPrivate();
                GitHubDirectVault.save(this, repository, credential);
                ui.post(() -> {
                    if (!active || requestVersion != version) return;
                    ghToken.setText("");
                    ghToken.setHint("کلید GitHub به صورت رمزگذاری‌شده ذخیره شد");
                    setStatus("اتصال به مخزن خصوصی تأیید شد؛ اتصال ChatGPT هنوز جداگانه لازم است.");
                });
            } catch (Exception failure) {
                ui.post(() -> { if (active && requestVersion == version) {
                    setStatus("اتصال GitHub تأیید نشد: " + failure.getMessage());
                } });
            }
        });
    }

    private void confirmDirectGitHub() {
        final String project;
        final String message = question.getText().toString().trim();
        try {
            project = GitHubBridgePolicy.project(ghProject.getText().toString().trim());
            if (message.isEmpty() || message.length() > 2500)
                throw new IllegalArgumentException("سؤال باید ۱ تا ۲۵۰۰ نویسه باشد");
            if (!GitHubDirectVault.available(this))
                throw new IllegalArgumentException("ابتدا اتصال مخزن خصوصی را تأیید کن");
            if (!GitHubDirectVault.repo(this).equalsIgnoreCase(ghRepo.getText().toString().trim()))
                throw new IllegalArgumentException("نشانی مخزن تغییر کرده؛ دوباره تأیید کن");
        } catch (Exception invalid) {
            setStatus(invalid.getMessage());
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("اجازه ارسال سؤال به GitHub خصوصی")
                .setMessage("متن سؤال در Issue مخزن خصوصی خودت ثبت می‌شود. "
                        + "تمام افراد دارای دسترسی به آن مخزن می‌توانند متن را ببینند. "
                        + "این کار چت شخصی ChatGPT را خودکار فعال نمی‌کند. ارسال انجام شود؟")
                .setNegativeButton("انصراف", (d, w) -> {})
                .setPositiveButton("ارسال خصوصی", (d, w) -> submitDirectGitHub(project, message))
                .show();
    }

    private void submitDirectGitHub(String project, String message) {
        final String repo = GitHubDirectVault.repo(this);
        final String credential;
        try { credential = GitHubDirectVault.token(this); }
        catch (Exception e) { setStatus("توکن GitHub قابل خواندن نیست"); return; }
        setStatus("در حال ارسال به مخزن خصوصی...");
        int requestVersion = ++version;
        background.execute(() -> {
            try {
                JSONObject response = new GitHubDirectBridge(repo, credential).submit(project, message);
                int issue = response.getInt("issue_number");
                String rid = response.getString("request_id");
                ui.post(() -> {
                    if (!active || requestVersion != version) return;
                    ghIssueNumber = issue;
                    ghRequestId = rid;
                    getPreferences(MODE_PRIVATE).edit()
                            .putInt("direct_gh_issue", issue)
                            .putString("direct_gh_request_id", rid)
                            .putString("direct_gh_project", project).apply();
                    ghCheck.setEnabled(true);
                    setStatus("درخواست در مخزن خصوصی ثبت شد؛ شماره Issue: " + issue
                            + ". اکنون منتظر پاسخ عامل متصل به ChatGPT است.");
                });
            } catch (Exception e) {
                ui.post(() -> { if (active && requestVersion == version)
                    setStatus("ثبت مستقیم ناموفق: " + e.getMessage()); });
            }
        });
    }

    private void checkDirectGitHub() {
        if (ghIssueNumber < 1 || !ghRequestId.matches("[a-f0-9]{32}")) {
            setStatus("ابتدا سؤال را در مخزن خصوصی ثبت کن");
            return;
        }
        final String repo = GitHubDirectVault.repo(this);
        final String credential;
        try { credential = GitHubDirectVault.token(this); }
        catch (Exception e) { setStatus("توکن اتصال GitHub در دسترس نیست"); return; }
        setStatus("در حال بررسی پاسخ در مخزن خصوصی...");
        int requestVersion = ++version;
        background.execute(() -> {
            try {
                JSONObject response = new GitHubDirectBridge(repo, credential).status(
                        ghIssueNumber, ghRequestId);
                ui.post(() -> {
                    if (!active || requestVersion != version) return;
                    if ("answered".equals(response.optString("status", ""))) {
                        latestAnswer = response.optString("answer", "");
                        answer.setText(latestAnswer);
                        setStatus("پاسخ از مخزن خصوصی دریافت شد. صحت اجرای عملیات باید جدا بررسی شود.");
                    } else {
                        setStatus("پاسخ هنوز در Issue خصوصی ثبت نشده است.");
                    }
                });
            } catch (Exception e) {
                ui.post(() -> { if (active && requestVersion == version)
                    setStatus("دریافت پاسخ ناموفق: " + e.getMessage()); });
            }
        });
    }

    private void clearDirectGitHub() {
        try {
            GitHubDirectVault.clear(this);
            getPreferences(MODE_PRIVATE).edit()
                    .remove("direct_gh_issue").remove("direct_gh_request_id")
                    .remove("direct_gh_project").apply();
            ghIssueNumber = 0;
            ghRequestId = "";
            ghRepo.setText("");
            ghToken.setText("");
            ghCheck.setEnabled(false);
            setStatus("توکن GitHub این گوشی پاک شد.");
        } catch (Exception error) {
            setStatus("پاک‌کردن اتصال GitHub ناموفق بود.");
        }
    }

    private void clearConnection() {
        try {
            TokenVault.clear(this);
            getPreferences(MODE_PRIVATE).edit().clear().apply();
            latestHandoffId = "";
            latestHandoffProject = "";
            if (checkHandoff != null) checkHandoff.setEnabled(false);
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
