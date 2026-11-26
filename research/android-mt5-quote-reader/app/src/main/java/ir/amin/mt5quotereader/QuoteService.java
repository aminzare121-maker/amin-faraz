package ir.amin.mt5quotereader;
import android.accessibilityservice.AccessibilityService;
import android.app.KeyguardManager;
import android.os.*;
import android.view.accessibility.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
public final class QuoteService extends AccessibilityService {
 static final String PKG="net.metaquotes.metatrader5";
 static final String FILE="observed_quotes.csv";
 static volatile boolean connected=false,armed=false;
 static volatile String status="سرویس هنوز فعال نیست";
 static volatile long count=0;
 private final Handler handler=new Handler(Looper.getMainLooper());
 private String last="";
 private long lastAt=0;
 private final Runnable loop=new Runnable(){public void run(){try{sample();}catch(Exception e){status="خواندن ناموفق؛ داده ثبت نشد";}finally{if(connected)handler.postDelayed(this,250);}}};
 @Override protected void onServiceConnected(){super.onServiceConnected();connected=true;armed=false;status="آماده؛ شروع دستی لازم است";handler.removeCallbacks(loop);handler.post(loop);}
 @Override public void onAccessibilityEvent(AccessibilityEvent event){} // polling is scoped to active MT5 window
 @Override public void onInterrupt(){armed=false;status="متوقف شد";}
 @Override public void onDestroy(){connected=false;armed=false;handler.removeCallbacks(loop);super.onDestroy();}
 private static String str(CharSequence x){return x==null?"":x.toString();}
 private static QuoteParser.Field field(AccessibilityNodeInfo x){return new QuoteParser.Field(x.getViewIdResourceName(),str(x.getText()),str(x.getContentDescription()));}
 private static boolean collect(AccessibilityNodeInfo node,List<QuoteParser.Field> fields,int depth,int[] budget){
  if(node==null)return true;
  if(depth>8||--budget[0]<0)return false;
  if(!node.isVisibleToUser())return true;
  QuoteParser.Field f=field(node);
  if(!f.text.isEmpty()||!f.desc.isEmpty())fields.add(f);
  if(fields.size()>32)return false;
  for(int i=0;i<node.getChildCount();i++){
   AccessibilityNodeInfo c=node.getChild(i);
   if(c!=null){try{if(!collect(c,fields,depth+1,budget))return false;}finally{c.recycle();}}
  }return true;
 }
 private QuoteParser.Quote row(AccessibilityNodeInfo n){
  AccessibilityNodeInfo parent=n.getParent();
  for(int depth=0;depth<3&&parent!=null;depth++){
   AccessibilityNodeInfo next=null;
   try {
    // Do not inspect an entire window as a single quote row.
    next=parent.getParent();
    if(next==null)return null;
    List<QuoteParser.Field> fields=new ArrayList<>();
    if(collect(parent,fields,0,new int[]{64})){
     QuoteParser.Quote q=QuoteParser.parse(fields);
     if(q!=null){next.recycle();return q;}
    }
   }finally{parent.recycle();}
   parent=next;
  }
  if(parent!=null)parent.recycle();
  return null;
 }
 private void sample() throws IOException {
  if(!armed){last="";return;}
  PowerManager pm=getSystemService(PowerManager.class);KeyguardManager km=getSystemService(KeyguardManager.class);
  if(pm==null||!pm.isInteractive()||km==null||km.isKeyguardLocked()){armed=false;status="صفحه خاموش یا قفل شد؛ ثبت متوقف شد";return;}
  AccessibilityNodeInfo root=getRootInActiveWindow();
  if(root==null){status="پنجره قابل خواندن نیست";last="";return;}
  try{
   if(!PKG.equals(str(root.getPackageName()))){status="منتظر صفحه فعال متاتریدر";last="";return;}
   List<AccessibilityNodeInfo> nodes=root.findAccessibilityNodeInfosByText(QuoteParser.SYMBOL);
   if(nodes==null||nodes.isEmpty()){status="نماد XAUUSD.st در صفحه قابل خواندن پیدا نشد";last="";return;}
   QuoteParser.Quote found=null;boolean ambiguous=false;
   try{
    for(AccessibilityNodeInfo node:nodes){
     if(!node.isVisibleToUser()||!QuoteParser.symbol(field(node)))continue;
     QuoteParser.Quote q=row(node);
     if(q!=null){
      if(found!=null&&(found.bid.compareTo(q.bid)!=0||found.ask.compareTo(q.ask)!=0))ambiguous=true;
      found=q;
     }
    }
   }finally{for(AccessibilityNodeInfo node:nodes)node.recycle();}
   if(found==null||ambiguous){status="نماد دیده شد، اما Bid/Ask با برچسب معتبر قابل استخراج نیست";last="";return;}
   String pair=found.bid.toPlainString()+","+found.ask.toPlainString();
   long now=System.currentTimeMillis();
   status="قیمت نمایان: "+pair+" | ثبت‌های این نشست: "+count;
   // Suppress duplicate display observations, not broker ticks.
   if(pair.equals(last)&&now-lastAt<5000)return;
   File f=new File(getFilesDir(),FILE);
   if(f.length()>20L*1024*1024){armed=false;status="سقف فایل؛ خروجی بگیر و پاک کن";return;}
   try(OutputStream out=new FileOutputStream(f,true)){
    if(f.length()==0)out.write("observed_device_epoch_ms,symbol,bid,ask,source\n".getBytes(StandardCharsets.UTF_8));
    out.write((now+","+QuoteParser.SYMBOL+","+pair+",MT5_ANDROID_VISIBLE_UI_NOT_TICK\n").getBytes(StandardCharsets.UTF_8));
   }
   last=pair;lastAt=now;count++;status="قیمت نمایان: "+pair+" | ثبت‌های این نشست: "+count;
  }finally{root.recycle();}
 }
}
