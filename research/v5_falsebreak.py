"""Research-only failed-breakout test. Input: private Eplanet CSV, never committed."""
import sys,json,math
import pandas as pd,numpy as np
d=pd.read_csv(sys.argv[1]).sort_values('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
p=d.close.shift()
tr=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1)
d['atr']=tr.shift(1).rolling(48).median()
top=d.high.shift(1).rolling(96).max();bottom=d.low.shift(1).rolling(96).min()
d['sig']=np.where((d.high>top+.15*d.atr)&(d.close<top)&(d.close>bottom),-1,np.where((d.low<bottom-.15*d.atr)&(d.close>bottom)&(d.close<top),1,0))
cut=int(len(d)*.7)
def run(start,end,follow=False,filterrisk=False):
 eq=1000.;peak=eq;dd=0.;wins=losses=fees=0.;n=opps=0;daily={};i=max(start,100)
 while i<end-7:
  s=int(d.sig.iloc[i-1]);atr=float(d.atr.iloc[i-1])
  if s==0 or not np.isfinite(atr) or atr<=0:i+=1;continue
  opps+=1
  if filterrisk and d.high.iloc[i-1]-d.low.iloc[i-1]>1.5*atr:i+=1;continue
  side=-s if follow else s;entry=float(d.open.iloc[i]);dist=max(1.,.9*atr)
  lot=math.floor(min(.1,eq*.01/(100*dist))/.01+1e-9)*.01
  if lot<.01:i+=1;continue
  stop=entry-side*dist;target=entry+side*dist*1.5
  exitp=float(d.close.iloc[i+7]);j=i+7
  for k in range(i,i+8):
   h=float(d.high.iloc[k]);l=float(d.low.iloc[k])
   hs=l<=stop if side==1 else h>=stop
   ht=h>=target if side==1 else l<=target
   if hs or ht:exitp=stop if hs else target;j=k;break
  fee=lot*(100*(.26+.60)+7);gross=(exitp-entry)*side*100*lot
  eq+=gross-fee;peak=max(peak,eq);dd=max(dd,peak-eq)
  wins+=max(gross,0);losses+=min(gross,0);fees+=fee;n+=1
  day=str(d.dt.iloc[j].date());daily[day]=daily.get(day,0)+gross-fee;i=j+1
 return dict(opportunities=opps,trades=n,gross_winners=round(wins,2),gross_losers=round(losses,2),costs=round(fees,2),net=round(eq-1000,2),max_closed_equity_drawdown=round(dd,2),trade_days=len(daily),days_net_ge_50=sum(v>=50 for v in daily.values()))
result={'rows':len(d),'split_utc':str(d.dt.iloc[cut]),'assumptions':'100 oz/lot; 1% equity risk; 0.01 minimum lot; 0.26 spread + 0.60 roundtrip slippage per oz; $7/lot commission; stop first; no tick or margin stopout','results':{}}
for name,(a,b) in {'train':(0,cut),'holdout':(cut,len(d))}.items():
 result['results'][name]={}
 for follow in (False,True):
  for filt in (False,True):
   key=('follow' if follow else 'fade')+('_riskfilter' if filt else '')
   result['results'][name][key]=run(a,b,follow,filt)
print(json.dumps(result,indent=2))
