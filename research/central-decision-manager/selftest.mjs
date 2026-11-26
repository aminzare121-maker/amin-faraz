import {decide} from './manager.mjs';
function selfTest(){
  const now=1800000000000, symbol="XAUUSD.st", opportunityId="case-1";
  const fixture=()=>{
    const registry=[{id:"e1",version:"v1",family:"structure"},{id:"e2",version:"v1",family:"structure"},{id:"e3",version:"v1",family:"independent"}];
    const signals=registry.map((e,i)=>({engineId:e.id,version:e.version,symbol,opportunityId,signalId:"new"+i,side:i===2?"SELL":"BUY",confirmed:true,knownAt:now-10,expiresAt:now+1000}));
    const bars=Array.from({length:24},(_,i)=>({closedAt:now-1000-(23-i)*900000,close:4000+i,high:4000+i+0.6,low:4000+i-0.6}));
    const history=registry.flatMap((e,i)=>Array.from({length:10},(_,j)=>({engineId:e.id,version:e.version,symbol,signalId:"h"+j,regime:"TREND_UP",side:i===2?"SELL":"BUY",verified:true,shadow:true,costsVerified:true,signalAt:now-500000-j*10000,closedAt:now-200000-j*10000,netUsd:i===2?3:0.5,initialRiskUsd:1})));
    const preflight=["BUY","SELL"].flatMap(side=>[0.01,0.02].map(lot=>({symbol,opportunityId,side,verified:true,costsVerified:true,orderCheckPassed:true,checkedAt:now-10,expiresAt:now+500,lot,entry:side==="BUY"?4023.2:4023,stop:side==="BUY"?4020:4026,maxLossUsd:lot===0.01?4:8,costUsd:1,expectedGrossUsd:lot===0.01?7:12,freeMarginAfter:160,marginLevelAfter:500})));
    return {now,symbol,opportunityId,registry,signals,history,ledger:[],market:{symbol,asOf:now-5,bid:4023,ask:4023.2,newsKnown:true,newsBlocked:false,sessionOpen:true,bars},account:{verified:true,asOf:now-5,equity:200,freeMargin:180,openRisk:0,openPositions:0,pendingPositions:0},policy:{minSamples:5,maxAgeMs:3000,maxHistoryAgeMs:1e9,penalty:1,minEdgeR:0.1,minGapR:0.1,minFamilies:1,maxRiskFraction:0.025,maxSpread:0.5,minMarginLevel:200,minFreeMargin:30,maxPositions:1},preflight};
  };
  const tests=[];
  const check=(name,change,predicate)=>{const x=fixture();change(x);const r=decide(x);if(!predicate(r))throw Error(name+" failed: "+JSON.stringify(r));tests.push(name);};
  check("one strong independent engine defeats two correlated votes",()=>{},r=>r.action==="SELL"&&r.lot===0.01&&r.scores.BUY===0.5&&r.scores.SELL===3&&r.ordersSent===0);
  check("future results ignored",x=>{x.history.forEach(h=>{if(h.engineId==="e3")h.closedAt=x.now+1;});},r=>r.action==="BUY");
  check("unverified costs excluded",x=>x.history.forEach(h=>h.costsVerified=false),r=>r.reason==="INSUFFICIENT_NET_EVIDENCE");
  check("stale signal blocks",x=>x.signals[0].expiresAt=x.now-1,r=>r.reason==="STALE_OR_INVALID_ENGINE_SIGNAL");
  check("future signal blocks",x=>x.signals[0].knownAt=x.now+1,r=>r.reason==="STALE_OR_INVALID_ENGINE_SIGNAL");
  check("missing engine blocks",x=>x.signals.pop(),r=>r.reason==="MISSING_OR_DUPLICATE_SIGNALS");
  check("duplicate opportunity blocks",x=>x.ledger.push({symbol,opportunityId,state:"RESERVED"}),r=>r.reason==="DUPLICATE_OPPORTUNITY");
  check("pending order blocks",x=>x.account.pendingPositions=1,r=>r.reason==="PORTFOLIO_LIMIT");
  check("spread blocks",x=>x.market.ask=4025,r=>r.reason==="MARKET_RISK_GATE");
  check("news blocks",x=>x.market.newsBlocked=true,r=>r.reason==="MARKET_RISK_GATE");
  check("unknown news blocks",x=>x.market.newsKnown=false,r=>r.reason==="MARKET_NOT_VERIFIED");
  check("unverified account blocks",x=>x.account.verified=false,r=>r.reason==="ACCOUNT_NOT_VERIFIED");
  check("insufficient margin blocks",x=>x.preflight.forEach(c=>c.marginLevelAfter=90),r=>r.reason==="NO_SAFE_BROKER_VALIDATED_SIZE");
  check("unverified preflight blocks",x=>x.preflight.forEach(c=>c.verified=false),r=>r.reason==="NO_SAFE_BROKER_VALIDATED_SIZE");
  check("existing risk reduces risk budget",x=>x.account.openRisk=3,r=>r.reason==="NO_SAFE_BROKER_VALIDATED_SIZE");
  check("negative edge abstains",x=>x.history.forEach(h=>h.netUsd=-2),r=>r.reason==="INSUFFICIENT_NET_EVIDENCE");
  check("duplicate history blocks",x=>x.history.push({...x.history[0]}),r=>r.reason==="DUPLICATE_HISTORY");
  check("minimum independent families",x=>x.policy.minFamilies=2,r=>r.reason==="INSUFFICIENT_NET_EVIDENCE");
  check("future bar blocks",x=>x.market.bars.at(-1).closedAt=x.now+1,r=>r.reason==="INVALID_OR_FUTURE_BARS");
  check("price changed since order check",x=>x.preflight.forEach(c=>c.entry+=1),r=>r.reason==="NO_SAFE_BROKER_VALIDATED_SIZE");
  check("version changed prevents inherited evidence",x=>{x.registry[2].version="v2";x.signals[2].version="v2";},r=>r.action==="BUY");
  check("missing risk policy fails closed",x=>delete x.policy.maxRiskFraction,r=>r.reason==="MISSING_OR_INVALID_RISK_POLICY");
  return {passed:tests.length,tests,example:decide(fixture())};
}
console.log(JSON.stringify(selfTest(),null,2));
