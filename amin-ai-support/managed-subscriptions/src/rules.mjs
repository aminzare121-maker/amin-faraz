// Pure security and money rules shared by the Worker and Node tests.
export const PRODUCT = "amin-ai-monthly";
export const ASSET = "USDT";
export const NETWORK = "TRC20";
export const MONTH_US = 30 * 24 * 60 * 60 * 1000;
export const QUOTE_TTL_MS = 15 * 60 * 1000;
export const RX_TOKEN = /^amin_[a-zA-Z0-9_-]{40,60}$/;
export const RX_HASH = /^[a-f0-9]{64}$/;
export const RX_TX = /^(?:[a-fA-F0-9]{64})$/;
export class GateError extends Error {
  constructor(code,status=400){super(code);this.code=code;this.status=status;}
}
export function requireMicroUSDT(n){
  if(!Number.isSafeInteger(n) || n<0 || n>10_000_000_000_000)
    throw new GateError("invalid_amount");
  return n;
}
export function combinedPrice(supplierMicro, monthlyRentMicro){
  const supplier=requireMicroUSDT(supplierMicro);
  const rent=requireMicroUSDT(monthlyRentMicro);
  const total=supplier+rent;
  if(!Number.isSafeInteger(total) || total<=0)throw new GateError("invalid_total");
  return total;
}
export function displayUSDT(micro){
  requireMicroUSDT(micro);
  const whole=Math.floor(micro/1_000_000);
  const decimals=String(micro%1_000_000).padStart(6,"0").replace(/0+$/,"");
  return String(whole)+(decimals?"."+decimals:"");
}
export function checkSupplierQuote(q,product,now=Date.now()){
  if(!q || typeof q!=="object" || q.product!==product ||
    q.currency!=="USDT" || q.network!=="TRC20" ||
    typeof q.quote_id!=="string" || !/^[a-zA-Z0-9_-]{8,128}$/.test(q.quote_id) ||
    !Number.isSafeInteger(q.cost_microunits) || q.cost_microunits<=0 ||
    !Number.isFinite(Date.parse(q.expires_at)) ||
    Date.parse(q.expires_at)<=now || Date.parse(q.expires_at)>now+QUOTE_TTL_MS)
    throw new GateError("supplier_quote_unavailable",503);
  return q;
}
export function checkConfirmation(invoice,event,now=Date.now()){
  if(!invoice || invoice.state!=="AWAITING_PAYMENT" ||
     typeof invoice.payment_tx!=="string" ||
     !RX_TX.test(invoice.payment_tx))throw new GateError("invoice_not_awaiting_payment",409);
  if(!event || event.invoice_id!==invoice.id ||
     event.tx_hash!==invoice.payment_tx ||
     event.network!==NETWORK || event.asset!==ASSET ||
     event.to_address!==invoice.destination ||
     event.confirmed!==true ||
     !Number.isInteger(event.confirmations) || event.confirmations<20 ||
     !Number.isSafeInteger(event.amount_microunits) ||
     event.amount_microunits<invoice.total_microunits ||
     !Number.isFinite(Date.parse(event.block_time)) ||
     Date.parse(event.block_time)<Date.parse(invoice.created_at)-300000 ||
     Date.parse(event.block_time)>now+300000)
     throw new GateError("payment_not_independently_confirmed",409);
  return {verified:true,invoice_id:invoice.id,tx_hash:event.tx_hash};
}
export function checkProvisioning(invoice,event,now=Date.now()){
  if(!invoice || invoice.state!=="PAYMENT_CONFIRMED" ||
     event?.invoice_id!==invoice.id ||
     event?.supplier_quote_id!==invoice.supplier_quote_id ||
     event?.product!==PRODUCT ||
     event?.fulfilled!==true ||
     typeof event.provider_reference!=="string" ||
     !/^[a-zA-Z0-9_.-]{8,120}$/.test(event.provider_reference) ||
     !Number.isFinite(Date.parse(event.access_expires_at)) ||
     Date.parse(event.access_expires_at)<=now ||
     Date.parse(event.access_expires_at)>now+45*24*60*60*1000)
     throw new GateError("provider_service_not_confirmed",409);
  return {active:true,expires_at:event.access_expires_at};
}
export async function sha256(value){
  const b=new TextEncoder().encode(value);
  const h=new Uint8Array(await crypto.subtle.digest("SHA-256",b));
  return [...h].map(x=>x.toString(16).padStart(2,"0")).join("");
}
export async function validWebhook(secret,timestamp,body,signature,now=Date.now()){
  if(typeof secret!=="string" || secret.length<32 ||
     typeof timestamp!=="string" || !/^\d{10,13}$/.test(timestamp) ||
     typeof signature!=="string" || !/^[a-f0-9]{64}$/.test(signature))return false;
  const millis=timestamp.length===10?Number(timestamp)*1000:Number(timestamp);
  if(!Number.isSafeInteger(millis) || Math.abs(now-millis)>300000)return false;
  const raw=new Uint8Array(signature.match(/.{2}/g).map(x=>parseInt(x,16)));
  const key=await crypto.subtle.importKey("raw",new TextEncoder().encode(secret),
    {name:"HMAC",hash:"SHA-256"},false,["verify"]);
  return crypto.subtle.verify("HMAC",key,raw,new TextEncoder().encode(timestamp+"."+body));
}
