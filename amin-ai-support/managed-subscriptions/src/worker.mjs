import {
 PRODUCT,ASSET,NETWORK,RX_TOKEN,RX_TX,QUOTE_TTL_MS,GateError,
 combinedPrice,displayUSDT,checkSupplierQuote,checkConfirmation,
 checkProvisioning,sha256,validWebhook
} from "./rules.mjs";
import {reconcileDue} from "./tron-watch.mjs";
const OWNER_CONSOLE = `<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مدیریت اجارهٔ هوش امین</title><style>body{font:16px Tahoma,Arial;background:#f3f5f9;color:#223;max-width:660px;margin:auto;padding:22px;line-height:1.8}section{background:white;border:1px solid #ddd;border-radius:12px;padding:17px;margin:14px 0}input,button{box-sizing:border-box;padding:13px;width:100%;margin:6px 0;font:inherit}button{background:#1c528d;color:white;border:0;border-radius:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#444}</style><h2>مدیریت اجارهٔ هوش امین</h2><section><p>فقط مالک. کلید مدیر فقط در حافظه همین صفحه باقی می‌ماند و ذخیره نمی‌شود.</p><input type="password" id="secret" autocomplete="off" placeholder="کلید خصوصی مدیر"><input type="text" id="rent" inputmode="decimal" placeholder="اجاره ماهانه، مثلاً 12.50 تتر"><button id="save">ذخیره مبلغ اجاره برای فاکتورهای بعدی</button><button id="load">نمایش اجاره فعلی</button><button id="queue">سفارش‌های دارای وصول تأییدشده که شارژ نشده‌اند</button><button id="clear">پاک‌کردن کلید از این صفحه</button><pre id="out">هنوز درخواستی ارسال نشده است.</pre></section><small>رسید مشتری به‌تنهایی پرداخت واقعی نیست. Google Pay از این صفحه به‌طور خودکار شارژ نمی‌شود؛ فعال‌سازی اشتراک فقط با تأیید واقعی تأمین‌کننده است.</small><script>
const el=id=>document.getElementById(id);
async function call(path,method,body){
 const headers={'Authorization':'Bearer '+el('secret').value,'Accept':'application/json'};
 if(body)headers['Content-Type']='application/json';
 const response=await fetch(path,{method,headers,body:body?JSON.stringify(body):undefined,cache:'no-store'});
 const data=await response.json();
 if(!response.ok)throw Error('درخواست رد شد: '+(data.error||response.status));
 return data;
}
el('save').onclick=async()=>{try{const d=await call('/v1/owner/rent','POST',{monthly_rent_usdt:el('rent').value.trim()});el('out').textContent=d.saved?'اجاره جدید ثبت شد: '+d.monthly_rent_usdt+' USDT. فقط برای فاکتورهای بعدی.':'ثبت انجام نشد';}catch(e){el('out').textContent=e.message;}};
el('load').onclick=async()=>{try{const d=await call('/v1/owner/rent','GET');el('out').textContent='اجاره فعلی: '+d.monthly_rent_usdt+' USDT';}catch(e){el('out').textContent=e.message;}};
el('queue').onclick=async()=>{try{const d=await call('/v1/owner/queue','GET');el('out').textContent=JSON.stringify(d.awaiting_owner_topup,null,2);if(!d.awaiting_owner_topup?.length)el('out').textContent='سفارش منتظر شارژ وجود ندارد.';}catch(e){el('out').textContent=e.message;}};
el('clear').onclick=()=>{el('secret').value='';el('out').textContent='کلید از این صفحه پاک شد.'};
</script></html>`;

const HEADERS={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer"};
const json=(data,status=200)=>Response.json(data,{status,headers:HEADERS});
const denied=(code,status=400)=>json({ok:false,error:code},status);
const unique=()=>crypto.randomUUID();
function isHttpsAddress(address){
  try { const u=new URL(address);return u.protocol==="https:" && !!u.hostname &&
    !u.username && !u.password && !u.search && !u.hash; }catch{return false;}
}
async function readJson(request){
  if(Number(request.headers.get("Content-Length")||0)>5000)
    throw new GateError("body_too_large",413);
  const text=await request.text();
  if(text.length>5000)throw new GateError("body_too_large",413);
  try {const b=JSON.parse(text);if(b&&typeof b==="object"&&!Array.isArray(b))return b;}
  catch {}throw new GateError("invalid_json");
}
function ensureRuntime(env){
  if(!env?.DB || !env?.CUSTOMER_ENROLLMENT_SECRET ||
    env.CUSTOMER_ENROLLMENT_SECRET.length<32)throw new GateError("service_not_configured",503);
}
async function customer(request,env){
  ensureRuntime(env);
  const auth=request.headers.get("Authorization")||"";
  if(!auth.startsWith("Bearer ") || !RX_TOKEN.test(auth.slice(7)))throw new GateError("unauthorized",401);
  // The token is a program-scoped credential provisioned by the existing Amin API.
  // Enforce separately issued per-customer tokens; public deployment requires
  // identity provisioner integration before external sales.
  const digest=await sha256(env.CUSTOMER_ENROLLMENT_SECRET+":"+auth.slice(7));
  const record=await env.DB.prepare("SELECT id, enabled FROM customers WHERE account_hash=?")
    .bind(digest).first();
  if(!record?.enabled)throw new GateError("customer_not_enrolled",403);
  return record;
}
async function owner(request,env){
  const h=request.headers.get("Authorization")||"";
  if(!env.OWNER_ADMIN_TOKEN || env.OWNER_ADMIN_TOKEN.length<40 ||
     h!=="Bearer "+env.OWNER_ADMIN_TOKEN)throw new GateError("owner_unauthorized",401);
}
async function supplierQuote(env,fetcher=fetch){
  // Never fabricate a provider price. Only a trusted, explicit HTTPS adapter.
  if(!isHttpsAddress(env.SUPPLIER_QUOTE_URL) ||
     !env.SUPPLIER_QUOTE_TOKEN || env.SUPPLIER_QUOTE_TOKEN.length<20)
    throw new GateError("supplier_quote_unavailable",503);
  const u=new URL(env.SUPPLIER_QUOTE_URL);
  if(u.search || u.hash)throw new GateError("supplier_quote_unavailable",503);
  let res;
  try {
    res=await fetcher(u.toString(),{method:"POST",headers:{
      Authorization:"Bearer "+env.SUPPLIER_QUOTE_TOKEN,
      "Content-Type":"application/json","Accept":"application/json"},
      body:JSON.stringify({product:PRODUCT,quantity:1,period:"month"}),
    });
  }catch{throw new GateError("supplier_quote_unavailable",503);}
  if(!res.ok)throw new GateError("supplier_quote_unavailable",503);
  const raw=await res.json();
  return checkSupplierQuote(raw,PRODUCT);
}
function parseOwnerRent(value){
  if(typeof value!=="string" || !/^(0|[1-9]\d{0,6})(?:\.\d{1,6})?$/.test(value))
    throw new GateError("invalid_owner_rent",400);
  const [whole,tail=""]=value.split(".");
  const n=Number(whole)*1000000+Number(tail.padEnd(6,"0"));
  if(!Number.isSafeInteger(n) || n<=0)throw new GateError("invalid_owner_rent",400);
  return n;
}
async function settings(env){
  const row=await env.DB.prepare(
    "SELECT value_microunits FROM owner_settings WHERE setting_key='monthly_rent_usdt'"
  ).first();
  if(row){
    if(!Number.isSafeInteger(row.value_microunits) || row.value_microunits<=0)
      throw new GateError("rent_not_configured",503);
    return row.value_microunits;
  }
  if(!/^[1-9]\d{0,11}$/.test(env.OWNER_RENT_MONTHLY_MICROUSDT||""))
    throw new GateError("rent_not_configured",503);
  return Number(env.OWNER_RENT_MONTHLY_MICROUSDT);
}
async function ownerRent(request,env){
  ensureRuntime(env);await owner(request,env);
  if(request.method==="GET"){
    const amount=await settings(env);
    return json({monthly_rent_usdt:displayUSDT(amount),owner_only:true});
  }
  const b=await readJson(request);
  const amount=parseOwnerRent(b.monthly_rent_usdt);
  // Atomic settings change + immutable audit entry; older invoices retain price.
  await env.DB.batch([
    env.DB.prepare("INSERT INTO owner_settings(setting_key,value_microunits,updated_at) VALUES('monthly_rent_usdt',?,CURRENT_TIMESTAMP) ON CONFLICT(setting_key) DO UPDATE SET value_microunits=excluded.value_microunits,updated_at=CURRENT_TIMESTAMP")
      .bind(amount),
    env.DB.prepare("INSERT INTO owner_settings_audit(id,setting_key,value_microunits) VALUES(?,?,?)")
      .bind(unique(),"monthly_rent_usdt",amount)
  ]);
  return json({saved:true,monthly_rent_usdt:displayUSDT(amount),new_invoices_only:true});
}

function destination(env){
  // Never guess an AbanTether deposit wallet. The account holder must verify
  // independent third-party deposits are allowed by the receiver.
  if(env.PAYMENT_DESTINATION_VERIFIED!=="1" ||
     env.PAYMENT_RECEIVER_CONSENT!=="1" ||
     !/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(env.PAYMENT_TRON_ADDRESS||""))
    throw new GateError("payment_destination_not_verified",503);
  return env.PAYMENT_TRON_ADDRESS;
}
async function createQuote(request,env,fetcher){
  const principal=await customer(request,env);
  const b=await readJson(request);
  if(b.product!==PRODUCT || b.months!==1)throw new GateError("only_one_month_product");
  const quote=await supplierQuote(env,fetcher);
  const rent=await settings(env);
  const total=combinedPrice(quote.cost_microunits,rent);
  const id=unique();
  const created=new Date().toISOString();
  const expires=new Date(Math.min(Date.parse(quote.expires_at),Date.now()+QUOTE_TTL_MS)).toISOString();
  await env.DB.prepare("INSERT INTO invoices(id,customer_id,product,supplier_quote_id,supplier_cost_microunits,rent_microunits,total_microunits,created_at,quote_expires_at,state) VALUES(?,?,?,?,?,?,?,?,?,?)")
    .bind(id,principal.id,PRODUCT,quote.quote_id,quote.cost_microunits,rent,total,created,expires,"QUOTED").run();
  // Customer sees a single bundled price (not a split fee breakdown).
  return json({invoice_id:id,product:PRODUCT,total_amount:displayUSDT(total),
    asset:ASSET,network:NETWORK,valid_until:expires,state:"QUOTED"});
}
async function paymentInstructions(request,env){
  const p=await customer(request,env);
  const b=await readJson(request);
  if(typeof b.invoice_id!=="string")throw new GateError("bad_invoice");
  const invoice=await env.DB.prepare("SELECT * FROM invoices WHERE id=? AND customer_id=?")
    .bind(b.invoice_id,p.id).first();
  if(!invoice)throw new GateError("invoice_not_found",404);
  if(invoice.state!=="QUOTED" && invoice.state!=="AWAITING_PAYMENT")
    throw new GateError("invoice_state_mismatch",409);
  if(Date.parse(invoice.quote_expires_at)<=Date.now() && invoice.state==="QUOTED")
    throw new GateError("quote_expired",409);
  const address=destination(env);
  if(invoice.state==="QUOTED"){
    await env.DB.prepare("UPDATE invoices SET state='AWAITING_PAYMENT',destination=? WHERE id=? AND state='QUOTED'")
      .bind(address,invoice.id).run();
  }else if(invoice.destination!==address)throw new GateError("destination_changed",409);
  return json({invoice_id:invoice.id,state:"AWAITING_PAYMENT",
    total_amount:displayUSDT(invoice.total_microunits),asset:ASSET,
    network:NETWORK,address:address,
    warning:"قبل از ارسال ارز، شبکه و پذیرش واریز شخص ثالث توسط صرافی مقصد را مستقلاً بررسی کنید. ثبت رسید برابر با تأیید وصول نیست."});
}
async function submitClaim(request,env){
  const p=await customer(request,env);
  const b=await readJson(request);
  if(typeof b.invoice_id!=="string" || typeof b.tx_hash!=="string" ||
     !RX_TX.test(b.tx_hash))throw new GateError("invalid_claim");
  const tx=b.tx_hash.toLowerCase();
  const existing=await env.DB.prepare("SELECT * FROM invoices WHERE id=? AND customer_id=?")
    .bind(b.invoice_id,p.id).first();
  if(!existing)throw new GateError("invoice_not_found",404);
  if(existing.state!=="AWAITING_PAYMENT")throw new GateError("invoice_state_mismatch",409);
  if(existing.payment_tx && existing.payment_tx!==tx)
    throw new GateError("payment_claim_already_submitted",409);
  // No OCR/AI classification can mark money paid; the independent observer must confirm.
  const result=await env.DB.prepare("UPDATE invoices SET payment_tx=? WHERE id=? AND customer_id=? AND state='AWAITING_PAYMENT' AND (payment_tx IS NULL OR payment_tx=?)")
    .bind(tx,existing.id,p.id,tx).run();
  if(result?.meta?.changes!==1)throw new GateError("concurrent_claim",409);
  return json({invoice_id:existing.id,payment_received:false,
    state:"AWAITING_INDEPENDENT_CONFIRMATION",human_receipt_not_proof:true});
}
async function readInvoice(request,env,url){
  const p=await customer(request,env);
  const id=url.searchParams.get("id");
  if(!id || id.length>60)throw new GateError("bad_invoice");
  const row=await env.DB.prepare("SELECT id,product,total_microunits,quote_expires_at,state,activated_until FROM invoices WHERE id=? AND customer_id=?")
    .bind(id,p.id).first();
  if(!row)throw new GateError("invoice_not_found",404);
  return json({invoice_id:row.id,product:row.product,total_amount:displayUSDT(row.total_microunits),
    asset:ASSET,state:row.state,
    active:row.state==="ACTIVE" && Date.parse(row.activated_until)>Date.now(),
    expires_at:row.state==="ACTIVE"?row.activated_until:null});
}
async function signedEvent(request,env,kind){
  ensureRuntime(env);
  const secret=kind==="payment"?env.PAYMENT_OBSERVER_SIGNING_SECRET:
    env.SUPPLIER_WEBHOOK_SIGNING_SECRET;
  const timestamp=request.headers.get("X-Amin-Timestamp");
  const signature=request.headers.get("X-Amin-Signature");
  const raw=await request.text();
  if(raw.length>5000 || !(await validWebhook(secret,timestamp,raw,signature)))
    throw new GateError("invalid_webhook_signature",401);
  let event;
  try{event=JSON.parse(raw);}catch{throw new GateError("invalid_webhook");}
  if(!event?.event_id || !/^[a-zA-Z0-9_-]{8,100}$/.test(event.event_id))
    throw new GateError("invalid_event_id");
  // Authenticated observers must be independent of the payer.
  const row=await env.DB.prepare("SELECT * FROM invoices WHERE id=?").bind(event.invoice_id).first();
  if(!row)throw new GateError("invoice_not_found",404);
  if(kind==="payment"){
    checkConfirmation(row,event);
    // D1 batch is transactional: enforce globally unique chain tx across all invoices.
    const results=await env.DB.batch([
      env.DB.prepare("INSERT INTO external_events(event_id,event_kind,invoice_id,tx_hash) VALUES(?,?,?,?)")
        .bind(event.event_id,"payment",row.id,event.tx_hash),
      env.DB.prepare("UPDATE invoices SET state='PAYMENT_CONFIRMED',paid_at=CURRENT_TIMESTAMP WHERE id=? AND state='AWAITING_PAYMENT'")
        .bind(row.id)
    ]);
    if(results[1]?.meta?.changes!==1)throw new GateError("payment_state_race",409);
    return json({ok:true,invoice_id:row.id,state:"PAYMENT_CONFIRMED",
      next:"OWNER_GOOGLE_PAY_TOPUP_REQUIRED"});
  }
  checkProvisioning(row,event);
  const results=await env.DB.batch([
    env.DB.prepare("INSERT INTO external_events(event_id,event_kind,invoice_id,tx_hash) VALUES(?,?,?,?)")
      .bind(event.event_id,"fulfillment",row.id,null),
    env.DB.prepare("UPDATE invoices SET state='ACTIVE',activated_until=?,supplier_reference=? WHERE id=? AND state='PAYMENT_CONFIRMED'")
      .bind(event.access_expires_at,event.provider_reference,row.id)
  ]);
  if(results[1]?.meta?.changes!==1)throw new GateError("provisioning_state_race",409);
  return json({ok:true,invoice_id:row.id,state:"ACTIVE",expires_at:event.access_expires_at});
}
async function ownerQueue(request,env){
  ensureRuntime(env);await owner(request,env);
  const rows=await env.DB.prepare("SELECT id,product,supplier_quote_id,supplier_cost_microunits,rent_microunits,total_microunits,paid_at,state FROM invoices WHERE state='PAYMENT_CONFIRMED' ORDER BY paid_at LIMIT 50").all();
  return json({awaiting_owner_topup:rows.results||[],automatic_google_pay_charge:false,
    notice:"شارژ Google Pay توسط مالک با احراز پرداخت؛ فعال‌سازی فقط پس از تأیید مستقل تأمین‌کننده"});
}
async function enrol(request,env){
  ensureRuntime(env);await owner(request,env);
  const b=await readJson(request);
  if(!RX_TOKEN.test(b.customer_token||""))throw new GateError("invalid_customer_token");
  const digest=await sha256(env.CUSTOMER_ENROLLMENT_SECRET+":"+b.customer_token);
  const id=unique();
  await env.DB.prepare("INSERT INTO customers(id,account_hash,enabled) VALUES(?,?,1) ON CONFLICT(account_hash) DO UPDATE SET enabled=1")
    .bind(id,digest).run();
  return json({enrolled:true,account_hash:digest,raw_key_echoed:false});
}
export default {
  async fetch(request,env,ctx){
    const url=new URL(request.url),path=url.pathname;
    if(path==="/owner" && request.method==="GET")
      return new Response(OWNER_CONSOLE,{status:200,headers:{
        "Content-Type":"text/html; charset=utf-8",
        "Content-Security-Policy":"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
        ...HEADERS}});
    if(path==="/health" && request.method==="GET")return json({
      service:"amin-managed-subscriptions",deployed:true,
      supplier_ready:!!env.SUPPLIER_QUOTE_URL && !!env.SUPPLIER_QUOTE_TOKEN,
      payment_reconciliation_ready:!!env.PAYMENT_OBSERVER_SIGNING_SECRET,
      fulfillment_ready:!!env.SUPPLIER_WEBHOOK_SIGNING_SECRET,
      destination_verified:env.PAYMENT_DESTINATION_VERIFIED==="1" &&
        env.PAYMENT_RECEIVER_CONSENT==="1",
      tron_reconciliation_ready:env.PAYMENT_RECEIVER_KIND==="self_custody" &&
        env.PAYMENT_DESTINATION_VERIFIED==="1" &&
        env.PAYMENT_RECEIVER_CONSENT==="1" && !!env.TRONGRID_API_KEY,
      automatic_google_pay_charge:false});
    if(!path.startsWith("/v1/"))return denied("not_found",404);
    const browserOrigin=request.headers.get("Origin");
    if(browserOrigin && browserOrigin!==url.origin)return denied("browser_origin_not_allowed",403);
    try{
      if(path==="/v1/quote" && request.method==="POST")return await createQuote(request,env,fetch);
      if(path==="/v1/order" && request.method==="POST")return await paymentInstructions(request,env);
      if(path==="/v1/claim" && request.method==="POST")return await submitClaim(request,env);
      if(path==="/v1/invoice" && request.method==="GET")return await readInvoice(request,env,url);
      if(path==="/v1/webhook/payment" && request.method==="POST")return await signedEvent(request,env,"payment");
      if(path==="/v1/webhook/supplier" && request.method==="POST")return await signedEvent(request,env,"supplier");
      if(path==="/v1/owner/rent" && (request.method==="GET" || request.method==="POST"))return await ownerRent(request,env);
      if(path==="/v1/owner/queue" && request.method==="GET")return await ownerQueue(request,env);
      if(path==="/v1/owner/enroll" && request.method==="POST")return await enrol(request,env);
      return denied("not_found",404);
    }catch(e){return denied(e instanceof GateError?e.code:"backend_unavailable",
      e instanceof GateError?e.status:503);}
  },
  async scheduled(event,env,ctx){
    // Cron is not a payment processor. Query a genuine finalized USDT event.
    if(env.PAYMENT_RECEIVER_KIND==="self_custody" &&
       env.PAYMENT_DESTINATION_VERIFIED==="1" &&
       env.PAYMENT_RECEIVER_CONSENT==="1" && !!env.TRONGRID_API_KEY && env.DB)
      ctx.waitUntil(reconcileDue(env));
  }
};
