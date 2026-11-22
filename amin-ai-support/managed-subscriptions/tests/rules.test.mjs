import test from "node:test";
import assert from "node:assert/strict";
import {
 PRODUCT,combinedPrice,displayUSDT,checkSupplierQuote,checkConfirmation,
 checkProvisioning,validWebhook
} from "../src/rules.mjs";
import worker from "../src/worker.mjs";
const future=Date.now()+300000;
const past=Date.now()-60000;
const supplier={product:PRODUCT,quote_id:"suppq_12345678",cost_microunits:9_250_000,currency:"USDT",
 network:"TRC20",expires_at:new Date(future).toISOString()};
test("bundled owner rent is one final exact value, not a percentage fake",()=>{
  assert.equal(displayUSDT(combinedPrice(9_250_000,1_750_000)),"11");
  assert.equal(displayUSDT(combinedPrice(1_000_001,100_004)),"1.100005");
  assert.throws(()=>combinedPrice(-1,10));
  assert.throws(()=>combinedPrice(Number.MAX_SAFE_INTEGER,10));
});
test("provider quote is rejected if unverified, mismatched or stale",()=>{
  assert.equal(checkSupplierQuote(supplier,PRODUCT).quote_id,supplier.quote_id);
  for (const p of [{currency:"USD"},{product:"another"},
    {cost_microunits:0},{quote_id:"unknown"},{expires_at:new Date(past).toISOString()}])
    assert.throws(()=>checkSupplierQuote({...supplier,...p},PRODUCT),/supplier_quote_unavailable/);
});
const hash="a".repeat(64);
const invoice={id:"order_123456",state:"AWAITING_PAYMENT",payment_tx:hash,
  destination:"TA".padEnd(34,"1"),total_microunits:11_000_000,
  created_at:new Date(Date.now()-360000).toISOString(),
  supplier_quote_id:"suppq_12345678"};
const event={invoice_id:invoice.id,tx_hash:hash,network:"TRC20",asset:"USDT",
  to_address:invoice.destination,amount_microunits:11_000_000,confirmed:true,
  confirmations:28,block_time:new Date().toISOString()};
test("a customer screenshot never confirms money; signed chain event requires amount, address, confirmations",()=>{
  assert.equal(checkConfirmation(invoice,event).verified,true);
  for(const p of [{confirmed:false},{confirmations:5},{amount_microunits:10_000_000},
    {to_address:"TWrong"},{tx_hash:"b".repeat(64)},{network:"ERC20"}])
    assert.throws(()=>checkConfirmation(invoice,{...event,...p}),/payment_not_independently_confirmed/);
});
test("supplier-not-confirmed or expired product is never automatically activated",()=>{
  const paid={...invoice,state:"PAYMENT_CONFIRMED"};
  const approved={invoice_id:invoice.id,supplier_quote_id:invoice.supplier_quote_id,
    product:PRODUCT,fulfilled:true,provider_reference:"provider_98765432",
    access_expires_at:new Date(Date.now()+2_592_000_000).toISOString()};
  assert.equal(checkProvisioning(paid,approved).active,true);
  for(const p of [{fulfilled:false},{supplier_quote_id:"wrongquote"},
    {provider_reference:""},
    {access_expires_at:new Date(past).toISOString()}])
    assert.throws(()=>checkProvisioning(paid,{...approved,...p}),/provider_service_not_confirmed/);
});
test("webhook HMAC rejects screenshot, missing secret, stale timestamp and forged signature",async()=>{
  assert.equal(await validWebhook(undefined,"123","{}","a".repeat(64)),false);
  const t=String(Date.now()), body=JSON.stringify(event), key="z".repeat(48);
  const cryptoKey=await crypto.subtle.importKey("raw",new TextEncoder().encode(key),
    {name:"HMAC",hash:"SHA-256"},false,["sign"]);
  const sig=[...new Uint8Array(await crypto.subtle.sign("HMAC",cryptoKey,
    new TextEncoder().encode(t+"."+body)))].map(x=>x.toString(16).padStart(2,"0")).join("");
  assert.equal(await validWebhook(key,t,body,sig),true);
  assert.equal(await validWebhook(key,t,body+"x",sig),false);
  assert.equal(await validWebhook(key,String(Date.now()-600000),body,sig),false);
});
test("without active backend config no quote or payment confirmation is fabricated",async()=>{
  const request=new Request("https://amin.example/v1/quote",{method:"POST",
    headers:{"Content-Type":"application/json",Authorization:"Bearer amin_"+"a".repeat(45)},
    body:JSON.stringify({product:PRODUCT,months:1})});
  const r=await worker.fetch(request,{DB:null,OWNER_RENT_MONTHLY_MICROUSDT:"1000000"});
  assert.equal(r.status,503);
  assert.equal((await r.json()).ok,false);
});
test("public health cannot pretend charging owner Google Pay is automated",async()=>{
  const r=await worker.fetch(new Request("https://amin.example/health"),{});
  const j=await r.json();
  assert.equal(j.automatic_google_pay_charge,false);
  assert.equal(j.payment_reconciliation_ready,false);
  assert.equal(j.destination_verified,false);
});
