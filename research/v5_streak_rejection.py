import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['date']=pd.to_datetime(d.time,unit='s',utc=True)
p=d.close.shift()
d['atr']=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1).shift().rolling(20).mean()
d['body']=np.sign(d.close-d.open)
signals=[]
for i in range(23,len(d)-5):
 if d.time.iloc[i+1]-d.time.iloc[i]!=900:continue
 b=d.body.iloc[i-2:i+1].values
 if not(np.all(b==1) or np.all(b==-1)):continue
 s=int(b[-1]);r=d.high.iloc[i]-d.low.iloc[i]
 if r<=0:continue
 wick=d.high.iloc[i]-max(d.open.iloc[i],d.close.iloc[i]) if s==1 else min(d.open.iloc[i],d.close.iloc[i])-d.low.iloc[i]
 a=d.atr.iloc[i]
 if wick/r<.4 or not np.isfinite(a) or a<=0:continue
 signals.append((i,s,float(a)))
split=pd.Timestamp('2026-07-21',tz='UTC')
def run(mode,oos):
 cash=peak=1000.;dd=0.;last=-1;wins=losses=fees=0.;n=0;days={}
 candidates=[(i,s,a) for i,s,a in signals if bool(d.date.iloc[i]>=split)==oos]
 for i,s,a in candidates:
  if i<=last:continue
  side=-s if mode=='fade' else s
  entry=float(d.open.iloc[i+1]);stop=entry-side*a;target=entry+side*1.5*a
  lot=np.floor(min(.2,cash*.01/(a*100))*100)/100
  if lot<.01:continue
  price=float(d.close.iloc[i+4]);end=i+4
  for j in range(i+1,i+5):
   if d.time.iloc[j]-d.time.iloc[j-1]!=900:end=j-1;price=float(d.close.iloc[end]);break
   if (d.low.iloc[j]<=stop if side==1 else d.high.iloc[j]>=stop):price=stop;end=j;break
   if (d.high.iloc[j]>=target if side==1 else d.low.iloc[j]<=target):price=target;end=j;break
  last=end
  gross=(price-entry)*side*100*lot
  fee=(.26+.60)*100*lot+7*lot
  cash+=gross-fee;peak=max(peak,cash);dd=max(dd,(peak-cash)/peak)
  wins+=max(0,gross);losses+=min(0,gross);fees+=fee;n+=1
  day=str(d.date.iloc[i].date());days[day]=days.get(day,0)+gross-fee
 return dict(opportunities=len(candidates),trades=n,gross_winners=round(wins,2),gross_losers=round(losses,2),costs=round(fees,2),net=round(cash-1000,2),max_drawdown_pct=round(dd*100,2),active_days=len(days),days_net_ge_50=sum(x>=50 for x in days.values()))
result={'rows':len(d),'split':'2026-07-21 UTC','assumptions':'3 same-direction bodies; terminal wick >=40% of candle; next open; stop 1 ATR20, target 1.5 ATR20, max 4 bars, stop first on ambiguous candle; risk 1% equity, lots floor 0.01 to 0.20; 100 oz/lot; spread .26/oz, slippage .30/oz each side, commission $7/lot round trip','results':{m:{'train':run(m,False),'oos':run(m,True)} for m in ('fade','continuation')}}
print(json.dumps(result,indent=2))
