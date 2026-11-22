// Server-only Google Play verifier. Never trust device-side purchase flags.
const API = "https://androidpublisher.googleapis.com/androidpublisher/v3";
const OAUTH = "https://oauth2.googleapis.com/token";
const SCOPE = "https://www.googleapis.com/auth/androidpublisher";
const AUTH_STATES = new Set([
  "SUBSCRIPTION_STATE_ACTIVE",
  "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
  "SUBSCRIPTION_STATE_CANCELED", // canceled but paid-through expiry
]);
export const tokenPattern = /^amin_[A-Za-z0-9_-]{40,60}$/;
export class BillingError extends Error {
  constructor(code, status = 400) { super(code); this.status = status; this.code = code; }
}
const bytes = value => new TextEncoder().encode(value);
export const hex = data => [...new Uint8Array(data)].map(v=>v.toString(16).padStart(2,"0")).join("");
export async function sha256(value) { return hex(await crypto.subtle.digest("SHA-256", bytes(value))); }
const base64url = raw => btoa(String.fromCharCode(...raw))
  .replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
function requireConfig(env) {
  if (!env || env.AMIN_MERCHANT_READY !== "1" ||
      env.PLAY_PACKAGE_NAME !== "com.amin.support.mobile" ||
      !/^[a-zA-Z0-9_.]{3,100}$/.test(env.PLAY_SUBSCRIPTION_ID||"") ||
      !env.PLAY_SERVICE_ACCOUNT_JSON || !env.DB) {
    throw new BillingError("merchant_not_verified_or_configured",503);
  }
}
export function assessReceipt(receipt, accountHash, product, nowMs = Date.now()) {
  if (!receipt || typeof receipt !== "object") throw new BillingError("bad_google_receipt",502);
  const actualAccount = receipt.externalAccountIdentifiers?.obfuscatedExternalAccountId;
  // Explicitly require account binding. Unbound receipts cannot unlock another user.
  if (!/^[a-f0-9]{64}$/.test(accountHash) || actualAccount !== accountHash)
    throw new BillingError("purchase_account_mismatch",403);
  if (!AUTH_STATES.has(receipt.subscriptionState)) throw new BillingError("subscription_not_active",402);
  const items = Array.isArray(receipt.lineItems) ? receipt.lineItems : [];
  const eligible = items.filter(v=>v && v.productId === product &&
    Number.isFinite(Date.parse(v.expiryTime)) && Date.parse(v.expiryTime) > nowMs);
  if (eligible.length !== 1 || items.length !== 1) throw new BillingError("product_or_expiry_mismatch",402);
  if (!receipt.startTime || !Number.isFinite(Date.parse(receipt.startTime)))
    throw new BillingError("unpaid_or_pending_subscription",402);
  return {
    product_id: product, state: receipt.subscriptionState,
    expires_at: eligible[0].expiryTime,
    must_acknowledge: receipt.acknowledgementState === "ACKNOWLEDGEMENT_STATE_PENDING",
    acknowledgement_state: receipt.acknowledgementState,
    test_purchase: !!receipt.testPurchase,
  };
}
async function serviceToken(env, http) {
  let service;
  try { service=JSON.parse(env.PLAY_SERVICE_ACCOUNT_JSON); } catch { throw new BillingError("service_account_config_invalid",503); }
  if (typeof service.client_email!=="string" || typeof service.private_key!=="string" ||
      !service.private_key.includes("BEGIN PRIVATE KEY")) throw new BillingError("service_account_config_invalid",503);
  const clean=service.private_key.replace(/-----BEGIN PRIVATE KEY-----|-----END PRIVATE KEY-----|\s/g,"");
  let der;
  try { der=Uint8Array.from(atob(clean),c=>c.charCodeAt(0)); } catch { throw new BillingError("service_account_config_invalid",503); }
  const key=await crypto.subtle.importKey("pkcs8",der,{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["sign"]);
  const now=Math.floor(Date.now()/1000);
  const enc=value=>base64url(bytes(JSON.stringify(value)));
  const head=enc({alg:"RS256",typ:"JWT"});
  const payload=enc({iss:service.client_email,scope:SCOPE,aud:OAUTH,iat:now,exp:now+3500});
  const unsigned=head+"."+payload;
  const signature=base64url(new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5",key,bytes(unsigned))));
  let response;
  try { response=await http(OAUTH,{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},
    body:new URLSearchParams({grant_type:"urn:ietf:params:oauth:grant-type:jwt-bearer",assertion:unsigned+"."+signature})}); }
  catch { throw new BillingError("google_auth_unavailable",503); }
  if(!response.ok) throw new BillingError("google_auth_rejected",503);
  const data=await response.json();
  if(!data?.access_token || typeof data.access_token!=="string") throw new BillingError("google_auth_rejected",503);
  return data.access_token;
}
export async function verifyWithGoogle(env,purchaseToken,accountHash,http=fetch) {
  requireConfig(env);
  if(typeof purchaseToken!=="string" || purchaseToken.length<20 || purchaseToken.length>4096 ||
      !/^[A-Za-z0-9_.-]+$/.test(purchaseToken)) throw new BillingError("bad_purchase_token",400);
  const access=await serviceToken(env,http);
  const url=API+"/applications/"+encodeURIComponent(env.PLAY_PACKAGE_NAME)+"/purchases/subscriptionsv2/tokens/"+encodeURIComponent(purchaseToken);
  let response;
  try { response=await http(url,{headers:{Authorization:"Bearer "+access,Accept:"application/json"}}); }
  catch { throw new BillingError("google_validation_unavailable",503); }
  if(!response.ok) throw new BillingError("google_validation_rejected",403);
  const receipt=await response.json();
  const normalized=assessReceipt(receipt,accountHash,env.PLAY_SUBSCRIPTION_ID);
  if(normalized.acknowledgement_state!=="ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED" && !normalized.must_acknowledge)
    throw new BillingError("acknowledgement_unknown",503);
  if(normalized.must_acknowledge) {
    const ack=API+"/applications/"+encodeURIComponent(env.PLAY_PACKAGE_NAME)+"/purchases/subscriptions/"+
      encodeURIComponent(env.PLAY_SUBSCRIPTION_ID)+"/tokens/"+encodeURIComponent(purchaseToken)+":acknowledge";
    let acknowledged;
    try { acknowledged=await http(ack,{method:"POST",headers:{Authorization:"Bearer "+access,"Content-Type":"application/json"},body:"{}"}); }
    catch { throw new BillingError("google_acknowledgement_unavailable",503); }
    if(!acknowledged.ok) throw new BillingError("google_acknowledgement_rejected",503);
  }
  return normalized;
}
