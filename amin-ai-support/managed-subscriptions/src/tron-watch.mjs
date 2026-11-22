// Read-only TRON USDT reconciler; independent of payer screenshots or owner claims.
// Uses TronGrid indexed history AND solidity-node finalized execution receipts.
import {checkConfirmation,GateError,RX_TX} from "./rules.mjs";

export const MAINNET_USDT="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t";
const BASE="https://api.trongrid.io";
const TX_AMOUNT=/^[0-9]{1,32}$/;

function tronAuth(env){
  // An exchange deposit address does not prove the exchange credited the owner.
  // Public-chain reconciliation alone is sufficient only for OWNER self-custody.
  if(env.PAYMENT_RECEIVER_KIND!=="self_custody" ||
     env.PAYMENT_DESTINATION_VERIFIED!=="1" ||
     env.PAYMENT_RECEIVER_CONSENT!=="1" ||
     typeof env.TRONGRID_API_KEY!=="string" ||
     env.TRONGRID_API_KEY.length<16 ||
     !/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(env.PAYMENT_TRON_ADDRESS||""))
     throw new GateError("automatic_reconciliation_not_configured",503);
  return {"TRON-PRO-API-KEY":env.TRONGRID_API_KEY,"Accept":"application/json"};
}
async function asJson(fetcher,url,options){
  let response;
  try{response=await fetcher(url,options);}catch{
    throw new GateError("tron_query_unavailable",503);
  }
  if(!response.ok)throw new GateError("tron_query_unavailable",503);
  let data;
  try{data=await response.json();}catch{
    throw new GateError("tron_query_invalid_response",503);
  }
  if(!data || typeof data!=="object")throw new GateError("tron_query_invalid_response",503);
  return data;
}
export function findValidTransfer(payload,invoice,now=Date.now()){
  if(!payload || payload.success===false || !Array.isArray(payload.data))
    throw new GateError("tron_indexer_unavailable",503);
  const valid=payload.data.filter(t=>
    t && t.type==="Transfer" &&
    t.transaction_id?.toLowerCase()===invoice.payment_tx &&
    t.to===invoice.destination &&
    t.token_info?.address===MAINNET_USDT &&
    Number(t.token_info.decimals)===6 &&
    typeof t.value==="string" && TX_AMOUNT.test(t.value) &&
    BigInt(t.value)<=BigInt(Number.MAX_SAFE_INTEGER) &&
    BigInt(t.value)>=BigInt(invoice.total_microunits) &&
    Number.isSafeInteger(t.block_timestamp) &&
    t.block_timestamp>=Date.parse(invoice.created_at)-300000 &&
    t.block_timestamp<=now+300000
  );
  // No ambiguous multiple transfer records can unlock one invoice.
  return valid.length===1?valid[0]:null;
}
async function lookupTransfer(env,invoice,fetcher=fetch){
  const headers=tronAuth(env);
  let fingerprint="";
  const minTimestamp=Date.parse(invoice.created_at)-300000;
  if(!Number.isFinite(minTimestamp))throw new GateError("invalid_invoice_time",503);
  for(let page=0;page<4;page++){
    const u=new URL(BASE+"/v1/accounts/"+invoice.destination+"/transactions/trc20");
    u.searchParams.set("only_confirmed","true");
    u.searchParams.set("only_to","true");
    u.searchParams.set("contract_address",MAINNET_USDT);
    u.searchParams.set("limit","200");
    u.searchParams.set("min_timestamp",String(minTimestamp));
    if(fingerprint)u.searchParams.set("fingerprint",fingerprint);
    const body=await asJson(fetcher,u.toString(),{method:"GET",headers});
    const event=findValidTransfer(body,invoice);
    if(event)return event;
    if(!body.meta?.fingerprint || body.meta.fingerprint===fingerprint)return null;
    fingerprint=body.meta.fingerprint;
  }
  return null;
}
async function readSolidity(env,path,tx,fetcher=fetch){
  return asJson(fetcher,BASE+path,{
    method:"POST",
    headers:{"Content-Type":"application/json",...tronAuth(env)},
    body:JSON.stringify(tx?{value:tx}:{})
  });
}
export function finalizedBlocks(receipt,transaction,head,tx){
  if(receipt.id?.toLowerCase()!==tx ||
     transaction.txID?.toLowerCase()!==tx ||
     receipt.result==="FAILED" || receipt.receipt?.result!=="SUCCESS" ||
     transaction.ret?.[0]?.contractRet!=="SUCCESS" ||
     !Number.isSafeInteger(receipt.blockNumber) ||
     !Number.isSafeInteger(head.block_header?.raw_data?.number))
     return 0;
  const confirmations=head.block_header.raw_data.number-receipt.blockNumber+1;
  return Number.isSafeInteger(confirmations)&&confirmations>=20?confirmations:0;
}
export async function verifyTronInvoice(env,invoice,fetcher=fetch){
  tronAuth(env);
  if(invoice.state!=="AWAITING_PAYMENT" || !RX_TX.test(invoice.payment_tx||"") ||
     invoice.destination!==env.PAYMENT_TRON_ADDRESS)return null;
  const transfer=await lookupTransfer(env,invoice,fetcher);
  if(!transfer)return null;
  const tx=invoice.payment_tx;
  const [body,receipt,head]=await Promise.all([
    readSolidity(env,"/walletsolidity/gettransactionbyid",tx,fetcher),
    readSolidity(env,"/walletsolidity/gettransactioninfobyid",tx,fetcher),
    readSolidity(env,"/walletsolidity/getnowblock",null,fetcher)
  ]);
  const confirmed=finalizedBlocks(receipt,body,head,tx);
  if(!confirmed)return null;
  const event={
    invoice_id:invoice.id,tx_hash:tx,asset:"USDT",network:"TRC20",
    to_address:invoice.destination,confirmed:true,confirmations:confirmed,
    amount_microunits:Number(transfer.value),
    block_time:new Date(transfer.block_timestamp).toISOString()
  };
  return checkConfirmation(invoice,event);
}
export async function reconcileDue(env,fetcher=fetch){
  tronAuth(env);
  if(!env.DB)throw new GateError("service_not_configured",503);
  const rows=await env.DB.prepare("SELECT * FROM invoices WHERE state='AWAITING_PAYMENT' AND payment_tx IS NOT NULL ORDER BY created_at LIMIT 6").all();
  let confirmed=0,unchecked=0,failed=0;
  for(const invoice of rows.results||[]){
    try{
      const verification=await verifyTronInvoice(env,invoice,fetcher);
      if(!verification){unchecked++;continue;}
      const results=await env.DB.batch([
        env.DB.prepare("INSERT INTO external_events(event_id,event_kind,invoice_id,tx_hash) VALUES(?,?,?,?)")
          .bind("tron_"+invoice.payment_tx,"payment",invoice.id,invoice.payment_tx),
        env.DB.prepare("UPDATE invoices SET state='PAYMENT_CONFIRMED',paid_at=CURRENT_TIMESTAMP WHERE id=? AND state='AWAITING_PAYMENT'")
          .bind(invoice.id)
      ]);
      if(results[1]?.meta?.changes===1)confirmed++;else failed++;
    }catch(error){
      // Stay pending on Tron API error, duplicate event, or absent finality.
      failed++;
    }
  }
  return {checked:(rows.results||[]).length,confirmed,unchecked,failed};
}
