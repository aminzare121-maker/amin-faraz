package ir.amin.gold;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.KeyguardManager;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Connected DEMO owner app. Original offline simulator remains a separate Activity. */
public final class DashboardActivity extends Activity {
    private final int BG=0xfff4f6fb,PANEL=0xffffffff,TEXT=0xff102653,MUTED=0xff62748b,GOLD=0xff946000,GREEN=0xff08765a,RED=0xffb52f42;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final ExecutorService network=Executors.newSingleThreadExecutor();
    private SecureState storage;
    private JSONObject connection=new JSONObject(),status=new JSONObject(),report=new JSONObject(),research=new JSONObject(),sources=new JSONObject();
    private JSONArray bars=new JSONArray(),events=new JSONArray(),commands=new JSONArray();
    private String error="",frame="15m",barsFrame="15m";private int tab=0;
    private boolean unlocked=false,authPending=false,active=false,busy=false,setupReady=false;
    private long receivedElapsed=-1,lastReceivedWall=0;
    private boolean restoredView=false;
    private boolean previewMode=false;
    private ScrollView contentScroll;
    private int shownTab=-1;
    private final java.util.Map<Integer,Integer> scrollPositions=new java.util.HashMap<>();
    private LinearLayout root,body;
    private final Runnable poll=new Runnable(){public void run(){if(active&&unlocked&&paired()){fetch();handler.postDelayed(this,5000);}}};

    public void onCreate(Bundle state){
        super.onCreate(state);getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE,WindowManager.LayoutParams.FLAG_SECURE);
        storage=new SecureState(this,"connection");
        try{String saved=storage.read();if(saved!=null)connection=new JSONObject(saved);}catch(Exception e){error="خواندن اتصال ذخیره‌شده ناموفق بود؛ اطلاعات قبلی حفظ شده‌اند.";}
        importCableSetup();
        previewMode=!paired();
        if(state!=null){tab=state.getInt("tab",0);previewMode=state.getBoolean("cabin_preview",!paired())&&!paired();for(int i=0;i<6;i++)scrollPositions.put(i,state.getInt("scroll_"+i,0));}
        render();
    }
    private void importCableSetup(){
        if(paired())return;
        java.io.File dir=getExternalFilesDir(null);
        if(dir==null)return;
        java.io.File file=new java.io.File(dir,"host-setup.json");
        if(!file.isFile())return;
        try{
            if(file.length()>8192)throw new IllegalArgumentException();
            byte[] bytes=java.nio.file.Files.readAllBytes(file.toPath());
            JSONObject supplied=new JSONObject(new String(bytes,java.nio.charset.StandardCharsets.UTF_8));
            String issue=SetupValidation.endpoint(supplied.optString("url"),supplied.optString("pin"));
            if(!issue.isEmpty()||!"usb-localhost".equals(supplied.optString("transport"))||!"localhost".equals(new java.net.URI(supplied.getString("url")).getHost()))throw new IllegalArgumentException();
            JSONObject clean=new JSONObject();
            for(String key:new String[]{"url","pin","pairing_code","pairing_expires","transport"})if(supplied.has(key))clean.put(key,supplied.get(key));
            storage.write(clean.toString());connection=clean;
            if(!file.delete())error="مشخصات دریافت شد؛ پاک‌سازی فایل انتقال انجام نشد.";
        }catch(Exception e){error="دریافت مشخصات میزبان ناموفق بود؛ اتصال برقرار نشده است.";}
    }
    protected void onStart(){super.onStart();active=true;if(paired()&&!unlocked)authenticate();else{unlocked=true;handler.post(poll);}}
    protected void onStop(){super.onStop();active=false;handler.removeCallbacks(poll);if(!authPending)unlocked=false;}
    protected void onDestroy(){super.onDestroy();network.shutdownNow();}
    protected void onSaveInstanceState(Bundle s){s.putInt("tab",tab);s.putBoolean("cabin_preview",previewMode);if(contentScroll!=null&&shownTab>=0)scrollPositions.put(shownTab,contentScroll.getScrollY());for(int i=0;i<6;i++)s.putInt("scroll_"+i,scrollPositions.containsKey(i)?scrollPositions.get(i):0);super.onSaveInstanceState(s);}
    protected void onActivityResult(int req,int result,Intent data){super.onActivityResult(req,result,data);if(req==700){authPending=false;unlocked=result==RESULT_OK;if(unlocked)restoreCachedView();render();if(unlocked)handler.post(poll);}}
    private void restoreCachedView(){
        if(!paired()||!unlocked)return;
        try{
            String raw=new SecureState(this,"owner-view").read();if(raw==null)return;
            JSONObject saved=new JSONObject(raw);
            if(!ViewFreshness.sameSession(ConnectionSession.identity(this),saved.optString("session")))return;
            JSONObject savedStatus=saved.getJSONObject("status"),savedReport=saved.getJSONObject("report"),savedResearch=saved.getJSONObject("research"),savedSources=saved.getJSONObject("sources");
            JSONArray savedBars=saved.getJSONArray("bars"),savedEvents=saved.getJSONArray("events"),savedCommands=saved.getJSONArray("commands");
            String savedFrame=saved.getString("frame");long savedWall=saved.getLong("received_wall_ms");
            status=savedStatus;report=savedReport;research=savedResearch;sources=savedSources;bars=savedBars;events=savedEvents;commands=savedCommands;frame=savedFrame;barsFrame=savedFrame;
            lastReceivedWall=savedWall;receivedElapsed=-1;restoredView=true;
        }catch(Exception e){error="بازیابی نمایش قبلی ناموفق بود؛ اطلاعات ذخیره‌شده پاک نشده‌اند.";}
    }
    private void clearViewState(){status=new JSONObject();report=new JSONObject();research=new JSONObject();sources=new JSONObject();bars=new JSONArray();events=new JSONArray();commands=new JSONArray();lastReceivedWall=0;receivedElapsed=-1;restoredView=false;frame="15m";barsFrame="15m";}
    private boolean paired(){return connection.has("access_token");}
    private void authenticate(){
        if(authPending)return;
        KeyguardManager k=(KeyguardManager)getSystemService(KEYGUARD_SERVICE);
        Intent i=k.createConfirmDeviceCredentialIntent("متاتریدر امین","تأیید هویت برای مشاهده و کنترل حساب دمو");
        if(i==null){error="برای اتصال حساب، ابتدا قفل امن گوشی را تنظیم کن.";render();return;}
        authPending=true;startActivityForResult(i,700);
    }
    private int dp(int n){return (int)(n*getResources().getDisplayMetrics().density+.5f);}
    private LinearLayout col(){LinearLayout l=new LinearLayout(this);l.setOrientation(1);return l;}
    private LinearLayout row(){LinearLayout l=new LinearLayout(this);l.setOrientation(0);l.setGravity(Gravity.CENTER_VERTICAL);return l;}
    private GradientDrawable shape(int color){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(16));d.setStroke(dp(1),0xffe1e7f0);return d;}
    private TextView text(String value,int size,int color){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(color);t.setGravity(Gravity.RIGHT);t.setTextDirection(View.TEXT_DIRECTION_FIRST_STRONG_RTL);t.setPadding(0,dp(5),0,dp(5));t.setLineSpacing(dp(3),1);return t;}
    private LinearLayout card(String title){LinearLayout c=col();c.setPadding(dp(16),dp(12),dp(16),dp(14));c.setBackground(shape(PANEL));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(12);body.addView(c,p);if(!title.isEmpty()){TextView t=text(title,18,TEXT);t.setTypeface(null,Typeface.BOLD);c.addView(t);}return c;}
    private Button button(LinearLayout parent,String label,boolean gold,Runnable action){Button b=new Button(this);b.setAllCaps(false);b.setText(label);b.setTextSize(14);b.setTextColor(gold?Color.WHITE:TEXT);b.setBackground(shape(gold?TEXT:PANEL));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(50));p.topMargin=dp(9);parent.addView(b,p);b.setOnClickListener(v->action.run());if(previewMode){b.setEnabled(false);b.setAlpha(.5f);}return b;}
    private EditText input(LinearLayout parent,String hint,boolean secret){EditText e=new EditText(this);e.setHint(hint);e.setTextColor(TEXT);e.setHintTextColor(MUTED);e.setTextSize(14);e.setSingleLine(true);e.setTextDirection(View.TEXT_DIRECTION_LTR);e.setInputType(secret?InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD:InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);parent.addView(e,new LinearLayout.LayoutParams(-1,dp(56)));return e;}
    private void metric(LinearLayout parent,String label,String value,int color){LinearLayout r=row();r.addView(text(label,13,MUTED),new LinearLayout.LayoutParams(0,-2,1));TextView t=text(value,15,color);t.setTextDirection(View.TEXT_DIRECTION_FIRST_STRONG);r.addView(t);parent.addView(r);}
    private void accountTile(LinearLayout parent,String label,String value){LinearLayout tile=col();tile.setPadding(dp(12),dp(10),dp(12),dp(10));tile.setBackground(shape(BG));tile.addView(text(label,11,MUTED));TextView amount=text(value,22,TEXT);amount.setTypeface(null,Typeface.BOLD);amount.setTextDirection(View.TEXT_DIRECTION_LTR);tile.addView(amount);tile.addView(text("USD",10,MUTED));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,1);p.setMargins(dp(4),dp(4),dp(4),dp(4));parent.addView(tile,p);}
    private void toast(String s){Toast.makeText(this,s,Toast.LENGTH_LONG).show();}
    private JSONObject obj(JSONObject o,String key){JSONObject result=o.optJSONObject(key);return result==null?new JSONObject():result;}
    private String reason(String code){
        switch(code){case "NEWS_NOT_CLEARED":return "پوشش معتبر خبر تأیید نشده";case "RECONCILIATION_REQUIRED":return "تطبیق وضعیت سفارش لازم است";case "NEW_ORDERS_PAUSED":return "سفارش جدید متوقف است";case "UNKNOWN_ORDER":return "نتیجه یک سفارش نامعلوم است";case "NO_ALIGNED_SETUP":return "شرایط تحلیل همسو نیست";case "AWAITING_VALIDATED_RESEARCH_APPROVAL":return "نسخه پژوهشی تأییدشده در دسترس نیست";default:return code;}
    }
    private void render(){
        if(contentScroll!=null&&shownTab>=0)scrollPositions.put(shownTab,contentScroll.getScrollY());
        previewMode=previewMode&&!paired();
        if(previewMode)getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);else getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE,WindowManager.LayoutParams.FLAG_SECURE);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        root=col();root.setBackgroundColor(BG);root.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);root.setPadding(dp(16),dp(8),dp(16),dp(8));
        root.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(dp(16),i.getSystemWindowInsetTop(),dp(16),i.getSystemWindowInsetBottom());return i;});setContentView(root);root.requestApplyInsets();
        buildCabinHeader();
        ScrollView scroll=new ScrollView(this);contentScroll=scroll;shownTab=tab;scroll.setFillViewport(true);body=col();body.setPadding(0,dp(12),0,dp(16));scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        final int savedScroll=scrollPositions.containsKey(tab)?scrollPositions.get(tab):0;scroll.post(()->scroll.scrollTo(0,savedScroll));
        if(paired()&&!unlocked){LinearLayout c=card("ورود مالک");button(c,"تأیید هویت با قفل گوشی",true,this::authenticate);if(!error.isEmpty())c.addView(text(error,13,RED));return;}
        if(!error.isEmpty())card("هشدار اتصال").addView(text(error,13,RED));
        if(paired()&&restoredView){LinearLayout cached=card("★ ۷ — آخرین اطلاعات ذخیره‌شده");cached.addView(text("این اطلاعات زنده نیستند؛ دریافت تازه و احراز اتصال لازم است. هیچ فرمانی از دادهٔ کهنه اجرا نمی‌شود.",13,GOLD));if(lastReceivedWall>0)cached.addView(text("آخرین دریافت: "+java.text.DateFormat.getDateTimeInstance().format(new java.util.Date(lastReceivedWall)),12,MUTED));}
        if(!paired()&&!previewMode){pairForm();button(body,"★ ۹ — پیش‌نمایش کامل کابین",true,()->{previewMode=true;tab=0;render();});return;}
        if(previewMode){LinearLayout preview=card("★ ۹ — کابین اندروید • پیش‌نمایش");preview.setBackground(shape(0xfffff2c9));preview.addView(text("این پیش‌نمایش دادهٔ حساب، قیمت نمونه یا معاملهٔ ساختگی ندارد. صفحه‌ها را ببین؛ کنترل‌های مالی غیرفعال‌اند.",13,GOLD));}
        if(tab==0)home();else if(tab==1)risk();else if(tab==2)trades();else if(tab==3)logs();else if(tab==5)strategyReview();else settings();
        buildCabinNavigation();
    }
    private void buildCabinHeader(){
        LinearLayout header=row();header.setPadding(0,dp(10),0,dp(8));
        LinearLayout brand=col();TextView name=text("امین",25,TEXT);name.setTypeface(null,Typeface.BOLD);brand.addView(name);brand.addView(text("کابین اختصاصی مالک • 0.4.3.10",11,MUTED));
        header.addView(brand,new LinearLayout.LayoutParams(0,-2,1));
        TextView menu=text("۸  بخش‌ها",13,TEXT);menu.setPadding(dp(14),dp(12),dp(14),dp(12));menu.setBackground(shape(PANEL));menu.setContentDescription("فهرست مشترک بخش‌های کابین مالک");menu.setOnClickListener(v->openCabinMenu());header.addView(menu);
        root.addView(header);
        LinearLayout strip=row();TextView state=text(previewMode?"پیش‌نمایش • بدون دادهٔ زنده":healthy()?"دادهٔ تازهٔ حساب دمو":restoredView?"آخرین دریافت • دادهٔ کهنه":paired()?"در انتظار دریافت تازه":"آماده‌سازی اتصال",12,healthy()?GREEN:GOLD);
        strip.addView(state,new LinearLayout.LayoutParams(0,-2,1));
        if(previewMode){TextView connect=text("تنظیم اتصال",12,TEXT);connect.setPadding(dp(8),dp(8),dp(8),dp(8));connect.setOnClickListener(v->{previewMode=false;tab=0;render();});strip.addView(connect);}
        root.addView(strip);
    }
    private void buildCabinNavigation(){
        LinearLayout nav=row();nav.setPadding(dp(4),dp(5),dp(4),dp(5));nav.setBackground(shape(PANEL));
        String[] names={"خانه","سرمایه","معاملات","گزارش","بیشتر"};
        for(int i=0;i<names.length;i++){final int n=i;boolean selected=i==tab||i==4&&tab>=4;TextView t=text(names[i],12,selected?TEXT:MUTED);t.setGravity(Gravity.CENTER);t.setTypeface(null,selected?Typeface.BOLD:Typeface.NORMAL);t.setPadding(0,dp(15),0,dp(15));if(selected)t.setBackground(shape(0xfffff2c9));t.setOnClickListener(v->{if(n==4)openCabinMenu();else{tab=n;render();}});nav.addView(t,new LinearLayout.LayoutParams(0,dp(54),1));}
        root.addView(nav);
    }
    private void pairForm(){
        LinearLayout intro=card("۱ — آماده‌سازی اتصال • تازه");intro.addView(text("اپ روی گوشی نصب شده است؛ موتور MT5 روی لپ‌تاپ اجرا می‌شود. نصب اپ به‌تنهایی اتصال زنده را برقرار نمی‌کند. ابتدا آماده‌بودن میزبان بررسی می‌شود؛ سپس کدهای مالک لازم می‌شوند.",14,GOLD));intro.addView(text("متاتریدر روی ویندوز اجرا می‌شود. این برنامه از طریق سرور امن، وضعیت حساب دمو را می‌گیرد و فرمان‌های تو را ارسال می‌کند.",14,MUTED));
        intro.addView(text("نشانی، اثر انگشت گواهی و کد اتصال از راه‌اندازی سرور به دست می‌آیند. رمز بروکر روی گوشی وارد نمی‌شود.",13,MUTED));
        LinearLayout c=card("۲ — مشخصات اتصال میزبان");
        EditText url=input(c,"https://your-server:8443",false),pin=input(c,"SHA-256 گواهی سرور • ۶۴ نویسه",false),code=input(c,"کد اتصال یک‌بارمصرف",true),otp=input(c,"کد ۶ رقمی احراز هویت",true);otp.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        url.setText(connection.optString("url",""));pin.setText(connection.optString("pin",""));
        boolean cable="usb-localhost".equals(connection.optString("transport"));
        if(cable){
            c.addView(text("★ مشخصات میزبان از کابل دریافت شد. کابل باید متصل بماند؛ این مسیر اتصال بی‌سیم نیست.",13,GOLD));
            url.setVisibility(View.GONE);pin.setVisibility(View.GONE);code.setVisibility(View.GONE);
            if(System.currentTimeMillis()/1000<connection.optLong("pairing_expires",0))code.setText(connection.optString("pairing_code",""));
            else c.addView(text("کد اتصال منقضی شده؛ از لپ‌تاپ دوباره منتقل شود. کد احراز هویت شخصی را هنوز وارد نکن.",13,RED));
        }
        button(c,"بررسی آماده‌بودن اتصال",true,()->{
            String issue=SetupValidation.endpoint(url.getText().toString().trim(),pin.getText().toString().trim());
            if(!issue.isEmpty()){error=issue;toast(issue);return;}
            if(busy)return;busy=true;
            try{JSONObject cfg=new JSONObject();cfg.put("url",url.getText().toString().trim());cfg.put("pin",pin.getText().toString().trim());
            network.execute(()->{try{JSONObject h=new RemoteApi(cfg).request("GET","/v1/health",null,false);
                boolean ready="amin-mt5".equals(h.optString("service"))&&"demo-only".equals(h.optString("execution_mode"));
                handler.post(()->{busy=false;setupReady=ready;error=ready?"": "میزبان پاسخ داد ولی سرویس دمو تأیید نشد.";toast(ready?"ارتباط امن با میزبان تأیید شد؛ اکنون کدهای مالک را وارد کنید.":error);});
            }catch(Exception ex){handler.post(()->{busy=false;setupReady=false;error="میزبان در دسترس نیست یا هویت آن تأیید نشد. کد مالک هنوز لازم نیست؛ اتصال لپ‌تاپ باید آماده شود.";toast(error);});}});
            }catch(Exception ex){busy=false;toast("اطلاعات اتصال آماده نیست.");}
        });
        c.addView(text("۳ — فقط پس از بررسی موفق میزبان، کد یک‌بارمصرف و کد شش‌رقمی را وارد کن. هیچ کدی به‌جای مالک ساخته یا وارد نمی‌شود.",13,GOLD));
        button(c,"اتصال امن به حساب دمو",true,()->{
            String issue=SetupValidation.endpoint(url.getText().toString().trim(),pin.getText().toString().trim());
            if(!issue.isEmpty()){toast(issue);return;}
            if(!setupReady){toast("ابتدا دکمهٔ بررسی آماده‌بودن اتصال را بزنید.");return;}
            issue=SetupValidation.codes(code.getText().toString(),otp.getText().toString());if(!issue.isEmpty()){toast(issue);return;}

            if(busy)return;
            KeyguardManager k=(KeyguardManager)getSystemService(KEYGUARD_SERVICE);if(!k.isDeviceSecure()){toast("ابتدا برای گوشی قفل امن تنظیم کن.");return;}
            try{
                JSONObject settings=new JSONObject();String address=url.getText().toString().trim();while(address.endsWith("/"))address=address.substring(0,address.length()-1);
                settings.put("url",address);settings.put("pin",pin.getText().toString().trim());
                JSONObject b=new JSONObject();b.put("code",code.getText().toString());b.put("otp",otp.getText().toString());b.put("device",Build.MANUFACTURER+" "+Build.MODEL);
                busy=true;toast("در حال بررسی اتصال امن…");
                network.execute(()->{try{
                    ConnectionSession.pair(this,settings,b);
                    handler.post(()->{clearViewState();connection=settings;busy=false;error="";unlocked=false;authenticate();});
                }catch(Exception e){handler.post(()->{busy=false;error=String.valueOf(e.getMessage());render();});}});
            }catch(Exception e){toast("مشخصات اتصال را بررسی کن.");}
        });
        LinearLayout local=card("آشنایی با مدیریت سرمایه");local.addView(text("شبیه‌ساز آفلاین قبلی جداگانه در دسترس است و به هیچ حسابی سفارش نمی‌دهد.",13,MUTED));button(local,"بازکردن شبیه‌ساز آفلاین",false,()->startActivity(new Intent(this,MainActivity.class)));
    }
    private void openCabinMenu(){
        try{
            JSONArray sections=OwnerCabinCatalog.load(this);String[] labels=new String[sections.length()];
            for(int i=0;i<labels.length;i++){JSONObject item=sections.getJSONObject(i);labels[i]=item.getString("label")+(!item.isNull("android_action")?" — بازکردن مستقل":item.isNull("android_route")?" — در حال انتقال":"");}
            new AlertDialog.Builder(this).setTitle("کابین مالک • فهرست مشترک با ویندوز")
                .setItems(labels,(dialog,index)->{
                    JSONObject item=sections.optJSONObject(index);if(item==null)return;
                    if("launch-mt5".equals(item.optString("android_action"))){OwnerExternalApps.metaTrader(this);return;}
                    if("open-eplanet".equals(item.optString("android_action"))){OwnerExternalApps.ePlanet(this);return;}
                    if(item.isNull("android_route")){toast("این بخش هنوز به اندروید منتقل نشده است؛ وجود نام در فهرست به معنی آماده‌بودن آن نیست.");return;}
                    int route=item.optInt("android_route",-1);
                    if(!paired()&&!previewMode){previewMode=true;}
                    tab=route;render();
                }).setNegativeButton("بستن",null).show();
        }catch(Exception e){toast("فهرست مشترک کابین قابل خواندن نیست؛ تنظیمات قبلی حفظ شد.");}
    }
    private void fetch(){
        if(busy||!paired()||!unlocked)return;busy=true;
        final JSONObject cfg=connection;final String selected=frame;
        network.execute(()->{try{
            JSONObject s=ConnectionSession.call(this,"GET","/v1/status",null),r=ConnectionSession.call(this,"GET","/v1/reports",null),
                ev=ConnectionSession.call(this,"GET","/v1/events",null),candles=ConnectionSession.call(this,"GET","/v1/candles/"+selected,null),
                researchResult=ConnectionSession.call(this,"GET","/v1/research",null),cmds=ConnectionSession.call(this,"GET","/v1/commands",null),
                sourceResult=ConnectionSession.call(this,"GET","/v1/sources",null);
            // Calendar failure must not fail unrelated dashboard reads. Never POST.
            try { JSONObject calendarState=ConnectionSession.call(this,"GET","/v1/research/calendar",null);
                researchResult.put("amin_calendar_report",obj(calendarState,"last_report"));
            } catch(Exception calendarError) { researchResult.put("amin_calendar_report",new JSONObject()); }
            JSONArray newEvents=ev.optJSONArray("events"),newBars=candles.optJSONArray("bars"),newCommands=cmds.optJSONArray("commands");
            if(newEvents==null)newEvents=new JSONArray();if(newBars==null)newBars=new JSONArray();if(newCommands==null)newCommands=new JSONArray();
            final JSONArray finalEvents=newEvents,finalBars=newBars,finalCommands=newCommands;
            long receivedWall=System.currentTimeMillis(),receivedMono=android.os.SystemClock.elapsedRealtime();
            JSONObject cached=new JSONObject().put("session",ConnectionSession.identity(this)).put("frame",selected).put("received_wall_ms",receivedWall)
                .put("status",s).put("report",r).put("research",researchResult).put("sources",sourceResult).put("events",finalEvents).put("bars",finalBars).put("commands",finalCommands);
            String saveIssue="";try{String encoded=cached.toString();if(encoded.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>8*1024*1024)throw new IllegalArgumentException();new SecureState(this,"owner-view").write(encoded);}catch(Exception saveError){saveIssue="داده دریافت شد ولی ذخیرهٔ پایدار آن تأیید نشد؛ دادهٔ تازه در همین نمایش در دسترس است.";}
            final String finalSaveIssue=saveIssue;
            handler.post(()->{busy=false;if(connection!=cfg||!unlocked||!active)return;status=s;receivedElapsed=receivedMono;lastReceivedWall=receivedWall;restoredView=false;report=r;research=researchResult;sources=sourceResult;events=finalEvents;bars=finalBars;barsFrame=selected;commands=finalCommands;error=finalSaveIssue;render();});
        }catch(Exception e){handler.post(()->{busy=false;if(connection!=cfg)return;receivedElapsed=-1;restoredView=lastReceivedWall>0;error="ارتباط تازه تأیید نشد؛ آخرین اطلاعات دریافت‌شده حفظ شده‌اند. دادهٔ کهنه مجوز اجرای فرمان نیست.";if(active&&unlocked)render();});}});
    }
    private boolean healthy(){return ViewFreshness.live(restoredView,status.optBoolean("connected",false),status.optBoolean("stale",true),receivedElapsed,android.os.SystemClock.elapsedRealtime());}
    private void home(){
        LinearLayout launch=card("★ ۱۰ — متاتریدر و کابین ای‌پلنت");
        Button mt5=button(launch,"اجرای متاتریدر ۵ نصب‌شده",true,()->OwnerExternalApps.metaTrader(this));mt5.setEnabled(true);mt5.setAlpha(1);
        Button ep=button(launch,"بازکردن ای‌پلنت • مسیر نسخهٔ ویندوز",false,()->OwnerExternalApps.ePlanet(this));ep.setEnabled(true);ep.setAlpha(1);
        launch.addView(text("همان برنامه یا مسیر رسمی جداگانه باز می‌شود. این دکمه‌ها سفارش نمی‌فرستند و حساب را تغییر نمی‌دهند.",12,MUTED));
        LinearLayout c=card("آخرین وضعیت حساب دمو");JSONObject snap=obj(status,"snapshot"),a=obj(snap,"account"),stage=obj(status,"stage"),market=obj(snap,"market");
        LinearLayout first=row();accountTile(first,"اکوییتی حساب",a.optString("equity","—"));accountTile(first,"سرمایهٔ فعال",stage.optString("active_capital","—"));c.addView(first);
        LinearLayout second=row();accountTile(second,"سود و زیان روز",status.optString("daily_pnl","—"));accountTile(second,"سود شناور",status.optString("floating_pnl","—"));c.addView(second);
        if(!previewMode){metric(c,"ارتباط با MT5",healthy()?"متصل به بروکر دمو":"قطع یا داده کهنه",healthy()?GREEN:RED);metric(c,"حساب",a.optString("identity","—"),MUTED);metric(c,"تأخیر دریافت",status.has("latency_ms")?status.optString("latency_ms")+" ms":"—",MUTED);}
        LinearLayout chart=card("طلای جهانی • XAUUSD • "+barsFrame);metric(chart,"خرید / فروش",market.optString("ask","—")+" / "+market.optString("bid","—"),GOLD);
        if(!frame.equals(barsFrame))chart.addView(text("بازهٔ درخواستی "+frame+" هنوز دریافت نشده؛ نمودار قبلی مربوط به "+barsFrame+" است.",12,GOLD));
        LinearLayout frames=row();frames.setLayoutDirection(View.LAYOUT_DIRECTION_LTR);for(String f:new String[]{"1m","3m","5m","15m","1h","4h","1D","1W","1M"}){TextView t=text(f,10,f.equals(frame)?GOLD:MUTED);t.setGravity(Gravity.CENTER);t.setOnClickListener(v->{frame=f;if(previewMode)render();else fetch();});frames.addView(t,new LinearLayout.LayoutParams(0,dp(40),1));}chart.addView(frames);
        if(bars!=null&&bars.length()>0){chart.addView(new MarketChart(this,bars),new LinearLayout.LayoutParams(-1,dp(200)));chart.addView(text("آخرین کندل می‌تواند در حال تشکیل باشد.",11,MUTED));}else{LinearLayout empty=col();empty.setGravity(Gravity.CENTER);empty.setPadding(dp(12),dp(16),dp(12),dp(16));empty.setBackground(shape(BG));TextView message=text("دادهٔ کندلی هنوز دریافت نشده است.",13,MUTED);message.setGravity(Gravity.CENTER);empty.addView(message);if(previewMode){TextView note=text("نمودار ساختگی نمایش داده نمی‌شود.",11,MUTED);note.setGravity(Gravity.CENTER);empty.addView(note);}chart.addView(empty,new LinearLayout.LayoutParams(-1,dp(100)));}
        LinearLayout d=card("علت تصمیم موتور");JSONObject decision=obj(status,"decision");String action=decision.optString("action","");d.addView(text(action.equals("no_trade")?"معامله نکن":action.equals("candidate_for_risk_check")?"در انتظار بررسی مستقل ریسک":"در انتظار داده",17,GOLD));JSONArray reasons=decision.optJSONArray("reasons");if(reasons!=null)for(int i=0;i<reasons.length();i++)d.addView(text("• "+reason(reasons.optString(i)),13,MUTED));
        d.addView(text("صدور سفارش خودکار به عبور از آزمون پژوهشی و فعال‌سازی نسخه مجاز نیاز دارد.",12,MUTED));
    }
    private void risk(){
        JSONObject s=obj(status,"stage");LinearLayout c=card("سرمایه و هدف سود");
        metric(c,"اکوییتی آغاز روز",s.optString("day_start_equity","—")+" USD",TEXT);metric(c,"هدف اکوییتی روز",status.optString("daily_target_equity","—")+" USD",GOLD);
        metric(c,"سرمایه فعال",s.optString("active_capital","—")+" USD",GOLD);metric(c,"مرحله",s.has("stage_index")?String.valueOf(s.optInt("stage_index")+1):"—",TEXT);
        c.addView(text("پس از زیان ۳٪ سرمایه فعال هر مرحله، سهم فعال نصف می‌شود. سرمایه فعال با سود خودکار افزایش نمی‌یابد.",14,MUTED));
        c.addView(text("با رسیدن به هدف سود روزانه، سفارش جدید متوقف می‌شود؛ معاملات باز با حد سود و حد ضرر خود باقی می‌مانند.",13,MUTED));
        LinearLayout controls=card("فرمان‌های مالک");metric(controls,"سفارش جدید",status.optBoolean("paused",true)?"متوقف":"فعال",GOLD);
        button(controls,"توقف سفارش جدید",true,()->command("pause",new JSONObject()));
        button(controls,"تطبیق وضعیت با بروکر",false,()->command("reconcile",new JSONObject()));
        Button resume=button(controls,"اجازه سفارش جدید دمو",false,()->command("resume",new JSONObject()));resume.setEnabled(healthy());
        controls.addView(text("هر فرمان حساس به کد یک‌بارمصرف نیاز دارد. این کنترل معاملات باز را نمی‌بندد.",12,MUTED));
    }
    private void trades(){
        JSONArray positions=status.optJSONArray("positions");LinearLayout c=card("معاملات باز حساب دمو");
        if(!healthy())c.addView(text("وضعیت قابل اتکای حساب در دسترس نیست.",14,RED));
        if(positions==null||positions.length()==0)c.addView(text("معامله باز گزارش نشده است.",14,MUTED));
        else for(int i=0;i<positions.length();i++){JSONObject p=positions.optJSONObject(i);if(p==null)continue;c.addView(text(p.optString("symbol")+" • "+(p.optInt("type")==0?"خرید":"فروش")+" • "+p.optString("volume"),16,GOLD));metric(c,"سود شناور",p.optString("profit")+" USD",TEXT);metric(c,"حد ضرر / حد سود",p.optString("sl")+" / "+p.optString("tp"),MUTED);}
        Button order=button(c,"ثبت سفارش آزمایشی دمو",true,this::orderForm);order.setEnabled(healthy());
        Button close=button(c,"بستن معاملات طلای حساب دمو",false,()->new AlertDialog.Builder(this).setTitle("بستن معاملات دمو")
            .setMessage("تمام معاملات باز نماد طلای تنظیم‌شده بسته می‌شوند؛ سفارش‌های معلق لغو نمی‌شوند. تأیید می‌کنی؟")
            .setPositiveButton("ادامه",(d,w)->{try{JSONObject b=new JSONObject();b.put("confirmation","CLOSE DEMO POSITIONS");command("close_all",b);}catch(Exception ignored){}}).setNegativeButton("انصراف",null).show());close.setEnabled(healthy());
    }
    private void orderForm(){
        LinearLayout v=col();v.setPadding(dp(18),0,dp(18),0);v.setBackgroundColor(PANEL);
        EditText side=input(v,"buy یا sell",false),volume=input(v,"حجم، مثلاً 0.01",false),sl=input(v,"قیمت حد ضرر اجباری",false),tp=input(v,"قیمت حد سود",false);
        new AlertDialog.Builder(this).setTitle("سفارش حساب دمو").setView(v).setPositiveButton("بررسی و تأیید",(d,w)->{
            try{JSONObject p=new JSONObject();p.put("side",side.getText().toString().trim());p.put("volume",volume.getText().toString().trim());p.put("stop_loss",sl.getText().toString().trim());p.put("take_profit",tp.getText().toString().trim());command("demo_order",p);}catch(Exception e){toast("اطلاعات سفارش معتبر نیست.");}
        }).setNegativeButton("انصراف",null).show();
    }
    private void logs(){
        // Shared observation-only calendar payload; no order action or new fetch.
        JSONObject calendar=obj(research,"amin_calendar_report");
        JSONObject intelligence=obj(calendar,"calendar_intelligence");
        LinearLayout calendarCard=card("★ تقویم اقتصادی امین — بازنگری شواهد");
        calendarCard.addView(text(!healthy()?"گزارش ذخیره‌شده تازه تأیید نشده است؛ برای وضعیت فعلی استفاده نشود.":intelligence.has("rendered_fa")?intelligence.optString("rendered_fa"):
            "گزارش هوشمند تقویم در پاسخ فعلی موجود نیست؛ وضعیت، سناریو و دقت تازه تأیید نشده است.",13,MUTED));
        LinearLayout sourceCard=card("اخبار و داده‌های مکمل");sourceCard.addView(text("منابع رسمی، اطلاعات تکمیلی می‌دهند؛ پوشش کامل تقویم خبر را تضمین نمی‌کنند.",12,MUTED));
        JSONArray feeds=sources.optJSONArray("sources");if(feeds!=null)for(int i=0;i<feeds.length();i++){
            JSONObject feed=feeds.optJSONObject(i);if(feed==null)continue;
            String sourceId=feed.optString("id");String label=sourceId.equals("fed-news")?"فدرال رزرو":sourceId.equals("bls-news")?"آمار آمریکا":sourceId.equals("bls-calendar")?"تقویم BLS":sourceId.equals("us-10y")?"بازده اوراق ۱۰ ساله":"پیشنهادهای پژوهش";
            metric(sourceCard,label,feed.optString("status").equals("usable_supplemental")?"دریافت شده":"در دسترس نیست",MUTED);
            JSONObject data=obj(feed,"data");JSONArray headlines=data.optJSONArray("records");
            if(headlines!=null&&!sourceId.equals("research-discovery"))for(int j=0;j<Math.min(2,headlines.length());j++){JSONObject h=headlines.optJSONObject(j);if(h!=null)sourceCard.addView(text(h.optString("title"),12,TEXT));}
            JSONObject latest=data.optJSONObject("latest");if(latest!=null)sourceCard.addView(text(latest.optString("observation_date")+" • "+latest.optString("value")+" %",12,GOLD));
        }
        LinearLayout c=card("گزارش عملکرد ثبت‌شده بروکر");metric(c,"سود بسته‌شده خالص",report.optString("realized_net_usd","—")+" USD",GOLD);metric(c,"کمیسیون و کارمزد",report.optString("recorded_commission_and_fees","—")+" USD",MUTED);
        c.addView(text("واریز و برداشت از سود معاملاتی جدا محاسبه می‌شوند. نرخ برد تا انتساب کامل معاملات گزارش نمی‌شود.",12,MUTED));
        LinearLayout r=card("پژوهش کنترل‌شده");r.addView(text(research.optBoolean("demo_review_eligible",false)?"نامزد پژوهشی برای بررسی مالک آماده است":"شواهد کافی برای تأیید نسخه وجود ندارد",14,GOLD));r.addView(text("ارتقای خودکار به معاملات واقعی مجاز نیست.",12,MUTED));
        JSONObject oos=obj(research,"out_of_sample");metric(r,"معاملات خارج‌ازنمونه",oos.optString("trades","—"),MUTED);metric(r,"سود خالص خارج‌ازنمونه",oos.optString("net_usd","—"),GOLD);
        if(research.optBoolean("demo_review_eligible",false))button(r,"تأیید این نسخه برای آزمایش خودکار دمو",false,()->{
            try{JSONObject p=new JSONObject();p.put("strategy_sha256",research.getString("strategy_sha256"));command("approve_demo_strategy",p);}catch(Exception e){toast("نسخه پژوهشی مشخص نیست.");}
        });
        button(r,"غیرفعال‌کردن راهبرد خودکار دمو",false,()->command("disable_demo_strategy",new JSONObject()));
        if(commands!=null)for(int i=0;i<Math.min(8,commands.length());i++){JSONObject cmd=commands.optJSONObject(i);if(cmd!=null){LinearLayout item=card("فرمان "+cmd.optString("action"));item.addView(text(cmd.optString("status")+" • "+cmd.optString("result"),12,MUTED));}}
        if(events!=null)for(int i=0;i<Math.min(20,events.length());i++){JSONObject e=events.optJSONObject(i);if(e!=null){LinearLayout item=card(e.optString("kind"));item.addView(text(e.optString("utc"),11,MUTED));}}
    }
    private void strategyReview(){
        LinearLayout intro=card("★ ۱۳ — بررسی راهبردها • تازه");
        intro.addView(text("رنگ زرد: بخش تازهٔ نسخهٔ موبایل. این صفحه فقط بررسی است؛ مجوز معامله یا تأیید سودآوری صادر نمی‌کند.",14,GOLD));
        intro.addView(text(healthy()?"دادهٔ حساب تازه دریافت شده":"بدون اتصال زندهٔ تأییدشده؛ نتیجهٔ تازه در دسترس نیست",13,healthy()?GREEN:RED));
        String[] details={
            "مقایسهٔ با/بدون سنتیمنت به نتیجهٔ مستقل نیاز دارد؛ گزارش سایه‌ای محلی ویندوز روی گوشی در دسترس نیست.",
            "تفکیک سشن/رژیم در گزارش پژوهش: "+(research.has("by_session")?"موجود؛ اعتبار نتیجه جداگانه بررسی شود":"منتظر پژوهش"),
            "سود خالص تحقق‌یافته: "+report.optString("realized_net_usd","—")+"؛ افت پژوهش: "+obj(research,"out_of_sample").optString("max_drawdown_usd","—")+". آمار زیان متوالی هنوز کامل متصل نشده.",
            "این صفحه سفارش سایه‌ای نمی‌فرستد؛ دادهٔ زندهٔ ناظر سایه‌ای در API فعلی گوشی ارائه نشده است.",
            "سیاست ریسک: "+obj(status,"active_risk_policy").optString("max_order_risk_fraction","—")+"؛ هدف روزانه اجازهٔ حذف محافظ‌ها نیست.",
            "رفت‌وبرگشت بروکر: "+status.optString("latency_ms","—")+" ms؛ تحلیل کامل کیفیت اجرا هنوز متصل نیست.",
            "ریسک مجموع تا حدضرر: "+obj(obj(status,"snapshot"),"exposure").optString("risk_to_stops","—")+"؛ مدل همبستگی چندنمادی تأیید نشده.",
            "حد افت روزانه: "+obj(status,"active_risk_policy").optString("max_daily_drawdown","—")+"؛ پایش آماری افت مدل هنوز کامل نشده.",
            "علت جاری: "+obj(status,"decision").optString("reasons","نامعلوم")+"؛ بررسی نتیجهٔ تمام فرصت‌ها کامل نشده.",
            "فشار هزینه: "+(research.has("stress")?"گزارش موجود":"منتظر پژوهش")+"؛ حساسیت کامل تنظیمات و زمان ورود تأیید نشده.",
            "واجد بررسی دمو: "+research.optString("demo_review_eligible","نامعلوم")+"؛ قبولی به شواهد مستقل و حداقل نمونه نیاز دارد.",
            "گزارش حساب، جای صورتحساب مستقل بروکر نیست؛ تطبیق مستقل مالی هنوز متصل نشده.",
            "جداسازی دادهٔ انتخاب از ارزیابی نهایی: "+(research.has("selection_uses_holdout")&&!research.optBoolean("selection_uses_holdout",true)?"در گزارش ثبت شده":"منتظر شاهد")+"؛ صحت پیش‌بینی آینده تضمین نمی‌شود."
        };
        for(int i=0;i<StrategyReview.TITLES.length;i++){
            LinearLayout c=card("★ ر"+(i+1)+" — "+StrategyReview.TITLES[i]);
            c.addView(text(StrategyReview.state(i,healthy()),13,GOLD));
            c.addView(text(healthy()?details[i]:"ورودی تازهٔ تأییدشده موجود نیست. "+StrategyReview.LIMITS[i],13,MUTED));
        }
    }
    private void settings(){
        LinearLayout c=card("اتصال امن");metric(c,"سرور",connection.optString("url"),MUTED);c.addView(text("هویت سرور با اثر انگشت گواهی بررسی می‌شود. نشست‌ها کوتاه‌مدت و قابل ابطال‌اند.",13,MUTED));
        button(c,"به‌روزرسانی وضعیت",true,this::fetch);button(c,"شبیه‌ساز آفلاین",false,()->startActivity(new Intent(this,MainActivity.class)));
        LinearLayout monitoring=card("اعلان‌های حساب");
        monitoring.addView(text("پایش فعال با اعلان دائمی، هشدارها را هر ۱۵ ثانیه بررسی می‌کند. محدودیت‌های باتری و زمان اجرای اندروید اعمال می‌شوند؛ بررسی دوره‌ای پس‌زمینه نیز به‌صورت کمکی زمان‌بندی می‌شود.",13,MUTED));
        button(monitoring,"فعال‌کردن پایش و اعلان‌ها",true,this::enableMonitoring);
        button(monitoring,"توقف پایش گوشی",false,this::disableMonitoring);
        LinearLayout recovery=card("پشتیبان و بازیابی");
        JSONObject backup=obj(status,"backup");metric(recovery,"بازیابی پشتیبان اخیر",backup.optBoolean("restore_verified",false)?"بررسی شده":"تأیید نشده",GOLD);
        metric(recovery,"نسخه خارج از میزبان",backup.optBoolean("off_host_verified",false)?"تأیید شده":"تأیید نشده",MUTED);
        if(obj(status,"recovery").optBoolean("review_required",false)){
            recovery.addView(text("این سرور از پشتیبان بازیابی شده است. تطبیق با بروکر و بررسی مالک لازم است؛ سفارش جدید در روز بازیابی متوقف می‌ماند.",13,GOLD));
            button(recovery,"تأیید بررسی بازیابی و تطبیق دمو",false,()->{
                try{JSONObject p=new JSONObject();p.put("confirmation","RECONCILED DEMO RESTORE");command("acknowledge_restore",p);}catch(Exception e){toast("فرمان بازیابی معتبر نیست.");}
            });
        }
        if(getSharedPreferences("monitor",MODE_PRIVATE).getBoolean("os_budget_exhausted",false))monitoring.addView(text("اندروید پایش مداوم را متوقف کرده است. بررسی دوره‌ای ممکن است با تأخیر اجرا شود؛ می‌توانی از داخل برنامه پایش فعال را دوباره آغاز کنی.",12,GOLD));
        button(c,"خروج و ابطال اتصال این گوشی",false,()->{
            if(busy)return;busy=true;final JSONObject cfg=connection;
            network.execute(()->{try{ConnectionSession.logout(this);handler.post(()->{disableMonitoring();busy=false;connection=new JSONObject();clearViewState();error="";render();});}
            catch(Exception e){handler.post(()->{busy=false;error="ابطال نشست تأیید نشد: "+e.getMessage();render();});}});
        });
        LinearLayout about=card("نسخه 0.4.3.10 • پیش‌نمایش کابین");about.addView(text("کابین و کنترل‌های این ساخت در حال تکمیل‌اند؛ اجرای مستقل و برابری کامل با ویندوز هنوز تأیید نشده است.",13,MUTED));
    }
    private void command(String action,JSONObject payload){
        if(!healthy()){toast("ابتدا دریافت تازه و اتصال معتبر لازم است؛ فرمان ذخیره یا صف‌بندی نشد.");return;}
        EditText otp=new EditText(this);otp.setHint("کد ۶ رقمی");otp.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        new AlertDialog.Builder(this).setTitle("تأیید فرمان: "+action).setMessage("کد برنامه احراز هویت را وارد کن. هر کد فقط برای یک فرمان مصرف می‌شود.").setView(otp)
            .setPositiveButton("ارسال",(d,w)->{
                if(busy){toast("دریافت وضعیت در جریان است؛ چند لحظه بعد دوباره اقدام کن.");return;}
                if(!healthy()){toast("داده هنگام تأیید کهنه شد؛ فرمان ارسال نشد.");return;}
                try{JSONObject b=new JSONObject();String id=UUID.randomUUID().toString();b.put("request_id",id);b.put("action",action);b.put("payload",payload);b.put("otp",otp.getText().toString());b.put("issued_at",System.currentTimeMillis()/1000.0);
                    busy=true;final JSONObject cfg=connection;
                    network.execute(()->{try{JSONObject result=ConnectionSession.call(this,"POST","/v1/commands",b);handler.post(()->{busy=false;toast("فرمان ثبت شد: "+result.optString("status"));fetch();});}
                    catch(Exception e){handler.post(()->{busy=false;error="نتیجه ارسال را در گزارش فرمان‌ها بررسی کن: "+e.getMessage();render();});}});
                }catch(Exception e){toast("فرمان معتبر نیست.");}
            }).setNegativeButton("انصراف",null).show();
    }
    private void enableMonitoring(){
        if(android.os.Build.VERSION.SDK_INT>=33&&checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},701);return;}
        if(!((android.app.NotificationManager)getSystemService(NOTIFICATION_SERVICE)).areNotificationsEnabled()){toast("اجازه اعلان‌ها را در تنظیمات گوشی فعال کن.");return;}
        getSharedPreferences("monitor",MODE_PRIVATE).edit().putBoolean("enabled",true).putBoolean("os_budget_exhausted",false).commit();
        AlertJobService.enable(this);startForegroundService(new Intent(this,MonitoringService.class));toast("پایش گوشی فعال شد.");
    }
    private void disableMonitoring(){
        getSharedPreferences("monitor",MODE_PRIVATE).edit().putBoolean("enabled",false).commit();AlertJobService.disable(this);stopService(new Intent(this,MonitoringService.class));
    }
    public void onRequestPermissionsResult(int request,String[] permissions,int[] results){
        super.onRequestPermissionsResult(request,permissions,results);if(request==701&&results.length>0&&results[0]==android.content.pm.PackageManager.PERMISSION_GRANTED)enableMonitoring();
    }
}
