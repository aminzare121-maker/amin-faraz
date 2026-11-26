/** Research-only decision core; no broker connection or order sending. */
export function decide(input) {
  const no=(reason,extra={})=>({mode:"SHADOW_ONLY",action:"NO_TRADE",reason,...extra});
  const finite=x=>typeof x==="number"&&Number.isFinite(x);
  const n=(x,min=0)=>finite(x)&&x>=min;
  const positive=x=>n(x)&&x>0;
  const str=x=>typeof x==="string"&&x.length>0;
  const {now,symbol,opportunityId,registry,signals,history,ledger,market,account,policy,preflight}=input??{};
  if(!n(now)||!str(symbol)||!str(opportunityId)||!Array.isArray(registry)||registry.length!==3||!Array.isArray(signals)||!Array.isArray(history)||!Array.isArray(ledger))return no("INVALID_INPUT");
  if(!registry.every(e=>str(e.id)&&str(e.version)&&str(e.family))||new Set(registry.map(e=>e.id)).size!==3)return no("INVALID_ENGINE_REGISTRY");
  const p=policy??{};
  if(!Number.isInteger(p.minSamples)||p.minSamples<2||!positive(p.maxAgeMs)||!positive(p.maxHistoryAgeMs)||!n(p.penalty)||!positive(p.minEdgeR)||!n(p.minGapR)||!Number.isInteger(p.minFamilies)||p.minFamilies<1||p.minFamilies>3||!positive(p.maxRiskFraction)||p.maxRiskFraction>1||!positive(p.maxSpread)||!positive(p.minMarginLevel)||!n(p.minFreeMargin)||!Number.isInteger(p.maxPositions)||p.maxPositions<1)return no("MISSING_OR_INVALID_RISK_POLICY");
  if(!market||market.symbol!==symbol||!n(market.asOf)||market.asOf>now||now-market.asOf>p.maxAgeMs||!positive(market.bid)||!positive(market.ask)||market.ask<market.bid||market.newsKnown!==true||typeof market.newsBlocked!=="boolean"||typeof market.sessionOpen!=="boolean"||!Array.isArray(market.bars))return no("MARKET_NOT_VERIFIED");
  if(!market.sessionOpen||market.newsBlocked||market.ask-market.bid>p.maxSpread)return no("MARKET_RISK_GATE");
  const bars=market.bars;
  if(bars.length<24||!bars.every((b,i)=>n(b.closedAt)&&b.closedAt<=market.asOf&&(i===0||b.closedAt>bars[i-1].closedAt)&&positive(b.close)&&positive(b.high)&&positive(b.low)&&b.low<=b.close&&b.high>=b.close))return no("INVALID_OR_FUTURE_BARS");
  const w=bars.slice(-24), ranges=w.map((b,i)=>i===0?b.high-b.low:Math.max(b.high-b.low,Math.abs(b.high-w[i-1].close),Math.abs(b.low-w[i-1].close)));
  const avg=a=>a.reduce((s,v)=>s+v,0)/a.length;
  const atr=avg(ranges.slice(-12)), prior=avg(ranges.slice(0,12));
  if(!positive(atr)||!positive(prior))return no("INSUFFICIENT_VOLATILITY_DATA");
  const displacement=w.at(-1).close-w[0].close;
  const movement=w.slice(1).reduce((s,b,i)=>s+Math.abs(b.close-w[i].close),0);
  const efficiency=movement>0?Math.abs(displacement)/movement:0;
  const regime=atr>1.8*prior?"HIGH_VOL":efficiency>=0.45&&Math.abs(displacement)>2*atr?(displacement>0?"TREND_UP":"TREND_DOWN"):"RANGE";
  const high=Math.max(...w.slice(0,-1).map(b=>b.high)),low=Math.min(...w.slice(0,-1).map(b=>b.low));
  const structure=w.at(-1).close>high?"BREAK_UP":w.at(-1).close<low?"BREAK_DOWN":w.at(-1).high>high||w.at(-1).low<low?"REJECTED_BREAK":"INSIDE";
  const context={regime,structure,atr};
  if(!account||account.verified!==true||!n(account.asOf)||account.asOf>now||now-account.asOf>p.maxAgeMs||!positive(account.equity)||!n(account.freeMargin)||!n(account.openRisk)||!Number.isInteger(account.openPositions)||account.openPositions<0||!Number.isInteger(account.pendingPositions)||account.pendingPositions<0)return no("ACCOUNT_NOT_VERIFIED",context);
  if(account.openPositions+account.pendingPositions>=p.maxPositions||account.freeMargin<p.minFreeMargin)return no("PORTFOLIO_LIMIT",context);
  if(ledger.some(x=>x&&x.symbol===symbol&&x.opportunityId===opportunityId&&["RESERVED","OPEN","CLOSED","SENT"].includes(x.state)))return no("DUPLICATE_OPPORTUNITY",context);
  if(signals.length!==3||new Set(signals.map(s=>s.engineId)).size!==3)return no("MISSING_OR_DUPLICATE_SIGNALS",context);
  const valid=registry.map(e=>({e,s:signals.find(s=>s.engineId===e.id)}));
  if(valid.some(({e,s})=>!s||s.version!==e.version||s.symbol!==symbol||s.opportunityId!==opportunityId||!str(s.signalId)||!["BUY","SELL","NEUTRAL"].includes(s.side)||s.confirmed!==true||!n(s.knownAt)||s.knownAt>now||now-s.knownAt>p.maxAgeMs||!n(s.expiresAt)||s.expiresAt<now))return no("STALE_OR_INVALID_ENGINE_SIGNAL",context);
  const eligible=history.filter(h=>h&&h.verified===true&&h.shadow===true&&h.costsVerified===true&&h.symbol===symbol&&h.regime===regime&&n(h.signalAt)&&n(h.closedAt)&&h.signalAt<=h.closedAt&&h.closedAt<now&&now-h.closedAt<=p.maxHistoryAgeMs&&finite(h.netUsd)&&positive(h.initialRiskUsd)&&str(h.signalId));
  const unique=new Set();
  for(const h of eligible){const k=JSON.stringify([h.engineId,h.version,h.signalId]);if(unique.has(k))return no("DUPLICATE_HISTORY",context);unique.add(k);}
  const diagnostics=[];
  for(const {e,s} of valid){
    const matching=eligible.filter(h=>h.engineId===e.id&&h.version===e.version&&h.side===s.side&&h.signalId!==s.signalId);
    const values=matching.map(h=>h.netUsd/h.initialRiskUsd);
    let edge=null,mean=null;
    if(values.length>=p.minSamples&&s.side!=="NEUTRAL"&&values.every(finite)){
      mean=avg(values);
      const sd=Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/(values.length-1));
      edge=mean-p.penalty*sd/Math.sqrt(values.length);
      if(!finite(edge))edge=null;
    }
    diagnostics.push({id:e.id,version:e.version,family:e.family,side:s.side,samples:values.length,meanR:mean,edgeR:edge,signalId:s.signalId});
  }
  const scores={BUY:0,SELL:0}, families={BUY:new Set(),SELL:new Set()};
  // A correlated family contributes at most its strongest positive edge, to only one side.
  for(const family of new Set(registry.map(e=>e.family))){
    const g=diagnostics.filter(d=>d.family===family&&d.edgeR!==null&&d.edgeR>0);
    const b=Math.max(0,...g.filter(d=>d.side==="BUY").map(d=>d.edgeR));
    const s=Math.max(0,...g.filter(d=>d.side==="SELL").map(d=>d.edgeR));
    if(b>s){scores.BUY+=b-s;families.BUY.add(family);}
    if(s>b){scores.SELL+=s-b;families.SELL.add(family);}
  }
  const side=scores.BUY>scores.SELL?"BUY":"SELL",opposite=side==="BUY"?"SELL":"BUY";
  const evidence={...context,scores,diagnostics};
  if(!finite(scores[side])||scores[side]<p.minEdgeR||scores[side]-scores[opposite]<=p.minGapR||families[side].size<p.minFamilies)return no("INSUFFICIENT_NET_EVIDENCE",evidence);
  // External broker-side read-only order_check and cost/risk calculator must supply candidates.
  // The manager never fabricates a price, stop, lot, margin or order authorization.
  if(!Array.isArray(preflight))return no("MISSING_BROKER_PREFLIGHT",evidence);
  const riskBudget=account.equity*p.maxRiskFraction-account.openRisk;
  const candidates=preflight.filter(c=>c&&c.symbol===symbol&&c.opportunityId===opportunityId&&c.side===side&&c.verified===true&&c.costsVerified===true&&c.orderCheckPassed===true&&n(c.checkedAt)&&c.checkedAt<=now&&now-c.checkedAt<=p.maxAgeMs&&n(c.expiresAt)&&c.expiresAt>=now&&positive(c.lot)&&positive(c.entry)&&positive(c.stop)&&((side==="BUY"&&c.stop<c.entry&&c.entry===market.ask)||(side==="SELL"&&c.stop>c.entry&&c.entry===market.bid))&&positive(c.maxLossUsd)&&c.maxLossUsd<=riskBudget&&n(c.costUsd)&&c.costUsd<=c.maxLossUsd&&positive(c.expectedGrossUsd)&&c.expectedGrossUsd>c.costUsd&&n(c.freeMarginAfter)&&c.freeMarginAfter>=p.minFreeMargin&&positive(c.marginLevelAfter)&&c.marginLevelAfter>=p.minMarginLevel);
  candidates.sort((a,b)=>(b.expectedGrossUsd-b.costUsd)/b.maxLossUsd-(a.expectedGrossUsd-a.costUsd)/a.maxLossUsd||a.maxLossUsd-b.maxLossUsd||a.lot-b.lot);
  if(!candidates.length)return no("NO_SAFE_BROKER_VALIDATED_SIZE",evidence);
  const c=candidates[0];
  return {mode:"SHADOW_ONLY",action:side,reason:"CONDITIONAL_RESEARCH_CANDIDATE",symbol,opportunityId,lot:c.lot,entry:c.entry,stop:c.stop,maxLossUsd:c.maxLossUsd,costUsd:c.costUsd,estimatedNetUsd:c.expectedGrossUsd-c.costUsd,expiresAt:Math.min(c.expiresAt,...signals.map(s=>s.expiresAt)),requiresAtomicReservation:true,ordersSent:0,...evidence};
}
