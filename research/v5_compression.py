"""Research only. Private Eplanet CSV stays local. Run: python research/v5_compression.py /path/to/Eplanet_M15_20251105_20261105_merged.csv"""
import sys,json
import numpy as np,pandas as pd
d=pd.read_csv(sys.argv[1]);d["dt"]=pd.to_datetime(d.time,unit="s",utc=True)
p=d.close.shift();tr=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1)
d["atr"]=tr.shift(1).rolling(48).median()
hi=d.high.shift(2).rolling(6).max();lo=d.low.shift(2).rolling(6).min()
w=hi-lo
d["sig"]=np.where((w<2.6*d.atr)&(d.close.shift(1)>hi),1,np.where((w<2.6*d.atr)&(d.close.shift(1)<lo),-1,0))
cut=int(len(d)*.7);threshold=float(np.nanquantile(d.atr.iloc[:cut],.50))
def run(start,end,reverse=False,filtered=False):
 eq=1000.;peak=eq;dd=0.;win=loss=costs=0.;trades=opps=0;daily={};i=max(start,60)
 while i<end-9:
  s=int(d.sig.iloc[i]);atr=float(d.atr.iloc[i])
  if s==0 or not np.isfinite(atr):i+=1;continue
  opps+=1
  if filtered and atr>threshold:i+=1;continue
  direction=s*(-1 if reverse else 1);entry=float(d.open.iloc[i]);dist=max(atr*.8,1.)
  lot=np.floor(min(.1,eq*.01/(dist*100))/.01)*.01
  if lot<.01:i+=1;continue
  stop=entry-direction*dist;target=entry+direction*1.4*dist
  exitp=float(d.close.iloc[i+8]);j=i+8
  for k in range(i,i+9):
   h=float(d.high.iloc[k]);l=float(d.low.iloc[k])
   hs=l<=stop if direction==1 else h>=stop
   ht=h>=target if direction==1 else l<=target
   if hs or ht:exitp=stop if hs else target;j=k;break
  fee=lot*(100*(.26+.60)+7)
  pnl=(exitp-entry)*direction*100*lot-fee
  eq+=pnl;peak=max(peak,eq);dd=max(dd,peak-eq)
  win+=max(pnl,0);loss+=min(pnl,0);costs+=fee;trades+=1
  day=str(d.dt.iloc[j].date());daily[day]=daily.get(day,0)+pnl
  i=j+1
 return dict(opportunities=int(opps),trades=int(trades),positive_net_trade_sum=round(win,2),negative_net_trade_sum=round(loss,2),estimated_cost=round(costs,2),net=round(eq-1000,2),max_closed_equity_drawdown=round(dd,2),days_ge_50=sum(v>=50 for v in daily.values()),days_with_trades=len(daily),end_equity=round(eq,2))
result={"rows":len(d),"split":str(d.dt.iloc[cut]),"assumptions":"100 oz/lot; 0.26 spread and 0.60 roundtrip slippage per ounce; $7/lot commission; no margin stopout or tick replay; 1% equity sizing; 0.01 minimum lot; worst-case stop first if both touched","results":{}}
for a,b,label in [(60,cut,"train"),(cut,len(d),"test")]:
 for reverse in (False,True):
  for filtered in (False,True):
   result["results"][f'{label}_{"reverse" if reverse else "breakout"}_{"filtered" if filtered else "plain"}']=run(a,b,reverse,filtered)
print(json.dumps(result,indent=2))
