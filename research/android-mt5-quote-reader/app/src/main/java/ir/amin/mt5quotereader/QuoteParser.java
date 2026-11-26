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
  Field(String id,String text,String desc){this.id=id==null?"":id;this.text=text==null?"":text;this.desc=desc==null?"":desc;}
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
