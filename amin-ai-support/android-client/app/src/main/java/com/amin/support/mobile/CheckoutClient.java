package com.amin.support.mobile;

import org.json.JSONObject;
import java.net.URL;
import java.net.HttpURLConnection;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;

/** Only the already scoped customer key, HTTPS, no redirects, no card data. */
public final class CheckoutClient {
    private final String host,key;
    public CheckoutClient(String endpoint,String scopedKey){
        host=SupportEndpoint.normalize(endpoint);
        key=SupportEndpoint.validateToken(scopedKey);
    }
    public JSONObject quote()throws Exception{
        return exchange("/v1/quote",new JSONObject().put("product","amin-ai-monthly").put("months",1),"");
    }
    public JSONObject order(String invoice)throws Exception{
        if(!CheckoutPolicy.invoice(invoice))throw new IllegalArgumentException("فاکتور نامعتبر است.");
        return exchange("/v1/order",new JSONObject().put("invoice_id",invoice),"");
    }
    public JSONObject claim(String invoice,String tx)throws Exception{
        if(!CheckoutPolicy.invoice(invoice)||!CheckoutPolicy.tx(tx))
            throw new IllegalArgumentException("فاکتور یا شناسه تراکنش نامعتبر است.");
        return exchange("/v1/claim",new JSONObject().put("invoice_id",invoice).put("tx_hash",tx.toLowerCase(java.util.Locale.ROOT)),"");
    }
    public JSONObject status(String invoice)throws Exception{
        if(!CheckoutPolicy.invoice(invoice))throw new IllegalArgumentException("فاکتور نامعتبر است.");
        return exchange("/v1/invoice",null,"?id="+invoice);
    }
    private JSONObject exchange(String route,JSONObject input,String query)throws Exception{
        HttpsURLConnection c=(HttpsURLConnection)new URL(CheckoutPolicy.url(host,route)+query).openConnection();
        c.setConnectTimeout(12000);
        c.setReadTimeout(45000);
        c.setInstanceFollowRedirects(false);
        c.setUseCaches(false);
        c.setRequestProperty("Authorization","Bearer "+key);
        c.setRequestProperty("Accept","application/json");
        c.setRequestProperty("Cache-Control","no-store");
        try{
            if(input!=null){
                byte[] data=input.toString().getBytes(StandardCharsets.UTF_8);
                if(data.length>5000)throw new IllegalArgumentException("بدنه درخواست طولانی است.");
                c.setRequestMethod("POST");
                c.setRequestProperty("Content-Type","application/json; charset=utf-8");
                c.setDoOutput(true);
                c.setFixedLengthStreamingMode(data.length);
                try(OutputStream out=c.getOutputStream()){out.write(data);}
            }else c.setRequestMethod("GET");
            int code=c.getResponseCode();
            if(code>=300&&code<400)throw new IllegalStateException("تغییر مسیر سرور پرداخت مسدود است.");
            if(code!=200)throw new IllegalStateException("پاسخ سرویس فروش ناموفق است؛ کد "+code);
            if(c.getContentType()==null||!c.getContentType().toLowerCase(java.util.Locale.ROOT).contains("application/json"))
                throw new IllegalStateException("پاسخ معتبر JSON دریافت نشد.");
            try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] buf=new byte[2048];int n;
                while((n=in.read(buf))!=-1){
                    if(out.size()+n>32000)throw new IllegalStateException("پاسخ بزرگ‌تر از حد مجاز است.");
                    out.write(buf,0,n);
                }
                return new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8));
            }
        }finally{c.disconnect();}
    }
}
