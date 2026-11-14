"""Run the session-drift hypothesis on PRIVATE Eplanet M15 CSV. Research only."""
import sys,json
from pathlib import Path
import pandas as pd,numpy as np
from strict_risk import lot_for_risk
d=pd.read_csv(sys.argv[1]).drop_duplicates('time').sort_values('time').reset_index(drop=True)
t=pd.to_datetime(d.time,unit='s',utc=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
atr=tr.ewm(alpha=1/14,adjust=False).mean()
sig=np.sign(d.close-d.close.shift(4))
ok=(t.dt.hour.between(13,15))&(atr>atr.shift(1).rolling(96,min_periods=96).median())&((d.close-d.close.shift(4)).abs()>.65*atr)&(d.spread*.01<=.8)
out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True);report={}
for label,start,end in [('development','2025-11-05','2026-05-01'),('holdout','2026-05-01','2026-11-06')]:
 eq=peak=1000.;dd=0.;rows=[];i=100;signals=reject=0
 while i<len(d)-10:
  if t.iat[i]<pd.Timestamp(start,tz='UTC'):i+=1;continue
  if t.iat[i]>=pd.Timestamp(end,tz='UTC'):break
  if not ok.iat[i] or sig.iat[i]==0:i+=1;continue
  signals+=1;j=i+1
  if d.time.iat[j]-d.time.iat[i]!=900:i+=1;continue
  side=int(sig.iat[i]);dist=max(1.5,.75*float(atr.iat[i]));slip=.3
  lot=lot_for_risk(eq,dist,slip,spread_buffer=.15)
  if not lot:reject+=1;i+=1;continue
  spread=float(d.spread.iat[j])*.01
  if spread>.8:i+=1;continue
  entry=float(d.open.iat[j])+(spread+slip if side==1 else -slip)
  stop=entry-side*dist;target=entry+side*1.5*dist;exitpx=None;why='timeout'
  for k in range(j,min(j+5,len(d))):
   sp=float(d.spread.iat[k])*.01
   op=float(d.open.iat[k])+(sp if side==-1 else 0)
   if k>j and d.time.iat[k]-d.time.iat[k-1]!=900:exitpx=op;why='gap';break
   adverse=float(d.low.iat[k]) if side==1 else float(d.high.iat[k])+sp
   favor=float(d.high.iat[k]) if side==1 else float(d.low.iat[k])+sp
   if side*(op-stop)<=0:exitpx=op;why='gap_stop';break
   if side*(adverse-stop)<=0:exitpx=stop;why='stop';break
   if side*(favor-target)>=0:exitpx=target;why='target';break
  if exitpx is None:exitpx=float(d.close.iat[k])+(float(d.spread.iat[k])*.01 if side==-1 else 0)
  pnl=side*(exitpx-side*slip-entry)*100*lot-10*lot
  eq+=pnl;peak=max(peak,eq);dd=max(dd,100*(peak-eq)/peak)
  rows.append(dict(entry_utc=str(t.iat[j]),exit_utc=str(t.iat[k]),side=side,lot=lot,net_usd=round(pnl,5),equity=round(eq,5),reason=why));i=k+1
 pd.DataFrame(rows).to_csv(out/f'{label}_ledger.csv',index=False)
 daily={}
 for r in rows:daily[r['exit_utc'][:10]]=daily.get(r['exit_utc'][:10],0)+r['net_usd']
 report[label]=dict(signals=signals,risk_rejected=reject,trades=len(rows),net_usd=round(eq-1000,2),drawdown_pct=round(dd,2),winners=sum(r['net_usd']>0 for r in rows),days_ge_50=sum(x>=50 for x in daily.values()),active_days=len(daily))
(out/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
