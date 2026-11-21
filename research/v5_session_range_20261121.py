import pandas as pd, numpy as np, json, sys
from pathlib import Path
p=Path(sys.argv[1])
d=pd.read_csv(p).sort_values('time').drop_duplicates('time').reset_index(drop=True)
t=pd.to_datetime(d.time,unit='s',utc=True)
d['day']=t.dt.date; d['hour']=t.dt.hour
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(20).mean().shift(1)
days=sorted(d.day.unique()); split=int(len(days)*.6)
def run(subset,protect):
 eq=1000.;peak=eq;dd=gp=gl=cost=0.;n=opp=skip=0;daily={}
 for day in subset:
  z=d[d.day==day];base=z[(z.hour>=6)&(z.hour<8)];trade=z[(z.hour>=8)&(z.hour<12)]
  if len(base)<6 or len(trade)<5:continue
  hi=base.high.max();lo=base.low.min();width=hi-lo
  if width<=0:continue
  for i in trade.index[:-1]:
   side=1 if d.close.iat[i]>hi and d.close.iat[i-1]<=hi else (-1 if d.close.iat[i]<lo and d.close.iat[i-1]>=lo else 0)
   if not side:continue
   opp+=1;a=d.atr.iat[i]
   if not np.isfinite(a) or a<=0:break
   stop=max(a,width*.5);lot=np.floor((eq*.01/(stop*100))*100)/100
   if lot<.01:skip+=1;break
   lot=min(lot,.2);oz=lot*100;entry=d.open.iat[i+1];end=min(i+5,trade.index[-1]);out=d.close.iat[end]
   if protect:
    sl=entry-side*stop
    for k in range(i+1,end+1):
     if (side==1 and d.low.iat[k]<=sl) or (side==-1 and d.high.iat[k]>=sl):out=sl;break
   raw=side*(out-entry)*oz;fee=.45*oz;pnl=raw-fee
   eq+=pnl;peak=max(eq,peak);dd=max(dd,peak-eq);gp+=max(0,raw);gl+=min(0,raw);cost+=fee;n+=1;daily[str(day)]=pnl
   break
 return dict(opportunities=int(opp),trades=int(n),skipped_min_lot=int(skip),gross_profit=round(gp,2),gross_loss=round(gl,2),estimated_cost=round(cost,2),net=round(eq-1000,2),max_closed_drawdown=round(dd,2),days_net_ge_50=int(sum(v>=50 for v in daily.values())),days_evaluated=int(len(subset)),days_traded=int(len(daily)))
r={'rows':int(len(d)),'assumptions':'100oz/lot; 0.01 minimum; 1% risk; estimated $0.45/oz round trip; UTC; OHLC only','train':{'signal':run(days[:split],False),'risk_guard':run(days[:split],True)},'out_of_sample':{'signal':run(days[split:],False),'risk_guard':run(days[split:],True)}}
print(json.dumps(r,indent=2))
