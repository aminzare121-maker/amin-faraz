// Companion billing gate, not a replacement for the existing Amin app backend.
// Needs legitimate Google Play merchant profile and server-side D1 + secrets.
import { BillingError,sha256,tokenPattern,verifyWithGoogle } from "./play-verifier.mjs";
const secure = {"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer"};
const reply=(data,status=200)=>Response.json(data,{status,headers:secure});
const error=(code,status)=>reply({error:code,entitlement_granted:false},status);
function authorizedAccount(request) {
  const value=request.headers.get("Authorization")||"";
  if(!/^Bearer amin_[A-Za-z0-9_-]{40,60}$/.test(value)) throw new BillingError("invalid_customer_token",401);
  return value.slice(7);
}
async function requestBody(request) {
  if(Number(request.headers.get("Content-Length")||0)>6000) throw new BillingError("body_too_large",413);
  const content=await request.text();
  if(content.length>6000) throw new BillingError("body_too_large",413);
  try { const x=JSON.parse(content); if(x&&typeof x==="object"&&!Array.isArray(x))return x; }
  catch {}
  throw new BillingError("bad_json",400);
}
export default {
  async fetch(request,env){
    const path=new URL(request.url).pathname;
    if(request.method==="GET"&&path==="/billing/health")
      return reply({service:"amin-play-billing",configured:env.AMIN_MERCHANT_READY==="1" &&
        !!env.DB && !!env.PLAY_SERVICE_ACCOUNT_JSON && env.PLAY_PACKAGE_NAME==="com.amin.support.mobile",
        merchant_income_wallet:"NOT_GOOGLE_PAY",settlement_source:"Google Play Console payments profile"});
    if(path!=="/billing/verify" || request.method!=="POST")return error("not_found",404);
    // Native Android clients do not set Origin. Cross-site browsers are blocked.
    if(request.headers.has("Origin"))return error("browser_origin_not_allowed",403);
    try {
      if(env.AMIN_MERCHANT_READY!=="1")throw new BillingError("merchant_not_verified_or_configured",503);
      const token=authorizedAccount(request);
      if(!tokenPattern.test(token))throw new BillingError("invalid_customer_token",401);
      const body=await requestBody(request);
      const accountHash=await sha256(token);
      const receipt=await verifyWithGoogle(env,body.purchase_token,accountHash);
      const receiptHash=await sha256(body.purchase_token);
      // Prevent recycling one Google purchase token to a second customer account.
      const result=await env.DB.prepare(
        "INSERT INTO play_receipts(receipt_hash,account_hash,product_id,subscription_state,expires_at,is_test,verified_at) "+
        "VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(receipt_hash) DO UPDATE SET "+
        "subscription_state=excluded.subscription_state,expires_at=excluded.expires_at,"+
        "verified_at=CURRENT_TIMESTAMP WHERE account_hash=excluded.account_hash AND product_id=excluded.product_id"
      ).bind(receiptHash,accountHash,receipt.product_id,receipt.state,receipt.expires_at,receipt.test_purchase?1:0).run();
      if(result?.meta?.changes!==1)throw new BillingError("receipt_already_claimed",409);
      return reply({
        entitlement_granted:true,source:"verified_google_play_api",product_id:receipt.product_id,
        expires_at:receipt.expires_at,subscription_state:receipt.state,
        test_purchase:receipt.test_purchase,
        payout_confirmed:false,google_pay_wallet_balance:null,
        merchant_payout_source:"Google Play Console (bank payout)"
      });
    } catch(e) { return error(e instanceof BillingError?e.code:"billing_backend_unavailable",
      e instanceof BillingError?e.status:503); }
  }
};
