import test from "node:test";
import assert from "node:assert/strict";
import {
 MAINNET_USDT,findValidTransfer,finalizedBlocks,verifyTronInvoice,reconcileDue
} from "../src/tron-watch.mjs";
const dest="T"+"1".repeat(33);
const tx="a".repeat(64);
const now=Date.now();
const invoice={id:"order_123456",state:"AWAITING_PAYMENT",payment_tx:tx,
 destination:dest,total_microunits:8_700_000,
 created_at:new Date(now-10*60*1000).toISOString()};
const transfer={transaction_id:tx,to:dest,from:"T"+"2".repeat(33),
 type:"Transfer",value:"8700000",
 block_timestamp:now-60000,token_info:{address:MAINNET_USDT,decimals:6}};
const payload={data:[transfer],success:true,meta:{}};
test("rejects wrong token contract, wrong destination, amount, forged tx and duplicate transfer",()=>{
  assert.equal(findValidTransfer(payload,invoice).value,"8700000");
  for(const p of [{token_info:{address:"fake",decimals:6}},{to:"T"+"4".repeat(33)},
    {value:"1"},{transaction_id:"b".repeat(64)},{type:"Approval"},
    {value:"0.5"},{block_timestamp:now-86_400_000}]){
    assert.equal(findValidTransfer({data:[{...transfer,...p}],success:true},invoice),null);
  }
  assert.equal(findValidTransfer({data:[transfer,transfer]},invoice),null);
});
test("require finalized chain execution and at least 20 finalized blocks after transfer",()=>{
  const receipt={id:tx,receipt:{result:"SUCCESS"},blockNumber:100};
  const body={txID:tx,ret:[{contractRet:"SUCCESS"}]};
  const head={block_header:{raw_data:{number:119}}};
  assert.equal(finalizedBlocks(receipt,body,head,tx),20);
  assert.equal(finalizedBlocks(receipt,body,{block_header:{raw_data:{number:118}}},tx),0);
  assert.equal(finalizedBlocks({...receipt,receipt:{result:"REVERT"}},body,head,tx),0);
  assert.equal(finalizedBlocks(receipt,{...body,ret:[{contractRet:"REVERT"}]},head,tx),0);
});
test("automatically verifies genuine TRON indexer plus solidity, never a screenshot",async()=>{
  const env={PAYMENT_DESTINATION_VERIFIED:"1",PAYMENT_RECEIVER_CONSENT:"1",
    TRONGRID_API_KEY:"test_rpc_key_123456789",PAYMENT_TRON_ADDRESS:dest};
  const requests=[];
  const fakeFetch=async(url,options)=>{
    requests.push(url);
    if(url.includes("/transactions/trc20"))return {ok:true,json:async()=>payload};
    if(url.endsWith("/gettransactionbyid"))return {ok:true,json:async()=>({txID:tx,ret:[{contractRet:"SUCCESS"}]})};
    if(url.endsWith("/gettransactioninfobyid"))return {ok:true,json:async()=>({id:tx,receipt:{result:"SUCCESS"},blockNumber:100})};
    if(url.endsWith("/getnowblock"))return {ok:true,json:async()=>({block_header:{raw_data:{number:122}}})};
    throw new Error("unexpected URL");
  };
  assert.deepEqual(await verifyTronInvoice(env,invoice,fakeFetch),
    {verified:true,invoice_id:invoice.id,tx_hash:tx});
  assert.equal(requests.length,4);
});
test("disabled receiver or missing Tron API key cannot approve payment",async()=>{
  await assert.rejects(verifyTronInvoice({PAYMENT_DESTINATION_VERIFIED:"1",
    PAYMENT_RECEIVER_CONSENT:"0",PAYMENT_TRON_ADDRESS:dest,TRONGRID_API_KEY:"test_rpc_key_123456789"},invoice),/automatic_reconciliation_not_configured/);
});
test("no database events or money claims if no API and consent",async()=>{
  await assert.rejects(reconcileDue({},async()=>{throw new Error("must not call");}),
    /automatic_reconciliation_not_configured/);
});
