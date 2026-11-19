# Research-only; private CSV stays local. No broker connection.
import pandas as pd, numpy as np
d=pd.read_csv("Eplanet_M15_20251105_20261105_merged.csv").sort_values("time").drop_duplicates("time").reset_index(drop=True)
a=(d.high-d.low).rolling(20).mean().shift(1)
ma=d.close.rolling(40).mean().shift(1)
t=np.sign(d.close.shift(3)-d.close.shift(43))
r=np.where(t>0,(d.close.shift(2)<d.open.shift(2))&(d.close.shift(1)<d.open.shift(1)),(d.close.shift(2)>d.open.shift(2))&(d.close.shift(1)>d.open.shift(1)))
c=np.where(t>0,(d.close>d.open)&(d.close>d.high.shift(1)),(d.close<d.open)&(d.close<d.low.shift(1)))
v=(t!=0)&r&c&(abs(d.close.shift(3)-d.close.shift(43))>2*a)&(abs(d.close-ma)>.3*a)&(a>0)&(d.time.diff().fillna(900)==900)
def run(start,end,guard=False):
 eq=peak=1000.;gross=fees=dd=0.;opp=trades=wins=0;days={};next_i=start
 for i in range(max(50,start),min(end-9,len(d)-9)):
  if not v.iloc[i] or i<next_i:continue
  opp+=1; atr=float(a.iloc[i]); side=int(t.iloc[i]);stop=max(2.,min(12.,1.2*atr))
  if guard and (atr>8 or abs(d.close.iloc[i]-ma.iloc[i])>3*atr):continue
  entry=float(d.open.iloc[i+1]);lot=min(.15,max(.01,np.floor(eq*.0075/(stop*100)*100)/100))
  if eq<100 or lot*100*stop>eq*.03:continue
  price=float(d.close.iloc[i+8]);exit_i=i+8
  for j in range(i+1,i+9):
   b=d.iloc[j];sl=entry-side*stop;tp=entry+side*1.8*stop
   if (b.low<=sl if side>0 else b.high>=sl):price=sl;exit_i=j;break
   if (b.high>=tp if side>0 else b.low<=tp):price=tp;exit_i=j;break
  pnl=(price-entry)*side*100*lot;fee=lot*100*.60
  gross+=pnl;fees+=fee;eq+=pnl-fee;peak=max(peak,eq);dd=max(dd,peak-eq)
  wins+=int(pnl-fee>0);trades+=1
  day=str(pd.to_datetime(d.time.iloc[i],unit="s",utc=True).date());days[day]=days.get(day,0)+pnl-fee
  next_i=exit_i+1
 return dict(opportunities=opp,trades=trades,wins=wins,gross=round(gross,2),cost=round(fees,2),net=round(gross-fees,2),drawdown=round(dd,2),days_ge_50=sum(x>=50 for x in days.values()),active_days=len(days))
s=int(len(d)*.6)
print("train",run(0,s));print("oos",run(s,len(d)));print("oos_guard",run(s,len(d),True))
