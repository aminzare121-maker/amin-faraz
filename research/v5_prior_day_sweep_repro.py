# Research-only reproduction. Requires private Eplanet CSV locally; never trade live.
import pandas as pd
d=pd.read_csv("Eplanet_M15_20251105_20261105_merged.csv").sort_values("time").reset_index(drop=True)
d["date"]=pd.to_datetime(d.time,unit="s",utc=True).dt.date
prior=d.groupby("date").agg(hi=("high","max"),lo=("low","min")).shift()
d=d.join(prior.rename(columns={"hi":"prev_hi","lo":"prev_lo"}),on="date")
def test(start,end,guard=False):
 eq=peak=1000.;dd=gross=cost=0.;opportunities=0;trades=0;over50=0;used=set()
 for i in range(max(25,start),min(end,len(d)-5)):
  a=d.iloc[i]
  if a.date in used or pd.isna(a.prev_hi):continue
  side=1 if a.low<a.prev_lo and a.close>a.prev_lo else (-1 if a.high>a.prev_hi and a.close<a.prev_hi else 0)
  if not side:continue
  used.add(a.date);opportunities+=1
  atr=(d.high.iloc[i-14:i]-d.low.iloc[i-14:i]).mean()
  if guard and a.high-a.low>1.5*atr:continue
  entry=d.open.iloc[i+1];stop=max(2.,min(12.,atr*.8));lot=max(.01,min(.15,round(eq*.01/(stop*100),2)))
  price=d.close.iloc[i+4]
  for j in range(i+1,i+5):
   bar=d.iloc[j];sl=entry-side*stop;tp=entry+side*1.5*stop
   if (bar.low<=sl if side==1 else bar.high>=sl):price=sl;break
   if (bar.high>=tp if side==1 else bar.low<=tp):price=tp;break
  profit=(price-entry)*side*100*lot;fee=lot*100*.40
  gross+=profit;cost+=fee;eq+=profit-fee;peak=max(peak,eq);dd=max(dd,peak-eq);trades+=1
 return dict(opportunities=opportunities,trades=trades,gross=round(gross,2),cost=round(cost,2),net=round(gross-cost,2),drawdown=round(dd,2))
split=int(len(d)*.6)
print("train",test(0,split))
print("oos",test(split,len(d)))
print("oos_guard",test(split,len(d),True))
