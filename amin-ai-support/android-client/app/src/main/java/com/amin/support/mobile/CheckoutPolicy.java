package com.amin.support.mobile;

import java.util.regex.Pattern;

/** Customer cannot submit fake receipts as paid; strict untrusted input policy. */
public final class CheckoutPolicy {
    private CheckoutPolicy(){}
    private static final Pattern INVOICE=Pattern.compile("[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}");
    private static final Pattern TX=Pattern.compile("[a-fA-F0-9]{64}");
    private static final Pattern TRON=Pattern.compile("T[1-9A-HJ-NP-Za-km-z]{33}");
    public static boolean invoice(String s){return s!=null&&INVOICE.matcher(s).matches();}
    public static boolean tx(String s){return s!=null&&TX.matcher(s).matches();}
    public static boolean tron(String s){return s!=null&&TRON.matcher(s).matches();}
    public static String url(String host,String route){
        if(!"/v1/quote".equals(route)&&!"/v1/order".equals(route)&&
           !"/v1/claim".equals(route)&&!"/v1/invoice".equals(route))
            throw new IllegalArgumentException("مسیر پرداخت مجاز نیست.");
        return SupportEndpoint.normalize(host)+route;
    }
}
