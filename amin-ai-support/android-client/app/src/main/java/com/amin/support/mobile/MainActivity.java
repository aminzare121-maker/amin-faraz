package com.amin.support.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
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
import java.io.File;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import javax.net.ssl.SSLException;

/**
 * A native mobile interface to the SAME multi-software support engine used on
 * Windows. Inference runs on the owner's configured backend, NOT on the phone.
 *
 * Only HTTPS, per-program scoped access, Keystore-protected bearer token.
 * No customer questions/transcripts are persisted on this device.
 * No paid external model or VPN is required. The OPTIONAL direct-private mode
 * stores the user's repo-scoped GitHub credential in a separate Android Keystore.
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
    private EditText liveWss;
    private EditText liveToken;
    private EditText liveProject;
    private EditText liveJob;
    private Spinner liveTarget;
    private Spinner liveOperation;
    private CheckBox liveWorkChatGPT;
    private TextView liveStatus;
    private Button verifiedApkInstall;
    private String availableApkUrl = "";
    private String availableApkSha = "";
    private LiveSocketClient liveClient;
    private int liveGeneration = 0;
    private static final int VOICE_REQUEST = 2401;
    private TextToSpeech speech;
    private boolean speechReady = false;
    private CheckBox voiceReplies;
    private CheckBox voiceAutoSend;
    private Button ghCheck;
    private int ghIssueNumber = 0;
    private String ghRequestId = "";
    private String ghNotifiedRequestId = "";
    private boolean resumed = false;
    private boolean directPollBusy = false;
    private final Runnable githubDirectPoll = new Runnable() {
        @Override public void run() {
            if (!active || !resumed) return;
            if (ghIssueNumber > 0 && GitHubDirectVault.available(MainActivity.this) && !directPollBusy) {
                pollDirectQuietly();
            }
            ui.postDelayed(this, 10_000L);
        }
    };
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
    private int diagnosticVersion = 0;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setTitle("هوش پشتیبان امین");
        setContentView(createContent());
        speech = new TextToSpeech(this, code -> {
            ui.post(() -> {
                if (!active || speech == null) return;
                if (code != TextToSpeech.SUCCESS) {
                    speechReady = false;
                    setStatus("صدای فارسی روی دستگاه آماده نیست.");
                    return;
                }
                int support = speech.setLanguage(new Locale("fa", "IR"));
                speechReady = support != TextToSpeech.LANG_MISSING_DATA
                        && support != TextToSpeech.LANG_NOT_SUPPORTED;
            });
        });
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
        liveWss.setText(getPreferences(MODE_PRIVATE).getString("live_wss", ""));
        liveProject.setText(getPreferences(MODE_PRIVATE).getString("live_project", "support"));
        liveJob.setText(getPreferences(MODE_PRIVATE).getString("live_job", ""));


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

        root.addView(section("مکالمه صوتی و نوشتاری"));
        root.addView(text("با لمس میکروفون، تشخیص گفتار دستگاه فعال می‌شود و متن برای "
                + "بازبینی نمایش داده می‌شود. بسته به موتور گفتار گوشی، صدای شما "
                + "ممکن است به ارائه‌دهنده آن سرویس منتقل شود؛ حالت صوتی اختیاری است.", 14, false));
        Button mic = button("میکروفون: گفتار فارسی به متن");
        mic.setOnClickListener(v -> startVoiceInput());
        root.addView(mic);
        voiceAutoSend = new CheckBox(this);
        voiceAutoSend.setText("پس از تشخیص گفتار، سؤال را خودکار در کانال زنده بفرست (اگر متصل است)");
        voiceAutoSend.setChecked(false);
        root.addView(voiceAutoSend);
        voiceReplies = new CheckBox(this);
        voiceReplies.setText("پاسخ‌ها با صدای فارسی خوانده شوند (اگر صدای فارسی موجود باشد)");
        voiceReplies.setChecked(false);
        root.addView(voiceReplies);
        Button speakAnswer = button("بلندخوانی پاسخ");
        speakAnswer.setOnClickListener(v -> speakPersian(latestAnswer));
        root.addView(speakAnswer);
        Button silence = button("توقف گفتار");
        silence.setOnClickListener(v -> { if (speech != null) speech.stop(); });
        root.addView(silence);

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
                + "در موتور خصوصی ثبت می‌شود. مخزن عمومی GitHub هیچ متنی دریافت نمی‌کند؛ "
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
        Button ghChatGPT = button("ارجاع درخواست خصوصی به ChatGPT Work");
        ghChatGPT.setOnClickListener(v -> confirmChatGPTWorkEvent());
        root.addView(ghChatGPT);
        root.addView(text("این دکمه یک Pull Request در مخزن خصوصی ایجاد می‌کند. "
                + "فقط اگر قبلاً یک وظیفه رویدادمحور GitHub در ChatGPT Work "
                + "فعال کرده باشی، ممکن است ChatGPT آن را دریافت کند. "
                + "این روش Codex یا کلید OpenAI API به کار نمی‌برد.", 13, false));
        ghCheck = button("دریافت پاسخ از GitHub خصوصی");
        ghCheck.setEnabled(false);
        ghCheck.setOnClickListener(v -> checkDirectGitHub());
        root.addView(ghCheck);
        Button ghApprove = button("تأیید پاسخ صحیح برای حافظه پروژه");
        ghApprove.setOnClickListener(v -> confirmDirectApproval());
        root.addView(ghApprove);
        Button ghClear = button("حذف کلید اتصال GitHub از گوشی");
        ghClear.setOnClickListener(v -> clearDirectGitHub());
        root.addView(ghClear);

        root.addView(section("گفت‌وگوی دوطرفه زنده (WSS)"));
        root.addView(text("در این حالت درخواست‌ها و وضعیت کار به‌طور هم‌زمان در یک اتصال زنده "
                + "ردوبدل می‌شوند؛ نیازی به زمان‌بندی ساعتی نیست. موتور باید روی "
                + "رایانه یا سرور قابل‌دسترسی فعال و دارای گواهی HTTPS معتبر باشد. "
                + "این کانال مستقیماً به چت شخصی ChatGPT متصل نیست.", 14, false));
        liveWss = edit("wss://your-support-server.example:8766", false);
        liveWss.setSingleLine(true);
        root.addView(liveWss);
        liveToken = edit("کلید اختصاصی کانال زنده (یا خالی برای استفاده از کلید موتور)", false);
        liveToken.setSingleLine(true);
        liveToken.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        root.addView(liveToken);
        liveProject = edit("شناسه نرم‌افزار برای کانال زنده", false);
        liveProject.setSingleLine(true);
        root.addView(liveProject);
        root.addView(text("محیطی که نتیجه باید برای آن آماده شود:", 14, false));
        liveTarget = new Spinner(this);
        liveTarget.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item,
                new String[]{"بدون محیط مشخص", "گوشی اندروید", "ویندوز", "وب", "مخزن GitHub"}));
        root.addView(liveTarget);
        root.addView(text("نوع درخواست:", 14, false));
        liveOperation = new Spinner(this);
        liveOperation.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item,
                new String[]{"پاسخ", "ساخت برنامه", "اصلاح برنامه", "تحلیل", "آماده‌سازی انتشار"}));
        root.addView(liveOperation);
        liveWorkChatGPT = new CheckBox(this);
        liveWorkChatGPT.setText("با یک تأیید، درخواست خصوصی به ChatGPT Work هم ارجاع شود "
                + "(نیازمند اتصال رویدادمحور مجاز در حساب ChatGPT و مجوز GitHub)");
        liveWorkChatGPT.setChecked(false);
        root.addView(liveWorkChatGPT);
        Button startLive = button("اتصال زنده به موتور");
        startLive.setOnClickListener(v -> connectLive());
        root.addView(startLive);
        Button askLive = button("ارسال سؤال هم‌زمان");
        askLive.setOnClickListener(v -> sendLiveQuestion());
        root.addView(askLive);
        Button workLive = button("درخواست ساخت یا اجرای برنامه");
        workLive.setOnClickListener(v -> confirmLiveWork());
        root.addView(workLive);
        liveJob = edit("شناسه کار برای پیگیری بدون قطع ارتباط", false);
        liveJob.setSingleLine(true);
        root.addView(liveJob);
        Button resumeLive = button("پیگیری کار روی کانال زنده");
        resumeLive.setOnClickListener(v -> resumeLiveWork());
        root.addView(resumeLive);
        Button stopLive = button("قطع کانال زنده");
        stopLive.setOnClickListener(v -> disconnectLive());
        root.addView(stopLive);
        liveStatus = text("کانال زنده متصل نیست.", 14, false);
        liveStatus.setTextIsSelectable(true);
        root.addView(liveStatus);
        Button diagnoseLive = button("آزمایش اتصال GitHub و TLS کانال زنده بدون ارسال رمز");
        diagnoseLive.setOnClickListener(v -> diagnoseConnectivity());
        root.addView(diagnoseLive);
        root.addView(section("تحویل خروجی ساخت‌شده به این گوشی"));
        root.addView(text("اگر عامل سازنده APK را در انتشار رسمی GitHub قرار دهد "
                + "و اثرانگشت SHA-256 معتبر اعلام کند، فایل با تأیید تو دانلود و "
                + "بررسی می‌شود؛ فقط نصب‌کننده رسمی Android اجازه نصب را دریافت می‌کند. "
                + "بدون تأیید شما نصب انجام نمی‌شود.", 14, false));
        verifiedApkInstall = button("دریافت و نصبِ فایل APK بررسی‌شده");
        verifiedApkInstall.setEnabled(false);
        verifiedApkInstall.setOnClickListener(v -> confirmVerifiedDelivery());
        root.addView(verifiedApkInstall);

        root.addView(section("محدودیت نسخه آزمایشی"));
        root.addView(text(
                "این اپ خودش مدل زبانی دانلود یا اجرا نمی‌کند. پاسخ از همان موتور "
                + "پشتیبانی تنظیم‌شده روی رایانه یا سرور دریافت می‌شود. "
                + "در حالت موتور مرکزی، بدون اتصال HTTPS معتبر و روشن‌بودن موتور پاسخ هوشمند دریافت نمی‌شود.\n"
                + "در حالت مستقیم GitHub، موتور لازم نیست ولی حساب مخزن خصوصی و عامل ChatGPT مجاز لازم است.\n"
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
                    if (voiceReplies.isChecked()) speakPersian(formatted);
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
                        + "هیچ اطلاعاتی در مخزن عمومی GitHub ثبت نمی‌شود. "
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
                    ghNotifiedRequestId = "";
                    setStatus("درخواست در مخزن خصوصی ثبت شد؛ شماره Issue: " + issue
                            + ". اکنون منتظر پاسخ عامل متصل به ChatGPT است.");
                });
            } catch (Exception e) {
                ui.post(() -> { if (active && requestVersion == version)
                    setStatus("ثبت مستقیم ناموفق: " + e.getMessage()); });
            }
        });
    }

    private void confirmChatGPTWorkEvent() {
        if (ghIssueNumber < 1 || !ghRequestId.matches("[a-f0-9]{32}")) {
            setStatus("ابتدا یک سؤال در Issue خصوصی ثبت کن.");
            return;
        }
        if (!GitHubDirectVault.available(this)) {
            setStatus("ابتدا اتصال GitHub خصوصی را برقرار کن.");
            return;
        }
        if (!GitHubDirectVault.repo(this).equalsIgnoreCase(
                ghRepo.getText().toString().trim())) {
            setStatus("مخزن تغییر کرده است؛ ابتدا اتصال را دوباره تأیید کن.");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("رویداد ChatGPT Work در GitHub خصوصی")
                .setMessage("برای درخواست موجود یک شاخه و Pull Request خصوصی ایجاد می‌شود؛ "
                        + "برای این کار توکن GitHub به مجوزهای Contents:write و "
                        + "Pull requests:write نیاز دارد. متن سؤال فقط در Issue خصوصی "
                        + "باقی می‌ماند. اتصال به ChatGPT Work باید جداگانه در حساب "
                        + "ChatGPT فعال شده باشد. این عمل ChatGPT را خودکار فعال نمی‌کند. "
                        + "موافقی؟")
                .setPositiveButton("ایجاد رویداد خصوصی", (dialog, which) -> {
                    final int issue = ghIssueNumber;
                    final String id = ghRequestId;
                    final String repo = GitHubDirectVault.repo(this);
                    final String credential;
                    try { credential = GitHubDirectVault.token(this); }
                    catch (Exception error) {
                        setStatus("کلید خصوصی GitHub قابل خواندن نیست."); return;
                    }
                    int requestVersion = ++version;
                    setStatus("در حال ایجاد Pull Request خصوصی برای ChatGPT Work...");
                    background.execute(() -> {
                        try {
                            JSONObject event = new GitHubDirectBridge(repo, credential)
                                    .triggerChatGPTWork(issue, id);
                            ui.post(() -> {
                                if (!active || requestVersion != version) return;
                                setStatus("رویداد Pull Request شمارهٔ "
                                        + event.optInt("pull_request_number")
                                        + " ایجاد شد؛ دریافت توسط ChatGPT هنوز تأیید نشده. "
                                        + "اگر وظیفهٔ Work فعال باشد، پاسخ را از Issue دریافت کن.");
                            });
                        } catch (Exception error) {
                            ui.post(() -> {
                                if (active && requestVersion == version)
                                    setStatus("ایجاد رویداد ChatGPT Work ناموفق: " + error.getMessage());
                            });
                        }
                    });
                })
                .setNegativeButton("انصراف", (dialog, which) -> {})
                .show();
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
                        if (voiceReplies.isChecked()) speakPersian(latestAnswer);
                        acceptArtifact(response.optJSONObject("artifact"));
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

    private void confirmDirectApproval() {
        if (ghIssueNumber < 1 || !ghRequestId.matches("[a-f0-9]{32}")) {
            setStatus("درخواستی برای تأیید وجود ندارد");
            return;
        }
        final String project;
        try {
            project = GitHubBridgePolicy.project(ghProject.getText().toString().trim());
            if (!GitHubDirectVault.available(this))
                throw new IllegalArgumentException("مخزن خصوصی متصل نیست");
        } catch (Exception error) { setStatus(error.getMessage()); return; }
        new AlertDialog.Builder(this)
                .setTitle("تأیید پاسخ برای یادگیری")
                .setMessage("فقط وقتی پاسخ را واقعاً بررسی کرده‌ای و درست است تأیید کن. "
                        + "این تأیید در مخزن خصوصی ثبت می‌شود تا عامل ChatGPT در درخواست‌های بعدی "
                        + "همین نرم‌افزار از آن استفاده کند. مدل به صورت خودکار بازآموزی نمی‌شود.")
                .setNegativeButton("انصراف", (d, w) -> {})
                .setPositiveButton("پاسخ درست است", (d, w) -> {
                    final String repo = GitHubDirectVault.repo(this);
                    final String secret;
                    try { secret = GitHubDirectVault.token(this); }
                    catch (Exception e) { setStatus("کلید GitHub در دسترس نیست"); return; }
                    final int issue = ghIssueNumber;
                    final String rid = ghRequestId;
                    int requestVersion = ++version;
                    setStatus("در حال ثبت بازخورد تأییدشده...");
                    background.execute(() -> {
                        try {
                            JSONObject confirmation = new GitHubDirectBridge(repo, secret)
                                    .approve(issue, rid, project);
                            ui.post(() -> {
                                if (!active || requestVersion != version) return;
                                setStatus(confirmation.optBoolean("already_approved")
                                        ? "این پاسخ قبلاً برای حافظه همین پروژه تأیید شده است."
                                        : "تأیید پاسخ در مخزن خصوصی ثبت شد؛ استفاده مجدد به عامل مجاز بستگی دارد.");
                            });
                        } catch (Exception error) {
                            ui.post(() -> { if (active && requestVersion == version)
                                setStatus("تأیید ثبت نشد: " + error.getMessage()); });
                        }
                    });
                }).show();
    }

    private void pollDirectQuietly() {
        final int issue = ghIssueNumber;
        final String rid = ghRequestId;
        if (issue <= 0 || !rid.matches("[a-f0-9]{32}") || rid.equals(ghNotifiedRequestId)) return;
        final String repo = GitHubDirectVault.repo(this);
        final String credential;
        try { credential = GitHubDirectVault.token(this); }
        catch (Exception ignored) { return; }
        directPollBusy = true;
        background.execute(() -> {
            try {
                JSONObject response = new GitHubDirectBridge(repo, credential).status(issue, rid);
                ui.post(() -> {
                    directPollBusy = false;
                    if (!active || !resumed || issue != ghIssueNumber
                            || !rid.equals(ghRequestId) || !GitHubDirectVault.available(this)) return;
                    if ("answered".equals(response.optString("status"))
                            && !rid.equals(ghNotifiedRequestId)) {
                        ghNotifiedRequestId = rid;
                        latestAnswer = response.optString("answer", "");
                        answer.setText(latestAnswer);
                        if (voiceReplies.isChecked()) speakPersian(latestAnswer);
                        acceptArtifact(response.optJSONObject("artifact"));
                        setStatus("پاسخ جدید از GitHub خصوصی دریافت شد؛ صحت اجرای آن مستقل بررسی شود.");
                    }
                });
            } catch (Exception ignored) {
                // Network unavailable: do not claim completion or display stale data.
                ui.post(() -> directPollBusy = false);
            }
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        resumed = true;
        ui.removeCallbacks(githubDirectPoll);
        ui.postDelayed(githubDirectPoll, 2_000L);
    }

    @Override
    protected void onPause() {
        resumed = false;
        ui.removeCallbacks(githubDirectPoll);
        super.onPause();
    }

    private void clearDirectGitHub() {
        try {
            GitHubDirectVault.clear(this);
            getPreferences(MODE_PRIVATE).edit()
                    .remove("direct_gh_issue").remove("direct_gh_request_id")
                    .remove("direct_gh_project").apply();
            ghIssueNumber = 0;
            ghRequestId = "";
            ghNotifiedRequestId = "";
            ghRepo.setText("");
            ghToken.setText("");
            ghCheck.setEnabled(false);
            setStatus("توکن GitHub این گوشی پاک شد.");
        } catch (Exception error) {
            setStatus("پاک‌کردن اتصال GitHub ناموفق بود.");
        }
    }

    private void startVoiceInput() {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "fa-IR");
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "سؤال یا درخواستت را به فارسی بگو");
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        try {
            startActivityForResult(intent, VOICE_REQUEST);
        } catch (android.content.ActivityNotFoundException error) {
            setStatus("برنامه تشخیص گفتار روی گوشی وجود ندارد؛ سؤال را تایپ کن.");
        } catch (SecurityException error) {
            setStatus("دسترسی میکروفون یا سرویس گفتار مجاز نیست.");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != VOICE_REQUEST || resultCode != RESULT_OK || data == null) return;
        ArrayList<String> results = data.getStringArrayListExtra(
                RecognizerIntent.EXTRA_RESULTS);
        if (results == null || results.isEmpty()) {
            setStatus("گفتار قابل تبدیل به متن نبود.");
            return;
        }
        String transcript = results.get(0).trim();
        if (transcript.isEmpty()) {
            setStatus("متن گفتار خالی است.");
            return;
        }
        if (transcript.length() > 2500) transcript = transcript.substring(0, 2500);
        question.setText(transcript);
        setStatus("متن گفتار دریافت شد؛ می‌توانی آن را اصلاح و ارسال کنی.");
        if (voiceAutoSend != null && voiceAutoSend.isChecked()) {
            if (liveClient != null && liveClient.isReady()) sendLiveQuestion();
            else setStatus("گفتار به متن تبدیل شد؛ کانال زنده متصل نیست و متن خودکار ارسال نشد.");
        }
    }

    private void speakPersian(String value) {
        if (value == null || value.trim().isEmpty()) {
            setStatus("متنی برای خواندن وجود ندارد.");
            return;
        }
        if (!speechReady || speech == null) {
            setStatus("موتور گفتار فارسی روی گوشی حاضر نیست. متن همچنان قابل مشاهده است.");
            return;
        }
        String safe = value.length() > 3700 ? value.substring(0, 3700) : value;
        speech.speak(safe, TextToSpeech.QUEUE_FLUSH, null, "amin_voice_reply");
    }

    private void acceptArtifact(JSONObject artifact) {
        if (artifact == null || !"android".equals(artifact.optString("environment", ""))) return;
        try {
            availableApkUrl = DeliveryPolicy.releaseUrl(artifact.getString("url"));
            availableApkSha = DeliveryPolicy.sha256(artifact.getString("sha256"));
            verifiedApkInstall.setEnabled(true);
            liveMessage("خروجی APK برای اندروید معرفی شد؛ نصب هنوز انجام نشده است.");
        } catch (Exception invalid) {
            availableApkUrl = "";
            availableApkSha = "";
            verifiedApkInstall.setEnabled(false);
            liveMessage("اطلاعات APK معتبر نیست؛ نصب مسدود شد.");
        }
    }

    private void confirmVerifiedDelivery() {
        final String url = availableApkUrl;
        final String sha = availableApkSha;
        try {
            DeliveryPolicy.releaseUrl(url);
            DeliveryPolicy.sha256(sha);
        } catch (Exception invalid) {
            liveMessage("خروجی نصب معتبر نیست.");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("اجازه دانلود و نصب در اندروید")
                .setMessage("فقط APK رسمی Github دریافت می‌شود؛ پس از بررسی SHA-256، "
                        + "نصب‌کنندهٔ اندروید باز خواهد شد. اعتبار SHA جایگزین "
                        + "اعتماد به سازنده و مجوزهای برنامه نیست. "
                        + "نصب بدون تأیید دوباره در سیستم ممکن نیست. ادامه می‌دهی؟")
                .setNegativeButton("انصراف", (d, which) -> {})
                .setPositiveButton("تأیید دریافت", (d, which) -> {
                    if (!AndroidDelivery.canRequestInstall(this)) {
                        liveMessage("اجازه نصب از این برنامه غیرفعال است؛ در تنظیمات فعال کن "
                                + "و سپس دوباره دکمه دریافت را بزن.");
                        try { AndroidDelivery.askInstallPermission(this); }
                        catch (Exception e) { liveMessage("باز کردن تنظیمات نصب ممکن نشد."); }
                        return;
                    }
                    verifiedApkInstall.setEnabled(false);
                    liveMessage("در حال دانلود و بررسی اثرانگشت فایل APK...");
                    background.execute(() -> {
                        try {
                            File verified = AndroidDelivery.downloadVerified(
                                    getApplicationContext(), url, sha);
                            ui.post(() -> {
                                if (!active) return;
                                verifiedApkInstall.setEnabled(true);
                                liveMessage("اثر انگشت فایل تأیید شد. در حال باز کردن نصب‌کنندهٔ Android...");
                                try {
                                    AndroidDelivery.launchSystemInstaller(this, verified);
                                } catch (Exception problem) {
                                    liveMessage("نصب‌کننده باز نشد: " + problem.getClass().getSimpleName());
                                }
                            });
                        } catch (Exception error) {
                            ui.post(() -> {
                                if (active) {
                                    verifiedApkInstall.setEnabled(true);
                                    liveMessage("دریافت/بررسی فایل ناموفق: "
                                            + error.getClass().getSimpleName());
                                }
                            });
                        }
                    });
                })
                .show();
    }

    private void liveMessage(String value) {
        if (active && liveStatus != null) liveStatus.setText(value);
    }

    private void diagnoseConnectivity() {
        String raw = liveWss.getText().toString().trim();
        liveMessage("در حال بررسی اتصال بدون ارسال کلید یا مکالمه...");
        int id = ++diagnosticVersion;
        background.execute(() -> {
            JSONObject github = ConnectivityProbe.github();
            JSONObject wss = raw.isEmpty() ? null : ConnectivityProbe.liveTls(raw);
            ui.post(() -> {
                if (!active || id != diagnosticVersion) return;
                String output = ConnectivityProbe.explain("GitHub API", github);
                if (wss != null) output += "\\n" + ConnectivityProbe.explain("WSS", wss);
                else output += "\\nنشانی WSS خالی است؛ فقط GitHub بررسی شد.";
                output += "\\nاین آزمایش فقط از همین گوشی انجام شده؛ "
                        + "وصل شدن به ChatGPT یا اجرای درخواست را تأیید نمی‌کند.";
                liveMessage(output);
            });
        });
    }

    private void connectLive() {
        final String endpoint, secret, project, freshToken;
        try {
            endpoint = LiveEndpointPolicy.requireWss(liveWss.getText().toString());
            project = LiveEndpointPolicy.project(liveProject.getText().toString().trim());
            freshToken = liveToken.getText().toString().trim();
            // The HTTPS engine token is NOT a generic WSS token. This vault
            // is bound to one endpoint and cannot silently follow an address edit.
            secret = freshToken.isEmpty()
                    ? LiveTokenVault.token(this, endpoint)
                    : SupportEndpoint.validateToken(freshToken);
        } catch (Exception problem) {
            liveMessage("تنظیمات اتصال زنده معتبر نیست: " + problem.getMessage());
            return;
        }
        disconnectLive();
        final int attempt = ++liveGeneration;
        liveMessage("در حال اتصال و احراز هویت WSS...");
        try {
            liveClient = new LiveSocketClient(endpoint, secret, new LiveSocketClient.Listener() {
                @Override public void onMessage(JSONObject event) {
                    ui.post(() -> {
                        if (!active || attempt != liveGeneration) return;
                        String type = event.optString("type", "");
                        if ("ready".equals(type)) {
                            if (!project.equals(event.optString("project", ""))) {
                                liveMessage("پروژه پاسخ‌دهنده با کلید انتخابی مطابقت ندارد؛ اتصال قطع شد.");
                                disconnectLive();
                                return;
                            }
                            try {
                                // Only persist a new secret after verified WSS + auth response.
                                if (!freshToken.isEmpty()) LiveTokenVault.save(
                                        MainActivity.this, endpoint, freshToken);
                                getPreferences(MODE_PRIVATE).edit()
                                        .putString("live_wss", endpoint)
                                        .putString("live_project", project).apply();
                                liveToken.setText("");
                                liveMessage("کانال دوطرفه امن متصل است؛ کلید فقط برای همین نشانی ذخیره شد. "
                                        + "ChatGPT شخصی هنوز به کانال اضافه نشده.");
                            } catch (Exception failure) {
                                liveMessage("ذخیره امن کلید ممکن نشد؛ اتصال قطع شد.");
                                disconnectLive();
                            }
                        } else if ("answer".equals(type)) {
                            latestAnswer = event.optString("answer", "");
                            answer.setText(latestAnswer);
                            if (voiceReplies.isChecked()) speakPersian(latestAnswer);
                            liveMessage("پاسخ زنده دریافت شد؛ عملیات اجرایی انجام نشده.");
                        } else if ("work_state".equals(type)) {
                            String jobId = event.optString("id_of_job", "");
                            if (jobId.matches("[a-f0-9]{32}")) {
                                liveJob.setText(jobId);
                                getPreferences(MODE_PRIVATE).edit().putString("live_job", jobId).apply();
                            }
                            String state = event.optString("status", "");
                            acceptArtifact(event.optJSONObject("artifact"));
                            if (event.has("answer")) {
                                latestAnswer = event.optString("answer", "");
                                answer.setText(latestAnswer);
                                if (voiceReplies.isChecked()) speakPersian(latestAnswer);
                            }
                            liveMessage("وضعیت ساخت/اجرا: " + state
                                    + (event.optBoolean("action_performed", false)
                                            ? "؛ اجرای عملیات گزارش شده (نیازمند بررسی)"
                                            : "؛ انجام عملیات هنوز تأیید نشده"));
                        } else if ("accepted".equals(type)) {
                            liveMessage("درخواست پذیرفته شد؛ کانال برای پرسش‌های بعدی باز است.");
                        } else if ("progress".equals(type)) {
                            liveMessage(event.optString("message", event.optString("status")));
                        } else if ("error".equals(type)) {
                            liveMessage("خطای درخواست زنده: " + event.optString("message", ""));
                        }
                    });
                }
                @Override public void onClosed(String description) {
                    ui.post(() -> {
                        if (attempt == liveGeneration) liveMessage(description);
                    });
                }
            });
        } catch (Exception failure) {
            liveMessage("اتصال برقرار نشد: " + failure.getMessage());
        }
    }

    private void sendLiveQuestion() {
        try {
            if (liveClient == null) throw new IllegalStateException("ابتدا اتصال زنده را برقرار کن");
            String requestId = liveClient.ask(
                    LiveEndpointPolicy.project(liveProject.getText().toString().trim()),
                    question.getText().toString().trim());
            liveMessage("سؤال " + requestId + " در کانال زنده ارسال شد.");
        } catch (Exception problem) {
            liveMessage("ارسال سؤال ناموفق: " + problem.getMessage());
        }
    }

    private void confirmLiveWork() {
        if (liveClient == null || !liveClient.isReady()) {
            liveMessage("ابتدا کانال زنده را متصل کن.");
            return;
        }
        String message = question.getText().toString().trim();
        if (message.isEmpty() || message.length() > 2500) {
            liveMessage("متن درخواست ساخت باید بین ۱ و ۲۵۰۰ نویسه باشد.");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("ارسال درخواست ساخت/اجرا")
                .setMessage("این دستور در موتور خصوصی ثبت می‌شود؛ در صورت تنظیم "
                        + "مخزن خصوصی به GitHub ارجاع می‌شود. "
                        + (liveWorkChatGPT.isChecked()
                            ? "همچنین رویداد Pull Request خصوصی برای ChatGPT Work ساخته می‌شود؛ "
                              + "دریافت توسط ChatGPT نیازمند وظیفهٔ فعال و مجوزهای حساب است. "
                            : "")
                        + "قبولی ساخت یا اجرای نهایی فقط پس از ارائه شواهد است. ارسال شود؟")
                .setPositiveButton("تأیید و ارسال", (d, which) -> {
                    try {
                        String[] destinations = {"none", "android", "windows", "web", "github"};
                        String[] operations = {"answer", "build", "repair", "analyze", "release"};
                        liveClient.work(
                                LiveEndpointPolicy.project(liveProject.getText().toString().trim()),
                                message,
                                destinations[liveTarget.getSelectedItemPosition()],
                                operations[liveOperation.getSelectedItemPosition()],
                                liveWorkChatGPT.isChecked());
                        liveMessage("کار در صف زنده ثبت می‌شود؛ منتظر شناسه و وضعیت هستیم.");
                    } catch (Exception problem) {
                        liveMessage("ثبت کار ناموفق: " + problem.getMessage());
                    }
                })
                .setNegativeButton("انصراف", (d, which) -> {})
                .show();
    }

    private void resumeLiveWork() {
        try {
            if (liveClient == null) throw new IllegalStateException("کانال زنده برقرار نیست");
            liveClient.resume(
                    LiveEndpointPolicy.project(liveProject.getText().toString().trim()),
                    LiveEndpointPolicy.jobId(liveJob.getText().toString().trim()));
            liveMessage("درخواست پیگیری زنده ارسال شد.");
        } catch (Exception problem) {
            liveMessage("پیگیری ناموفق: " + problem.getMessage());
        }
    }

    private void disconnectLive() {
        ++liveGeneration; // Prevent callbacks from stale WSS connections.
        if (liveClient != null) {
            liveClient.close();
            liveClient = null;
        }
        liveMessage("کانال زنده قطع شد.");
    }

    private void clearConnection() {
        try {
            disconnectLive();
            TokenVault.clear(this);
            LiveTokenVault.clear(this);
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
        resumed = false;
        ui.removeCallbacks(githubDirectPoll);
        disconnectLive();
        if (speech != null) {
            speech.stop();
            speech.shutdown();
            speech = null;
        }
        ++version;
        background.shutdownNow();
        super.onDestroy();
    }
}
