"""Reproduce V5 gap experiment. Input private CSV passed by user; never commit CSV."""
import sys,json,numpy as np,pandas as pd
D=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
D['date']=pd.to_datetime(D.time,unit='s',utc=True).dt.date
R=(D.high-D.low).shift().rolling(32,min_periods=32).median()
G=D.open-D.close.shift(); delay=D.time.diff().fillna(900)
S=np.where((delay>=1800)&(G.abs()>=.35*R)&(G.abs()<=2*R),np.sign(G),0)
SAFE=((D.high.shift()-D.low.shift())<=1.8*R)&(delay<=14400)
COST=.86; CONTRACT=100; cut=int(len(D)*.6)
def run(start,end,filtered):
 trades=[]; i=max(start,33)
 while i<min(end,len(D)-5):
  s=int(S[i]); r=R.iat[i]
  if not s or not np.isfinite(r) or (filtered and not SAFE.iat[i]): i+=1;continue
  entry=D.open.iat[i]; eq=1000+sum(t[1] for t in trades)
  lot=max(0,min(.2,np.floor((eq*.01)/(r*CONTRACT)*100)/100))
  if lot<.01:i+=1;continue
  pnl=None; jend=i+4
  for j in range(i,min(i+5,len(D))):
   if (s==1 and D.low.iat[j]<=entry-r) or (s==-1 and D.high.iat[j]>=entry+r):pnl=-r;jend=j;break
   if (s==1 and D.high.iat[j]>=entry+1.5*r) or (s==-1 and D.low.iat[j]<=entry-1.5*r):pnl=1.5*r;jend=j;break
  if pnl is None:pnl=s*(D.close.iat[jend]-entry)
  trades.append((str(D.date.iat[i]),(pnl-COST)*CONTRACT*lot,pnl*CONTRACT*lot,COST*CONTRACT*lot,lot))
  i=jend+1
 vals=np.array([t[1] for t in trades]); curve=np.r_[1000,1000+np.cumsum(vals)]
 daily={}
 for t in trades:daily[t[0]]=daily.get(t[0],0)+t[1]
 return dict(opportunities=int(np.count_nonzero(S[start:end])),trades=len(trades),gross=round(sum(t[2] for t in trades),2),cost=round(sum(t[3] for t in trades),2),net=round(sum(vals),2),max_closed_drawdown=round(float(np.max(np.maximum.accumulate(curve)-curve)),2),winning_trades=int(np.count_nonzero(vals>0)),days_50=int(sum(v>=50 for v in daily.values())),trading_days=len(set(D.date.iloc[start:end])),lot_min=min((t[4] for t in trades),default=None),lot_max=max((t[4] for t in trades),default=None))
print(json.dumps({'rows':len(D),'split':cut,'train':{'baseline':run(0,cut,False),'filter':run(0,cut,True)},'out_of_sample':{'baseline':run(cut,len(D),False),'filter':run(cut,len(D),True)}},indent=2))
