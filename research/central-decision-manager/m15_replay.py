"""OHLC research only: three M15 signals and a single-position adaptive manager.
No broker API, orders, or actual tick replay. Input archives are private and not bundled.
"""
import argparse, csv, math, statistics as st, zipfile
from collections import defaultdict, deque

CAPITAL=200.; LOT=.03; OZ=3.; SLIP=.30; LEVERAGE=500.; STOP=5.; PAD=1.; STEP=3.
LOCK={'Twin':7.,'SAR':3.,'MA':10.}

def read_zip(path,name):
    with zipfile.ZipFile(path) as z:
        return list(csv.DictReader(z.read(name).decode('utf-8-sig').splitlines()))

def load(bars_zip,twin_zip):
    bars=[(int(r['time']),*[float(r[k]) for k in ('open','high','low','close')],float(r['spread'])*.01) for r in read_zip(bars_zip,'eplanet_m15_requested_year.csv')]
    native={int(r['bar_open_native']):(int(r['long']),int(r['short'])) for r in read_zip(twin_zip,'native_buffers.csv')}
    assert all(bars[i][0]<bars[i+1][0] for i in range(len(bars)-1))
    return bars,native

def sar_dots(b):
    # Wilder-style research implementation; MT5 native buffer parity not verified.
    side=1 if b[1][4]>=b[0][4] else -1
    sar=min(b[0][3],b[1][3]) if side==1 else max(b[0][2],b[1][2]); ep=max(b[0][2],b[1][2]) if side==1 else min(b[0][3],b[1][3]); af=.02; dot=0
    out=[0,0]
    for i in range(2,len(b)):
        _,o,h,l,c,_=b[i]; nxt=sar+af*(ep-sar)
        if side==1:
            nxt=min(nxt,b[i-1][3],b[i-2][3])
            if l<nxt: side=-1; nxt=ep; ep=l; af=.02; dot=1
            else:
                if h>ep: ep=h; af=min(.20,af+.02)
                dot=dot+1 if dot else 0
        else:
            nxt=max(nxt,b[i-1][2],b[i-2][2])
            if h>nxt: side=1; nxt=ep; ep=h; af=.02; dot=1
            else:
                if l<ep: ep=l; af=min(.20,af+.02)
                dot=dot+1 if dot else 0
        sar=nxt; out.append(side if 1<=dot<=3 else 0)
    return out

def thresholds(b,method):
    cs=[x[4] for x in b]; out=[None]*len(b); a=2/22; z=2/101; e1=e2=cs[0]
    for i in range(1,len(b)):
        if i>=99:
            if method=='SMA': out[i]=(21*sum(cs[i-99:i])-100*sum(cs[i-20:i]))/79
            else: out[i]=((1-z)*e2-(1-a)*e1)/(a-z)
        e1=a*cs[i]+(1-a)*e1; e2=z*cs[i]+(1-z)*e2
    return out

def regime(b,i):
    if i<25:return 'WARMUP'
    w=b[i-24:i]; c=[x[4] for x in w]; r=[max(x[2]-x[3],abs(x[2]-b[i-25+j][4]),abs(x[3]-b[i-25+j][4])) for j,x in enumerate(w)]
    atr=st.mean(r[-12:]); prior=st.mean(r[:12]); move=sum(abs(y-x) for x,y in zip(c,c[1:])); delta=c[-1]-c[0]
    if atr>1.8*prior:return 'HIGH_VOL'
    if move and abs(delta)/move>=.45 and abs(delta)>2*atr:return 'UP' if delta>0 else 'DOWN'
    return 'RANGE'

class Book:
    def __init__(self,name,funded=True):
        self.name=name; self.funded=funded; self.balance=CAPITAL; self.pos=None; self.trades=[]; self.peak=CAPITAL; self.dd=0.; self.low=CAPITAL; self.reject=0; self.stopouts=0; self.max_margin=0.; self.min_free=CAPITAL
    def mark(self,p,spread):
        x=self.pos
        return x['side']*OZ*((p if x['side']==1 else p+spread)-x['entry']) if x else 0.
    def observe(self,p,sp):
        equity=self.balance+self.mark(p,sp); margin=self.pos['margin'] if self.pos else 0.
        self.peak=max(self.peak,equity); self.dd=max(self.dd,self.peak-equity); self.low=min(self.low,equity); self.min_free=min(self.min_free,equity-margin); self.max_margin=max(self.max_margin,margin)
    def close(self,p,sp,i,reason):
        x=self.pos; pnl=self.mark(p,sp)-OZ*SLIP; self.balance+=pnl
        self.trades.append((x['engine'],x['regime'],x['side'],x['i'],i,pnl,reason))
        self.pos=None; self.observe(p,sp)
        if reason=='stopout': self.stopouts+=1
    def enter(self,p,sp,i,engine,side,reg):
        if self.pos:return
        entry=p+sp+SLIP if side==1 else p-SLIP; margin=entry*OZ/LEVERAGE
        if self.funded and self.balance-OZ*(sp+SLIP)<margin:self.reject+=1;return
        self.pos={'engine':engine,'side':side,'entry':entry,'margin':margin,'best':0.,'stop':-STOP,'i':i,'regime':reg}
        self.observe(p,sp); self.advance(p,p,sp,i)
    def advance(self,p,q,sp,i):
        if not self.pos:return
        x=self.pos; m0=self.mark(p,sp); m1=self.mark(q,sp)
        floor=.5*x['margin']-self.balance if self.funded else -math.inf
        threshold=max(x['stop'],floor); reason='stopout' if floor>x['stop'] else 'stop'
        if m0<=threshold:
            self.close(p,sp,i,reason);return
        if m1<m0 and m1<=threshold:
            at=p+(q-p)*(threshold-m0)/(m1-m0); self.observe(at,sp);self.close(at,sp,i,reason);return
        x['best']=max(x['best'],m0,m1); best=x['best']; lock=LOCK[x['engine']]
        locked=lock+STEP*math.floor((best-lock-PAD+1e-10)/STEP) if best>=lock+PAD else -math.inf
        x['stop']=max(x['stop'],best-STOP,locked);self.observe(q,sp)
    def summary(self,start,end):
        t=self.trades
        return {'net':round(self.balance-CAPITAL,2),'final':round(self.balance,2),'trades':len(t),'wins':sum(x[5]>0 for x in t),'dd':round(self.dd,2),'low':round(self.low,2),'rejected':self.reject,'stopouts':self.stopouts,'margin_peak':round(self.max_margin,2),'min_free':round(self.min_free,2)}

def replay(b,native,method,path):
    split=len(b)//2; sar=sar_dots(b); th=thresholds(b,method)
    shadow={e:Book(e,False) for e in LOCK}; base={e:Book(e) for e in LOCK}; manager=Book('manager'); books=[*shadow.values(),*base.values(),manager]; hist=defaultdict(lambda:deque(maxlen=100)); seen=defaultdict(int); ma_side=0; events=defaultdict(int)
    def collect():
        for e,book in shadow.items():
            for _,reg,side,_,_,pnl,_ in book.trades[seen[e]:]:hist[(e,reg,side)].append(pnl/STOP)
            seen[e]=len(book.trades)
    def event(signals,p,sp,i,reg):
        collect()
        for e,side in signals.items():
            events[e]+=1; shadow[e].enter(p,sp,i,e,side,reg)
            if i>=split:base[e].enter(p,sp,i,e,side,reg)
        if i<split or manager.pos or not signals:return
        scores={}
        for e,side in signals.items():
            a=hist[(e,reg,side)]
            if len(a)>=20:
                edge=st.mean(a)-1.96*st.stdev(a)/math.sqrt(len(a))
                if edge>0:scores[e]=(edge,side)
        if not scores:return
        e,(edge,side)=max(scores.items(),key=lambda x:x[1][0]); opp=max((v[0] for v in scores.values() if v[1]!=side),default=0.)
        if edge-opp>.1: manager.enter(p,sp,i,e,side,reg)
    for i,(ts,o,h,l,c,sp) in enumerate(b):
        if i<1:continue
        reg=regime(b,i); threshold=th[i]
        for book in books:book.advance(o,o,sp,i)
        signals={}; native_side=native.get(b[i-1][0],(0,0))
        if native_side==(1,0):signals['Twin']=1
        if native_side==(0,1):signals['Twin']=-1
        if sar[i-1]:signals['SAR']=sar[i-1]
        if threshold is not None:
            initial=1 if o>threshold else -1 if o<threshold else ma_side
            if ma_side and initial and initial!=ma_side:signals['MA']=initial
            ma_side=initial
        event(signals,o,sp,i,reg)
        if path=='HL': pts=[o,h,l,c]
        elif path=='LH': pts=[o,l,h,c]
        else:
            amp=float(path.split('_')[1]); up=min(h,o+amp); dn=max(l,o-amp); pts=[o,up,dn,up,dn,h,l,c]
        for p,q in zip(pts,pts[1:]):
            new=1 if threshold is not None and q>threshold else -1 if threshold is not None and q<threshold else ma_side
            if threshold is not None and ma_side and new!=ma_side and min(p,q)<=threshold<=max(p,q):
                for book in books:book.advance(p,threshold,sp,i)
                event({'MA':new},threshold,sp,i,reg)
                for book in books:book.advance(threshold,q,sp,i)
            else:
                for book in books:book.advance(p,q,sp,i)
            ma_side=new
        collect()
    for book in books:
        if book.pos:book.close(b[-1][4],b[-1][5],len(b)-1,'end')
    out=[]
    for book in [*base.values(),manager]:
        out.append({'method':method,'path':path,'engine':book.name,'eval_bars':len(b)-split,'signals_whole_year':events.get(book.name,''),**book.summary(split,len(b))})
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('bars_zip');p.add_argument('twin_zip');p.add_argument('--out',default='summary.csv');a=p.parse_args();b,n=load(a.bars_zip,a.twin_zip)
    rows=[r for m in ('SMA','EMA') for path in ('HL','LH','zigzag_1','zigzag_1.5') for r in replay(b,n,m,path)]
    with open(a.out,'w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print('bars',len(b),'native',len(n),'test starts',b[len(b)//2][0]);print(*rows,sep='\n')
if __name__=='__main__':main()
