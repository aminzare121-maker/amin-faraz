"""Eplanet V5: reopening gap fade; research only, no orders. Run with local CSV."""
import pandas as pd, numpy as np
from pathlib import Path
d=pd.read_csv("Eplanet_M15_20251105_20261105_merged.csv").sort_values("time").drop_duplicates("time").reset_index(drop=True)
d["atr"]=(d.high-d.low).shift(1).rolling(96).median()
d["gap"]=d.open-d.close.shift(1)
d["elapsed"]=d.time.diff()
cut=int(len(d)*.6)
def test(a,b,threshold,guard=0):
    i=max(98,a); eq=1000.; peak=eq; dd=0.; opp=0; trades=[]
    while i<b-5:
        r=d.iloc[i]; gap=r.gap; atr=r.atr
        if r.elapsed>1800 and r.elapsed<=259200 and np.isfinite(atr) and atr>0 and abs(gap)>=threshold*atr:
            opp+=1; direction=-np.sign(gap); entry=d.iloc[i+1].open
            stop_dist=max(atr,abs(gap)*.75)
            lot=np.floor(eq*.01/(stop_dist*100)*100)/100
            if lot<.01 or (guard and (abs(gap)<1.46*guard or abs(entry-r.open)>atr*.4)):
                i+=1; continue
            if any(d.iloc[j].elapsed!=900 for j in range(i+1,i+5)):
                i+=1; continue
            exitp=d.iloc[i+4].close
            for j in range(i+1,i+5):
                x=d.iloc[j]; stop=entry-direction*stop_dist
                if direction>0 and x.low<=stop: exitp=min(stop,x.open); break
                if direction<0 and x.high>=stop: exitp=max(stop,x.open); break
            gross=direction*(exitp-entry)*lot*100
            cost=1.46*lot*100
            eq+=gross-cost; peak=max(peak,eq); dd=max(dd,peak-eq)
            trades.append((int(r.time),gross,cost,gross-cost))
            i+=5
        else: i+=1
    return {"opportunities":opp,"trades":len(trades),"gross":round(sum(t[1] for t in trades),2),"cost":round(sum(t[2] for t in trades),2),"net":round(sum(t[3] for t in trades),2),"max_closed_drawdown":round(dd,2)}
if __name__=="__main__":
    ranking=sorted([(test(0,cut,t)["net"],t) for t in [.5,1,1.5,2]],reverse=True)
    threshold=ranking[0][1]
    print("training",ranking,"chosen",threshold)
    print("OOS signal",test(cut,len(d),threshold))
    print("OOS cost guard",test(cut,len(d),threshold,3))
