'use strict';
// Pure offline model. No broker, networking, persistence or execution adapter.
const Cabin = (() => {
 const pages=['نمای اصلی','نمودار و MT5','معاملات و سفارش‌ها','سرمایه و خطر','مرکز تصمیم AI','آزمایشگاه و گزارش‌ها','ویندوز و موبایل','ابزارهای شخصی'];
 const initial=()=>({terminal:'UNKNOWN',broker_demo:'UNKNOWN',engine:'UNKNOWN',data_fresh:'UNKNOWN',execution_armed:false,observed:0,emergency:false,reconciled:false,mode:'manual',riskLimit:null,costsKnown:false,modelHash:null});
 const fixture=()=>({...initial(),terminal:'OK',broker_demo:'OK',engine:'OK',data_fresh:'OK',observed:10000,reconciled:true,riskLimit:0.03,costsKnown:true,modelHash:'fixture-only-not-trained'});
 function gate(s,now){
  const reasons=[];
  for(const key of ['terminal','broker_demo','engine','data_fresh'])if(s[key]!=='OK')reasons.push(key+':UNKNOWN_OR_UNHEALTHY');
  if(!Number.isFinite(now)||!Number.isFinite(s.observed)||now<s.observed||now-s.observed>5000)reasons.push('STALE_OR_INVALID_TIME');
  if(s.emergency!==false)reasons.push('EMERGENCY');
  if(s.reconciled!==true)reasons.push('RECONCILIATION_REQUIRED');
  if(s.execution_armed!==true)reasons.push('DISARMED');
  if(!Number.isFinite(s.riskLimit)||s.riskLimit<=0||s.riskLimit>0.03)reasons.push('RISK_POLICY_UNRESOLVED');
  if(s.costsKnown!==true)reasons.push('COSTS_UNKNOWN');
  if(!['manual','semi','auto'].includes(s.mode))reasons.push('INVALID_MODE');
  if(s.mode!=='manual'&&!s.modelHash)reasons.push('MODEL_UNVERIFIED');
  return {eligible:reasons.length===0,reasons};
 }
 function transition(s,event){
  const n={...s};
  if(event==='disconnect'){n.engine='OFFLINE';n.data_fresh='UNKNOWN';n.execution_armed=false;n.reconciled=false;}
  else if(event==='stale'){n.data_fresh='STALE';n.execution_armed=false;}
  else if(event==='unknown'){n.broker_demo='UNKNOWN';n.execution_armed=false;}
  else if(event==='stop'){n.emergency=true;n.execution_armed=false;}
  else if(event==='reconnect'){n.engine='OK';n.data_fresh='UNKNOWN';n.execution_armed=false;n.reconciled=false;}
  else if(event==='reconcile'){n.reconciled=true;n.execution_armed=false;}
  else if(event==='mobile_lost'){n.mobile='OFFLINE';} // independent engine/guardian
  else throw new Error('Unknown event');
  return n;
 }
 function navigate(index,action,count=pages.length){
  let next=index;if(action==='next'||action==='ArrowLeft'||action==='swipeRight')next++;else if(action==='previous'||action==='ArrowRight'||action==='swipeLeft')next--;else if(Number.isInteger(action))next=action;
  return Math.min(count-1,Math.max(0,next));
 }
 function swipe(dx,dy){return Math.abs(dx)>=60&&Math.abs(dx)>Math.abs(dy)*1.5?(dx>0?'swipeRight':'swipeLeft'):null;}
 function pnl(lots,move,contract,spread,commission){
  if(![lots,move,contract,spread,commission].every(Number.isFinite)||lots<=0||contract<=0||spread<0||commission<0)throw new Error('Invalid illustrative inputs');
  const gross=lots*move*contract,cost=lots*(spread*contract+commission);return {gross,cost,net:gross-cost,realized:0};
 }
 function simulator(){
  const seen=new Map(),journal=[];
  return {journal,submit(id,s,now,confirmed=false){
   if(typeof id!=='string'||!id.trim())return {accepted:false,reason:'INVALID_ID'};
   if(seen.has(id))return {...seen.get(id),duplicate:true};
   const g=gate(s,now);if(s.mode!=='auto'&&confirmed!==true)g.reasons.push('HUMAN_CONFIRMATION_REQUIRED');
   const result={accepted:g.reasons.length===0,reason:g.reasons.join(' | ')||'SIMULATED_ONLY',ordersSent:0};
   seen.set(id,result);journal.push({id,...result});return result;
  }};
 }
 return {pages,initial,fixture,gate,transition,navigate,swipe,pnl,simulator};
})();
if(typeof module!=='undefined')module.exports=Cabin;
