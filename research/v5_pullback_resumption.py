import pandas as pd,numpy as np,json,sys,hashlib
p=sys.argv[1];d=pd.read_csv(p).sort_values('time').drop_duplicates('time').reset_index(drop=True)
t=d.time.to_numpy();o=d.open.to_numpy();c=d.close.to_numpy();h=d.high.to_numpy();l=d.low.to_numpy();n=len(d)
ema=pd.Series(c).ewm(span=48,adjust=False).mean().to_numpy();slow=pd.Series(c).ewm(span=192,adjust=False).mean().to_numpy()
atr=pd.Series(h-l).rolling(32).median().to_numpy();rv=pd.Series(d.tick_volume).rolling(32).median().to_numpy()
trend=np.where(ema>slow,1,-1)
signal=np.zeros(n,dtype=int)
for i in range(200,n-1):
 s=trend[i];signal[i]=s if s*(c[i]-ema[i])>0 and s*(c[i-1]-ema[i-1])<=0 and s*(ema[i]-slow[i])>1.0*atr[i] and abs(c[i]-ema[i])<.75*atr[i] else 0
safe=((h-l)<1.35*atr)&(d.tick_volume.to_numpy()>.7*rv)&(atr<12)
cut=int(n*.6)
def run(a,b,guard):
 eq=1000.;peak=eq;dd=0;opp=0;tr=[];i=max(200,a)
 while i<b-5:
  if signal[i] and np.all(np.diff(t[i:i+6])==900):
   opp+=1
   if not guard or safe[i]:
    dist=max(1.5*atr[i],1);lot=np.floor(min(.10,eq*.007/(100*dist))*100)/100
    if lot>=.01 and lot*100*dist<=eq*.015:
     entry=o[i+1];ex=o[i+5];gross=(ex-entry)*signal[i]*100*lot;cost=.86*100*lot
     eq+=gross-cost;peak=max(peak,eq);dd=max(dd,peak-eq)
     tr.append((int(t[i+1]),gross,cost,lot));i+=5;continue
  i+=1
 daily={}
 for stamp,g,cost,lot in tr:
  day=str(pd.to_datetime(stamp,unit='s',utc=True).date());daily[day]=daily.get(day,0)+g-cost
 return dict(opportunities=opp,trades=len(tr),gross=round(sum(x[1] for x in tr),2),cost=round(sum(x[2] for x in tr),2),net=round(eq-1000,2),max_closed_drawdown=round(dd,2),active_days=len(daily),days_ge_50=sum(z>=50 for z in daily.values()),lot_min=min((x[3] for x in tr),default=None),lot_max=max((x[3] for x in tr),default=None))
res=dict(hypothesis='EMA48 recross in EMA48/192 trend after pullback',rows=n,split=cut,train={k:run(200,cut,k=='guard') for k in ['signal','guard']},oos={k:run(cut,n,k=='guard') for k in ['signal','guard']},sha256=hashlib.sha256(open(p,'rb').read()).hexdigest(),assumptions='100 oz/lot, $0.86/oz roundtrip, 4-bar exit, no intrabar execution, closed-equity drawdown only')
print(json.dumps(res,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
