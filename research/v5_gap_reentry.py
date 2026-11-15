"""Reopening gap study. Python 3 stdlib. Input private Eplanet CSV, never committed."""
import csv,sys,json,statistics,datetime
from collections import defaultdict
def run(path):
 with open(path,newline="") as f:
  bars=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
 n=len(bars);tr=[]
 for i in range(1,n):
  p,b=bars[i-1],bars[i]
  tr.append(max(b["high"]-b["low"],abs(b["high"]-p["close"]),abs(b["low"]-p["close"])))
 atr=[None]*n
 for i in range(20,n):atr[i]=statistics.mean(tr[i-14:i])
 split=int(n*.7)
 def sim(side,filtered,start,end):
  eq=1000.;peak=eq;dd=0.;wins=losses=costs=0.;deals=opp=0;days=defaultdict(float);last=-100
  for i in range(max(start,22),min(end,n-5)):
   if i<=last+4:continue
   p,b=bars[i-1],bars[i]
   gap=b["open"]-p["close"]
   if b["time"]-p["time"]<1800 or atr[i-1] is None or abs(gap)<.7*atr[i-1]:continue
   opp+=1
   if filtered and abs(gap)<1.3*atr[i-1]:continue
   direction=(1 if gap>0 else -1)*(1 if side=="follow" else -1)
   distance=max(atr[i-1]*1.5,2.)
   lots=min(.1,max(0.,int((eq*.01/(distance*100))/.01)*.01))
   if lots<.01:continue
   gross=(bars[i+3]["close"]-b["open"])*direction*100*lots
   cost=(.86*100+7)*lots
   pnl=gross-cost;eq+=pnl;peak=max(peak,eq);dd=max(dd,peak-eq)
   if gross>=0:wins+=gross
   else:losses+=gross
   costs+=cost;deals+=1;last=i+3
   day=datetime.datetime.fromtimestamp(b["time"],datetime.timezone.utc).date().isoformat();days[day]+=pnl
  return dict(opportunities=opp,trades=deals,gross_wins=round(wins,2),gross_losses=round(losses,2),costs=round(costs,2),net=round(wins+losses-costs,2),max_drawdown_usd=round(dd,2),end_equity=round(eq,2),days_traded=len(days),days_net_ge_50=sum(v>=50 for v in days.values()))
 return {"hypothesis":"M15 reopening gaps after >=30min missing bar, threshold 0.7 previous ATR14; fade versus follow; 1.3 ATR filter","data_rows":n,"split_index":split,"cost_model":"0.26 spread + 0.60 slippage per ounce; $7 commission/lot; 100 oz/lot","caveats":"4-bar close-only exit; optimistic open fills; no intrabar stop, margin, stopout or broker session validation","results":{f'{s}_{"filtered" if fl else "baseline"}_{part}':sim(s,fl,lo,hi) for s in ["fade","follow"] for fl in [False,True] for part,lo,hi in [("train",0,split),("oos",split,n)]}}
if __name__=="__main__":print(json.dumps(run(sys.argv[1]),indent=2))
