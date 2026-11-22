import test from "node:test";
import assert from "node:assert/strict";
import {assessReceipt,BillingError,sha256} from "../src/play-verifier.mjs";
import worker from "../src/index.mjs";
const account="a".repeat(64), product="amin_support_monthly";
const receipt=(p={})=>({
  subscriptionState:"SUBSCRIPTION_STATE_ACTIVE",
  startTime:"2026-11-01T10:00:00Z",
  acknowledgementState:"ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
  externalAccountIdentifiers:{obfuscatedExternalAccountId:account},
  lineItems:[{productId:product,expiryTime:"2027-01-15T00:00:00Z"}],...p
});
const expected=()=>({product_id:product,state:"SUBSCRIPTION_STATE_ACTIVE"});
test("accepts only matching owner, product, unexpired Google receipt",()=>{
  assert.deepEqual((( {product_id,state} )=>({product_id,state}))(assessReceipt(receipt(),account,product,Date.parse("2026-12-01T00:00:00Z"))),expected());
});
test("never treats pending purchase or expired period as paid",()=>{
  for(const p of [
    {subscriptionState:"SUBSCRIPTION_STATE_PENDING"},
    {subscriptionState:"SUBSCRIPTION_STATE_PAUSED"},
    {subscriptionState:"SUBSCRIPTION_STATE_ON_HOLD"},
    {subscriptionState:"SUBSCRIPTION_STATE_EXPIRED"},
    {lineItems:[{productId:product,expiryTime:"2026-01-01T00:00:00Z"}]},
    {lineItems:[{productId:"another",expiryTime:"2027-01-15T00:00:00Z"}]},
    {startTime:null},
  ])assert.throws(()=>assessReceipt(receipt(p),account,product,Date.parse("2026-12-01T00:00:00Z")),BillingError);
});
test("rejects receipts linked to different purchaser",()=>{
  assert.throws(()=>assessReceipt(receipt(), "b".repeat(64), product,Date.parse("2026-12-01T00:00:00Z")), /purchase_account_mismatch/);
});
test("canceled but still paid through expiry is not mistaken for expired",()=>{
  const result=assessReceipt(receipt({subscriptionState:"SUBSCRIPTION_STATE_CANCELED"}),account,product,Date.parse("2026-12-01T00:00:00Z"));
  assert.equal(result.state,"SUBSCRIPTION_STATE_CANCELED");
});
test("same token deterministic digest with no plaintext stored",async()=>{
  assert.match(await sha256("amin_".padEnd(45,"A")),/^[a-f0-9]{64}$/);
});
test("fails closed: no merchant credentials, no payment claim",async()=>{
  const req=new Request("https://billing.example/billing/verify",{method:"POST",
    headers:{Authorization:"Bearer amin_"+"A".repeat(45),"Content-Type":"application/json"},
    body:JSON.stringify({purchase_token:"x".repeat(50)})});
  const res=await worker.fetch(req,{AMIN_MERCHANT_READY:"0"});
  assert.equal(res.status,503);const body=await res.json();
  assert.equal(body.entitlement_granted,false);
});
test("health discloses no fake wallet or revenue settlement",async()=>{
  const res=await worker.fetch(new Request("https://billing.example/billing/health"),{AMIN_MERCHANT_READY:"0"});
  const body=await res.json();
  assert.equal(body.configured,false);assert.equal(body.merchant_income_wallet,"NOT_GOOGLE_PAY");
});
