import pandas as pd,numpy as np,json,sys,hashlib
from pathlib import Path
p=Path(sys.argv[1]);d=pd.read_csv(p).sort_values('time').drop_duplicates('time').reset_index(drop=True)
t=d.time.to_numpy();o=d.open.to_numpy();c=d.close.to_numpy();h=d.high.to_numpy();l=d.low.to_numpy();v=d.tick_volume.to_numpy();n=len(d)
r=pd.Series(c).diff();ac=r.shift(1).rolling(64,min_periods=64).corr(r.shift(2)).to_numpy()
atr=pd.Series(h-l).rolling(32,min_periods=32).median().to_numpy();medvol=pd.Series(v).rolling(64,min_periods=64).median().to_numpy()
side=np.where(ac>.18,np.sign(c-np.roll(c,1)),np.where(ac<-.18,-np.sign(c-np.roll(c,1)),0))
valid=(np.abs(ac)>.18)&(np.abs(c-np.roll(c,1))>.35*atr)&(np.abs(c-np.roll(c,1))<1.6*atr)&(side!=0)
risk=(v>=.65*medvol)&((h-l)<1.8*atr)&(atr<12)
cut=int(n*.6)
def run(a,b,guard):
 eq=1000.;peak=eq;dd=0;tr=[];i=max(a,70);opp=0
 while i<b-5:
  if valid[i] and np.isfinite(ac[i]) and np.all(np.diff(t[i:i+6])==900):
   opp+=1
   if not guard or risk[i]:
    entry=o[i+1];exitp=o[i+5];stopdist=max(2*atr[i],1)
    lot=np.floor(min(.10,max(.01,eq*.005/(100*stopdist)))*100)/100
    if lot*100*stopdist<=eq*.012:
     gross=(exitp-entry)*side[i]*100*lot;cost=.86*100*lot
     eq+=gross-cost;peak=max(peak,eq);dd=max(dd,peak-eq)
     tr.append((int(t[i+1]),gross,cost,lot));i+=5;continue
  i+=1
 days=len(set(pd.to_datetime(t[a:b],unit='s',utc=True).date));daily={}
 for stamp,g,cost,lot in tr:
  day=str(pd.to_datetime(stamp,unit='s',utc=True).date());daily[day]=daily.get(day,0)+g-cost
 return dict(opportunities=opp,trades=len(tr),gross=round(sum(x[1] for x in tr),2),cost=round(sum(x[2] for x in tr),2),net=round(eq-1000,2),max_closed_drawdown=round(dd,2),days=days,days_ge_50=sum(z>=50 for z in daily.values()),active_days=len(daily),lot_min=min((x[3] for x in tr),default=None),lot_max=max((x[3] for x in tr),default=None))
res=dict(hypothesis='rolling return autocorrelation selects continuation vs reversal; four-bar fixed exit',rows=n,cut=cut,train={k:run(70,cut,k=='guard') for k in ['signal','guard']},oos={k:run(cut,n,k=='guard') for k in ['signal','guard']},data_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),assumptions='0.86 USD per oz round trip; 100 oz/lot; fixed 4 bar exit; no intrabar stops; illustrative execution, not broker fills')
print(json.dumps(res,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
