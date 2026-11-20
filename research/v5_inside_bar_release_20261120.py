import pandas as pd, numpy as np, json, hashlib, argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--csv",required=True);p.add_argument("--out",default="v5_inside_bar_release_results.json");a=p.parse_args()
P=Path(a.csv);d=pd.read_csv(P).sort_values("time").drop_duplicates("time").reset_index(drop=True)
d["date"]=pd.to_datetime(d.time,unit="s",utc=True).dt.strftime("%Y-%m-%d")
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
atr=tr.shift(1).rolling(64,min_periods=64).median()
imp=(d.close.shift(2)-d.open.shift(2)).abs()>1.25*atr.shift(2)
inside=(d.high.shift(1)<d.high.shift(2))&(d.low.shift(1)>d.low.shift(2))
side=np.sign(d.close.shift(2)-d.open.shift(2))
release=np.where((side>0)&(d.close>d.high.shift(1)),1,np.where((side<0)&(d.close<d.low.shift(1)),-1,0))
signal=imp&inside&(release!=0)&((d.high-d.low)<2.5*atr)
split=int(len(d)*.6);rows=[];opp={"train":0,"holdout":0};lastend=-1
for i in range(70,len(d)-7):
 if not signal.iloc[i]:continue
 seg="train" if i<split else "holdout";opp[seg]+=1
 if i<=lastend:continue
 s=int(release[i]);entry=float(d.open.iloc[i+1]);dist=float(np.clip(atr.iloc[i],2.5,12))
 if not np.isfinite(dist):continue
 stop=entry-s*dist;target=entry+s*dist*1.6;end=i+6;exitprice=float(d.close.iloc[end]);reason="time"
 for j in range(i+1,i+7):
  if (d.low.iloc[j]<=stop if s==1 else d.high.iloc[j]>=stop):end=j;exitprice=stop;reason="stop";break
  if (d.high.iloc[j]>=target if s==1 else d.low.iloc[j]<=target):end=j;exitprice=target;reason="target";break
 rows.append(dict(i=i,end=end,segment=seg,date=d.date.iloc[i+1],side=s,entry=entry,exit=exitprice,dist=dist,reason=reason));lastend=end
out={}
for seg in ("train","holdout"):
 out[seg]={"opportunities":opp[seg]}
 for guard in (False,True):
  equity=1000.;peak=1000.;dd=0.;gross=fees=0.;daily={};n=0;blocked=0;win=0
  for t in rows:
   if t["segment"]!=seg:continue
   if guard and daily.get(t["date"],0)<=-15:blocked+=1;continue
   risk=min(10,equity*.01);lot=min(.1,np.floor(risk/(t["dist"]*100)*100)/100)
   if lot<.01:blocked+=1;continue
   pnl=t["side"]*(t["exit"]-t["entry"])*100*lot;fee=87*lot;net=pnl-fee
   gross+=pnl;fees+=fee;equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity);n+=1;win+=net>0;daily[t["date"]]=daily.get(t["date"],0)+net
  out[seg]["guard" if guard else "base"]={"trades":n,"gross":round(gross,2),"fees":round(fees,2),"net":round(gross-fees,2),"max_closed_drawdown":round(dd,2),"wins":win,"blocked":blocked,"days_ge_50":sum(x>=50 for x in daily.values()),"days_total":d.iloc[:split].date.nunique() if seg=="train" else d.iloc[split:].date.nunique(),"active_days":len(daily)}
result={"hypothesis":"impulse inside bar directional release","sha256":hashlib.sha256(P.read_bytes()).hexdigest(),"candles":len(d),"split":split,"assumptions":{"round_trip_usd_per_lot":87,"contract_oz_per_lot":100,"max_risk_usd":10,"stop_first":True,"max_hold_bars":6,"min_lot":.01,"max_lot":.1},"results":out}
Path(a.out).write_text(json.dumps(result,indent=2,default=int));print(json.dumps(result,indent=2,default=int))
