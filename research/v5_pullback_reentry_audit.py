"""V5 trend-pullback research; local Eplanet CSV required, never publish private data."""
import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(20).mean().shift(1)
d['ema']=d.close.ewm(span=48,adjust=False).mean().shift(1)
d['slope']=d.ema-d.ema.shift(8)
cut=pd.Timestamp('2026-06-15',tz='UTC')
out=[]
for guard in (False,True):
    equity=1000.; busy=-1; trades=[]
    for i in range(65,len(d)-5):
        a=d.iloc[i]; p=d.iloc[i-1]
        if not np.isfinite(a.atr) or a.atr<=0:continue
        side=1 if a.slope>.35*a.atr and a.close>a.ema else (-1 if a.slope<-.35*a.atr and a.close<a.ema else 0)
        if not side:continue
        signal=(p.close<p.open and a.close>p.high and a.close>a.open) if side==1 else (p.close>p.open and a.close<p.low and a.close<a.open)
        if not signal or i<=busy:continue
        if guard and (a.high-a.low>1.8*a.atr or a.spread>30 or a.high-a.low<.35*a.atr):continue
        lots=min(.10,np.floor((max(equity,0)*.01/(max(1.2*a.atr,1)*100))/.01)*.01)
        if lots<.01:continue
        gross=side*(d.iloc[i+4].close-d.iloc[i+1].open)*100*lots
        cost=100*lots*(a.spread*.01+.10)+7*lots
        net=gross-cost;equity+=net;busy=i+4
        trades.append(dict(date=str(a['dt'])[:10],period='oos' if a['dt']>=cut else 'train',gross=float(gross),cost=float(cost),net=float(net),lots=float(lots)))
    for period in ('train','oos'):
        t=[x for x in trades if x['period']==period];eq=pk=1000.;dd=0;daily={}
        for x in t:
            eq+=x['net'];pk=max(pk,eq);dd=max(dd,pk-eq);daily[x['date']]=daily.get(x['date'],0)+x['net']
        out.append(dict(guard=guard,period=period,trades=len(t),gross_profit=round(sum(max(x['gross'],0) for x in t),2),gross_loss=round(sum(min(x['gross'],0) for x in t),2),costs=round(sum(x['cost'] for x in t),2),net=round(sum(x['net'] for x in t),2),max_closed_drawdown=round(dd,2),days_ge_50=sum(v>=50 for v in daily.values())))
print(json.dumps(out,indent=2))
