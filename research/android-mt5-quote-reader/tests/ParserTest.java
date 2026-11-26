package ir.amin.mt5quotereader;
import java.util.*;
public class ParserTest {
 static QuoteParser.Field f(String id,String text){return new QuoteParser.Field(id,text,"");}
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args){
  var s=f("","XAUUSD.st");
  check(QuoteParser.parse(List.of(s,f("","Bid: 4100.25"),f("","Ask: 4100.45")))!=null);
  check(QuoteParser.parse(List.of(s,f("id/bid","4100.25"),f("id/ask","4100.45")))!=null);
  check(QuoteParser.parse(List.of(s,f("","4100.25"),f("","4100.45")))==null);
  check(QuoteParser.parse(List.of(s,f("","Bid: 4100.45"),f("","Ask: 4100.25")))==null);
  check(QuoteParser.parse(List.of(s,f("","Bid: 4100.25"),f("","Bid: 4101.25"),f("","Ask: 4101.45")))==null);
  check(QuoteParser.parse(List.of(f("","XAUUSD"),f("","Bid: 4100.25"),f("","Ask: 4100.45")))==null);
  check(QuoteParser.parse(List.of(s,f("","EURUSD"),f("","Bid: 4100.25"),f("","Ask: 4100.45")))==null);
  check(QuoteParser.parse(List.of(s,f("","Bid: 0.00"),f("","Ask: 4100.45")))==null);
  var symbol=new QuoteParser.Field("","XAUUSD.st","",548,202,663,225);
  var ask=new QuoteParser.Field("","3572.00","",30,185,140,218);
  var bid=new QuoteParser.Field("","3571.64","",160,185,273,218);
  var quote=QuoteParser.parseVisibleRow(List.of(symbol,ask,bid,f("","H: 3607.01"),f("","L: 3551.23"),f("","36")));
  check(quote!=null&&quote.bid.toPlainString().equals("3571.64")&&quote.ask.toPlainString().equals("3572.00"));
  check(QuoteParser.parseVisibleRow(List.of(symbol,bid,ask,f("","EURUSD.st")))==null);
  check(QuoteParser.parseVisibleRow(List.of(symbol,bid,ask,new QuoteParser.Field("","3571.80","",285,185,370,218)))==null);
  check(QuoteParser.parseVisibleRow(List.of(symbol,bid,new QuoteParser.Field("","3572.00","",30,305,140,338)))==null);
  check(QuoteParser.parseVisibleRow(List.of(symbol,bid,new QuoteParser.Field("","۳۵۷۲٫۰۰","",30,185,140,218)))!=null);
  check(QuoteParser.parseVisibleRow(List.of(symbol,bid,new QuoteParser.Field("","3580.00","",30,185,140,218)))==null);
  check(QuoteParser.parseVisibleRow(List.of(symbol,bid,ask,f("","Bid: 3572.00")))==null);
  System.out.println("15 parser checks passed; synthetic fixtures including screenshot-derived RTL quote layout");
 }
}
