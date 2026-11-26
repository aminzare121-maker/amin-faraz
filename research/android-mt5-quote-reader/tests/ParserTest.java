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
  System.out.println("8 parser checks passed; synthetic fixtures only");
 }
}
