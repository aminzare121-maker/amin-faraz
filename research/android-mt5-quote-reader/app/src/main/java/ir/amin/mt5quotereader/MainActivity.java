package ir.amin.mt5quotereader;
import android.app.*;
import android.content.*;
import android.os.*;
import android.provider.Settings;
import android.widget.*;
import android.view.View;
import java.io.*;
public final class MainActivity extends Activity {
 private TextView status;
 private final Handler h=new Handler(Looper.getMainLooper());
 private final Runnable refresh=new Runnable(){public void run(){status.setText((QuoteService.armed?"ثبت روشن":"ثبت خاموش")+"\n"+QuoteService.status);h.postDelayed(this,400);}};
 private void button(LinearLayout l,String text,View.OnClickListener listener){Button b=new Button(this);b.setText(text);b.setOnClickListener(listener);l.addView(b);}
 @Override public void onCreate(Bundle state){super.onCreate(state);
  LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.VERTICAL);l.setPadding(24,24,24,24);
  ScrollView s=new ScrollView(this);s.addView(l);setContentView(s);
  TextView t=new TextView(this);t.setText("واسط قیمت امین — نسخه آزمایشی\nفقط XAUUSD.st روی صفحه قیمت‌های MT5. با مجوز دسترسی‌پذیری، فقط جفت قیمت دارای برچسب معتبر ثبت می‌شود. این برنامه تاریخچه بروکر را نمی‌خواند و تیک کامل تولید نمی‌کند. زمان ثبت، زمان گوشی است. بدون اینترنت، بدون رمز و بدون معامله.");t.setTextSize(17);l.addView(t);
  status=new TextView(this);status.setTextSize(18);l.addView(status);
  button(l,"۱. فعال‌سازی مجوز دسترسی‌پذیری",v->startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
  button(l,"۲. شروع ثبت دستی",v->{
   if(!QuoteService.connected){Toast.makeText(this,"ابتدا سرویس واسط قیمت امین را فعال کن",Toast.LENGTH_LONG).show();return;}
   QuoteService.armed=true;QuoteService.count=0;QuoteService.status="صفحه قیمت‌های MT5 را باز کن";
  });
  button(l,"توقف ثبت",v->{QuoteService.armed=false;QuoteService.status="متوقف شد";});
  button(l,"باز کردن متاتریدر",v->{Intent i=getPackageManager().getLaunchIntentForPackage(QuoteService.PKG);if(i!=null)startActivity(i);else Toast.makeText(this,"MT5 را از صفحه گوشی باز کن",Toast.LENGTH_SHORT).show();});
  button(l,"ذخیره خروجی CSV",v->{QuoteService.armed=false;File f=new File(getFilesDir(),QuoteService.FILE);if(!f.exists()){Toast.makeText(this,"هنوز قیمتی ثبت نشده",Toast.LENGTH_LONG).show();return;}Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT);i.setType("text/csv");i.addCategory(Intent.CATEGORY_OPENABLE);i.putExtra(Intent.EXTRA_TITLE,"amin_mt5_visible_quotes.csv");startActivityForResult(i,10);});
  button(l,"پاک کردن داده‌های محلی",v->new AlertDialog.Builder(this).setMessage("همه مشاهدات محلی حذف شوند؟").setNegativeButton("خیر",null).setPositiveButton("بله",(a,b)->{QuoteService.armed=false;deleteFile(QuoteService.FILE);QuoteService.count=0;QuoteService.status="فایل محلی پاک شد";}).show());
 }
 @Override protected void onResume(){super.onResume();h.removeCallbacks(refresh);h.post(refresh);}
 @Override protected void onPause(){h.removeCallbacks(refresh);super.onPause();}
 @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);
  if(request==10&&result==RESULT_OK&&data!=null&&data.getData()!=null){
   try(InputStream in=new FileInputStream(new File(getFilesDir(),QuoteService.FILE));OutputStream out=getContentResolver().openOutputStream(data.getData(),"wt")){
    if(out==null)throw new IOException();byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);
    Toast.makeText(this,"فایل ذخیره شد",Toast.LENGTH_LONG).show();
   }catch(IOException e){Toast.makeText(this,"ذخیره ناموفق بود",Toast.LENGTH_LONG).show();}
  }
 }
}
