package com.amin.support.mobile;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONObject;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Companion flow. The existing voice/chat functions remain unchanged. */
public final class CheckoutActivity extends Activity {
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final ExecutorService tasks=Executors.newSingleThreadExecutor();
    private EditText host,transaction;
    private TextView status;
    private String invoice="";
    private boolean alive=true;
    private interface NetworkTask{JSONObject run(CheckoutClient api)throws Exception;}
    @Override protected void onCreate(Bundle state){
        super.onCreate(state);
        setTitle("صورتحساب اجاره هوش امین");
        ScrollView scroll=new ScrollView(this);
        LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setLayoutDirection(android.view.View.LAYOUT_DIRECTION_RTL);
        root.setPadding(28,28,28,48);
        scroll.addView(root);
        TextView heading=label("اجاره ماهانه هوش امین",22);
        root.addView(heading);
        root.addView(label("قیمت تأمین‌کننده و اجاره مالک فقط به شکل یک مبلغ نهایی نمایش داده می‌شود. ثبت فیش یا هش به معنی پرداخت قطعی نیست. این مسیر فقط برای نسخه مستقل خارج از Google Play است.",15));
        host=new EditText(this);
        host.setHint("https://billing-host.example");
        host.setSingleLine(true);
        host.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
        host.setText(getPreferences(MODE_PRIVATE).getString("checkout_host",""));
        root.addView(host);
        Button quote=button("استعلام قیمت نهایی یک ماه",root);
        quote.setOnClickListener(v->runNetwork(api->api.quote(),"price"));
        Button order=button("نمایش آدرس پرداخت تأییدشده",root);
        order.setOnClickListener(v->{
            if(!CheckoutPolicy.invoice(invoice)){message("ابتدا قیمت معتبر دریافت کن.");return;}
            runNetwork(api->api.order(invoice),"order");
        });
        transaction=new EditText(this);
        transaction.setSingleLine(true);
        transaction.setHint("هش تراکنش TRC20 (۶۴ رقم)");
        root.addView(transaction);
        Button claim=button("ثبت تراکنش برای تطبیق با واریز واقعی",root);
        claim.setOnClickListener(v->{
            String tx=transaction.getText().toString().trim();
            if(!CheckoutPolicy.invoice(invoice)||!CheckoutPolicy.tx(tx)){
                message("فاکتور یا شناسه تراکنش نامعتبر است.");return;
            }
            runNetwork(api->api.claim(invoice,tx),"claim");
        });
        Button refresh=button("پیگیری وضعیت پرداخت و شارژ واقعی",root);
        refresh.setOnClickListener(v->{
            if(!CheckoutPolicy.invoice(invoice)){message("فاکتوری موجود نیست.");return;}
            runNetwork(api->api.status(invoice),"status");
        });
        status=label("هنوز فاکتوری صادر نشده است.",15);
        status.setTextIsSelectable(true);
        root.addView(status);
        invoice=getPreferences(MODE_PRIVATE).getString("checkout_invoice","");
        setContentView(scroll);
    }
    private Button button(String value,LinearLayout root){
        Button b=new Button(this);b.setAllCaps(false);b.setText(value);root.addView(b);return b;
    }
    private TextView label(String value,int font){
        TextView t=new TextView(this);
        t.setText(value);t.setTextSize(font);
        t.setGravity(Gravity.RIGHT);
        t.setPadding(2,10,2,10);return t;
    }
    private void message(String s){if(alive&&status!=null)status.setText(s);}
    private void runNetwork(NetworkTask task,String action){
        final String endpoint=host.getText().toString().trim();
        message("در حال بررسی با سرور معتبر ...");
        tasks.execute(()->{
            try{
                String scoped=TokenVault.token(this);
                CheckoutClient client=new CheckoutClient(endpoint,scoped);
                JSONObject response=task.run(client);
                ui.post(()->{
                    if(!alive)return;
                    getPreferences(MODE_PRIVATE).edit().putString("checkout_host",endpoint).apply();
                    switch(action){
                        case "price":
                            String id=response.optString("invoice_id");
                            if(!CheckoutPolicy.invoice(id)){message("فاکتور معتبر از سرور دریافت نشد.");return;}
                            invoice=id;
                            getPreferences(MODE_PRIVATE).edit().putString("checkout_invoice",id).apply();
                            message("مبلغ نهایی: "+response.optString("total_amount")+" USDT\nاعتبار تا: "+
                                response.optString("valid_until")+"\nشماره فاکتور: "+id);
                            break;
                        case "order":
                            String address=response.optString("address");
                            if(!CheckoutPolicy.tron(address)){message("آدرس پرداخت معتبر نیست؛ وجه ارسال نکن.");return;}
                            message("پرداخت: "+response.optString("total_amount")+" USDT\nشبکه: TRC20\nمقصد: "+address+
                                "\nدر صورت نداشتن تأیید صرافی بابت واریز شخص ثالث، وجهی ارسال نکن.");
                            break;
                        case "claim":
                            message("هش ارسال شد؛ اشتراک هنوز فعال نیست.\nمنتظر مشاهده و تأیید مستقل وصول پول می‌ماند.");
                            break;
                        case "status":
                            message(response.optBoolean("active",false)
                                ? "اشتراک تأیید شده و فعال است تا: "+response.optString("expires_at")
                                : "اشتراک فعال نیست. مرحله فعلی: "+response.optString("state"));
                            break;
                    }
                });
            }catch(Exception e){ui.post(()->message("فرآیند متوقف شد؛ هیچ واریز یا شارژی تأیید نشد. "+e.getMessage()));}
        });
    }
    @Override protected void onDestroy(){alive=false;tasks.shutdownNow();super.onDestroy();}
}
