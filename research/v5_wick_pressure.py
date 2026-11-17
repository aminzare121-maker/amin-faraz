import pandas as pd, numpy as np, json
from pathlib import Path
import argparse
parser=argparse.ArgumentParser()
parser.add_argument("--csv",required=True)
args=parser.parse_args()
d=pd.read_csv(args.csv).sort_values("time").drop_duplicates("time").reset_index(drop=True)
rg=(d.high-d.low).clip(lower=.01); med=rg.rolling(32).median().shift(1)
up=((d.close-d.low)/rg>=.8)&((d.open-d.low)/rg>=.55)&(rg>=.8*med)&(rg<=2.2*med)
dn=((d.high-d.close)/rg>=.8)&((d.high-d.open)/rg>=.55)&(rg>=.8*med)&(rg<=2.2*med)
sig=up|dn; direction=np.where(up,1,-1)
cut=int(len(d)*.6)
def run(start,end,guard=False):
 eq=1000.;peak=eq;dd=0.;gross=cost=0.;n=0;wins=0;days={};opps=int(sig.iloc[start:end-2].sum());skips=0;lots=[];max_intrabar_dd=0.
 i=max(start,33)
 while i<end-2 and eq>0:
  if not sig.iloc[i]:i+=1;continue
  risk=float(med.iloc[i])*1.15
  if guard and (d.spread.iloc[i]>d.spread.iloc[i-96:i].median()*1.15 or rg.iloc[i]>1.5*med.iloc[i]):skips+=1;i+=1;continue
  risk_budget=max(0,eq)*(.0075 if guard else .015)
  lot=min(.10,np.floor(risk_budget/(risk*100)/.01)*.01)
  if lot<.01:skips+=1;i+=1;continue
  ent=float(d.open.iloc[i+1]);side=int(direction[i]);stop=ent-side*risk
  exit_price=float(d.close.iloc[i+2]);intrabar=0
  for j in (i+1,i+2):
   adverse=(ent-float(d.low.iloc[j])) if side==1 else (float(d.high.iloc[j])-ent)
   intrabar=max(intrabar,adverse*lot*100)
   if (side==1 and d.low.iloc[j]<=stop) or (side==-1 and d.high.iloc[j]>=stop):exit_price=stop;break
  g=(exit_price-ent)*side*lot*100;c=1.46*lot*100
  gross+=g;cost+=c;eq+=g-c;peak=max(peak,eq);dd=max(dd,peak-eq);max_intrabar_dd=max(max_intrabar_dd,peak-(eq-(g-c))+intrabar)
  n+=1;wins+=g-c>0;lots.append(lot)
  day=pd.to_datetime(d.time.iloc[i],unit="s",utc=True).strftime("%Y-%m-%d");days[day]=days.get(day,0)+g-c
  i+=3
 return dict(opportunities=opps,trades=n,gross=round(gross,2),cost=round(cost,2),net=round(gross-cost,2),max_closed_drawdown=round(dd,2),max_intrabar_drawdown_estimate=round(max_intrabar_dd,2),wins=wins,losses=n-wins,active_days=len(days),days_ge_50=sum(v>=50 for v in days.values()),skipped=skips,lot_min=round(min(lots),2) if lots else None,lot_max=round(max(lots),2) if lots else None,ending_equity=round(eq,2))
r={"hypothesis":"wick rejection pressure, next two-bar follow-through; no breakout or volume condition","rows":len(d),"split":cut,"train":run(33,cut),"holdout_base":run(cut,len(d)),"holdout_guard":run(cut,len(d),True),"cost":"estimated $1.46 per ounce roundtrip including spread, fees and slippage; 100 oz/lot","limitations":"OHLC stop-first, no broker execution validation; intrabar DD is conservative estimate based on bar extremes; zero real orders"}
print(json.dumps(r,indent=2,default=lambda x:x.item()))
