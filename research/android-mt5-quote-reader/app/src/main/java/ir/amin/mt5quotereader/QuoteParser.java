package ir.amin.mt5quotereader;
import java.math.BigDecimal;
import java.util.*;
import java.util.regex.*;
final class QuoteParser {
 static final String SYMBOL="XAUUSD.st";
 static final Pattern PRICE=Pattern.compile("[0-9]{1,6}\\.[0-9]{1,5}");
 static final Pattern LABELED=Pattern.compile("(?i)^\\s*(bid|ask)\\s*[:=]?\\s*([0-9]{1,6}\\.[0-9]{1,5})\\s*$");
 static final class Field {
  final String id,text,desc;
  final int left,top,right,bottom;
  Field(String id,String text,String desc){this(id,text,desc,0,0,0,0);}
  Field(String id,String text,String desc,int l,int t,int r,int b){this.id=id==null?"":id;this.text=text==null?"":text;this.desc=desc==null?"":desc;left=l;top=t;right=r;bottom=b;}
  boolean positioned(){return right>left&&bottom>top;}
  int cy(){return (top+bottom)/2;}
 }
 static final class Quote {
  final BigDecimal bid,ask;
  Quote(BigDecimal b,BigDecimal a){bid=b;ask=a;}
 }
 static boolean symbol(Field f){return SYMBOL.equals(f.text.trim())||SYMBOL.equals(f.desc.trim());}
 static String label(String id) {
  String s=id.toLowerCase(Locale.ROOT);int slash=s.lastIndexOf('/');s=s.substring(slash+1);
  if(s.equals("bid")||s.equals("bid_price")||s.equals("price_bid")||s.equals("quote_bid")||s.equals("bidprice"))return "bid";
  if(s.equals("ask")||s.equals("ask_price")||s.equals("price_ask")||s.equals("quote_ask")||s.equals("askprice"))return "ask";
  return "";
 }
 static boolean add(Map<String,BigDecimal> m,String k,String raw){
  if(!PRICE.matcher(raw).matches())return false;
  BigDecimal x=new BigDecimal(raw);
  if(x.signum()<=0)return false;
  BigDecimal old=m.putIfAbsent(k,x);
  return old==null||old.compareTo(x)==0;
 }
 static String normalized(String raw){
  StringBuilder out=new StringBuilder();
  for(int i=0;i<raw.length();i++){
   char c=raw.charAt(i);
   if(c=='\u200e'||c=='\u200f'||c=='\u061c'||c=='\u202a'||c=='\u202b'||c=='\u202c'||c=='\u202d'||c=='\u202e'||c=='\u2066'||c=='\u2067'||c=='\u2068'||c=='\u2069')continue;
   int digit=Character.digit(c,10);
   if(digit>=0)out.append((char)('0'+digit));else if(c=='\u066b')out.append('.');else out.append(c);
  }
  return out.toString().trim();
 }
 static Quote parseVisibleRow(List<Field> fields){
  Quote labeled=parse(fields);
  if(labeled!=null)return labeled;
  if(fields.size()>32||fields.stream().filter(QuoteParser::symbol).count()!=1)return null;
  Field s=fields.stream().filter(QuoteParser::symbol).findFirst().get();
  if(!s.positioned())return null;
  List<Field> candidates=new ArrayList<>();
  List<BigDecimal> prices=new ArrayList<>();
  for(Field f:fields){
   if(symbol(f))continue;
   String a=normalized(f.text),b=normalized(f.desc);
   for(String v:new String[]{a,b}){
    if(v.matches("(?i)^[A-Z]{3,8}(?:[./_-][A-Za-z0-9]{1,12})?$")&&!v.equalsIgnoreCase("bid")&&!v.equalsIgnoreCase("ask"))return null;
   }
   // Never fall back when explicit price labels exist but conflict or are incomplete.
   if(!label(f.id).isEmpty()||LABELED.matcher(a).matches()||LABELED.matcher(b).matches())return null;
   boolean pa=a.matches("[0-9]{3,6}\\.[0-9]{2}"),pb=b.matches("[0-9]{3,6}\\.[0-9]{2}");
   if(!pa&&!pb)continue;
   if(pa&&pb&&!a.equals(b))return null;
   if(!f.positioned())return null;
   // The two quote values are horizontally adjacent, near the symbol's vertical center.
   if(Math.abs(f.cy()-s.cy())>Math.max(s.bottom-s.top,f.bottom-f.top))continue;
   BigDecimal price=new BigDecimal(pa?a:b);
   if(price.signum()<=0)return null;
   candidates.add(f);prices.add(price);
  }
  if(candidates.size()!=2)return null;
  Field a=candidates.get(0),b=candidates.get(1);
  if(Math.abs(a.cy()-b.cy())>Math.max(2,Math.min(a.bottom-a.top,b.bottom-b.top)/2))return null;
  if(!(a.right<=b.left||b.right<=a.left))return null;
  // Require both quote boxes on the same side of the symbol, not a chart or mixed rows.
  if(!((a.right<=s.left&&b.right<=s.left)||(a.left>=s.right&&b.left>=s.right)))return null;
  BigDecimal lo=prices.get(0).min(prices.get(1)),hi=prices.get(0).max(prices.get(1));
  if(hi.compareTo(lo)<=0||hi.subtract(lo).compareTo(new BigDecimal("5.00"))>0)return null;
  return new Quote(lo,hi);
 }
 static Quote parse(List<Field> fields){
  if(fields.size()>32||fields.stream().filter(QuoteParser::symbol).count()!=1)return null;
  Map<String,BigDecimal> m=new HashMap<>();
  for(Field f:fields){
   if(symbol(f))continue;
   for(String s:new String[]{f.text.trim(),f.desc.trim()}){
    if(s.isEmpty())continue;
    // Reject any other visible symbol in the candidate row; do not guess columns.
    if(s.matches("(?i)^[A-Z]{3,8}(?:[./_-][A-Za-z0-9]{1,12})?$")&&!s.equalsIgnoreCase("bid")&&!s.equalsIgnoreCase("ask"))return null;
    Matcher a=LABELED.matcher(s);
    if(a.matches()){
     if(!add(m,a.group(1).toLowerCase(Locale.ROOT),a.group(2)))return null;
    }else if(!label(f.id).isEmpty()&&PRICE.matcher(s).matches()){
     if(!add(m,label(f.id),s))return null;
    }
   }
  }
  BigDecimal b=m.get("bid"),a=m.get("ask");
  return b!=null&&a!=null&&a.compareTo(b)>=0?new Quote(b,a):null;
 }
}
