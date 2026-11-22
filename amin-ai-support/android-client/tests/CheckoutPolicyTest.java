package com.amin.support.mobile;
public final class CheckoutPolicyTest {
    private static void require(boolean b){if(!b)throw new AssertionError("Checkout security policy");}
    public static void main(String[] arg){
        require(CheckoutPolicy.invoice("05d9f2f6-a854-4a99-a73b-7a81fc87e28e"));
        require(!CheckoutPolicy.invoice("../server/files"));
        require(CheckoutPolicy.tx("a".repeat(64)));
        require(!CheckoutPolicy.tx("screenshot.png"));
        require(CheckoutPolicy.tron("T"+"1".repeat(33)));
        require(!CheckoutPolicy.tron("0x"+"a".repeat(40)));
        require(CheckoutPolicy.url("https://billing.example","/v1/quote").equals("https://billing.example/v1/quote"));
        boolean denied=false;
        try{CheckoutPolicy.url("http://billing.example","/v1/claim");}
        catch(IllegalArgumentException e){denied=true;}
        require(denied);
        denied=false;try{CheckoutPolicy.url("https://billing.example","/v1/admin");}
        catch(IllegalArgumentException e){denied=true;}require(denied);
        System.out.println("PASS: separate checkout HTTPS, scoped invoice, tx and crypto address");
    }
}
