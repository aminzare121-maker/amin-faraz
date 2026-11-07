"""Frozen price-only candidate shared by runtime and chronological research."""
import hashlib
from pathlib import Path
from decimal import Decimal, ROUND_FLOOR
from .analysis import features
from .model import dec
from dataclasses import dataclass,asdict
import json

NAME='m15-price-breakout-v1'


def version():
    # Report-only calendar/forecast/provider modules are not trading dependencies.
    names=('strategy.py','analysis.py','model.py','risk.py','research.py','learning.py','experiments.py','runtime.py','mt5.py','execution.py','news.py','account_profiles.py','connectivity.py','capital_notice.py','research_context.py','demo_autonomy.py')
    names=(*names,'auto_sizing.py','profit_reinvestment.py','adaptive_exit.py','carry_policy.py','account_risk_diagnostics.py')
    return hashlib.sha256(b''.join(n.encode()+b'\0'+(Path(__file__).with_name(n).read_bytes() if Path(__file__).with_name(n).exists() else b'') for n in names)).hexdigest()


@dataclass(frozen=True)
class Candidate:
    family:str='breakout'
    lookback:int=20
    stop_multiple:float=1.5

    def validate(self):
        if self.family not in {'breakout','rejection','retest'} or self.lookback not in (20,40) or self.stop_multiple not in (1.5,2.0):
            raise ValueError('Unknown or unbounded candidate')
        return self

    @property
    def id(self):return f'{self.family}-{self.lookback}-{self.stop_multiple:g}'


def candidates():return [Candidate(f,n,1.5) for f in ('breakout','rejection','retest') for n in (20,40)]


def plan(bars,asof,candidate=None,*,price_asof=None):
    candidate=(candidate or Candidate()).validate()
    f=features(bars[-max(64,candidate.lookback+3):],asof,price_asof=price_asof)
    if not f.get('ready'):return None
    closed=[b for b in bars if b.get('final',False)]
    if len(closed)<candidate.lookback+2:return None
    prior,last=closed[-candidate.lookback-1:-1],closed[-1]
    high=max(dec(b['high']) for b in prior);low=min(dec(b['low']) for b in prior)
    close,opened=dec(last['close']),dec(last['open']);span=max(dec(last['high'])-dec(last['low']),dec('.01'))
    side=None
    if candidate.family=='breakout':
        side='buy' if close>high else 'sell' if close<low else None
        if side and (side=='buy')!=(f['trend']=='up'):side=None
    elif candidate.family=='rejection':
        if dec(last['low'])<low<close and (min(opened,close)-dec(last['low']))/span>=dec('.40'):side='buy'
        elif dec(last['high'])>high>close and (dec(last['high'])-max(opened,close))/span>=dec('.40'):side='sell'
    else:
        older=closed[-candidate.lookback-2:-2];previous=closed[-2]
        resistance=max(dec(b['high']) for b in older);support=min(dec(b['low']) for b in older)
        if dec(previous['close'])>resistance and dec(last['low'])<=resistance<close and close>opened:side='buy'
        elif dec(previous['close'])<support and dec(last['high'])>=support>close and close<opened:side='sell'
    if side is None:return None
    anchor=dec(closed[-1]['close'])
    distance=max(dec(f['range_atr_proxy'])*dec(candidate.stop_multiple),dec('0.5'))
    if candidate.family=='rejection':distance=max(anchor-dec(last['low']) if side=='buy' else dec(last['high'])-anchor,dec('.5'))+dec('.01')
    stop=(anchor-distance if side=='buy' else anchor+distance).quantize(Decimal('.01'))
    volatility=max(float(f['range_atr_proxy']),.01)
    history=closed[-20:];avg_range=sum(float(b['high'])-float(b['low']) for b in history)/20
    volumes=[float(b.get('tick_volume',1)) for b in history]
    vector=[(float(close)-float(closed[-6]['close']))/volatility,
            float(close-opened)/float(span),float((min(opened,close)-dec(last['low']))-(dec(last['high'])-max(opened,close)))/float(span),
            float(span)/max(avg_range,.01),volumes[-1]/max(sum(volumes)/len(volumes),1),
            (float(close)-float((high+low)/2))/volatility,1.0 if side=='buy' else -1.0]
    return {'side':side,'stop_loss':str(stop),'signal_time':closed[-1]['time'],'features':f,'learning_features':vector,'candidate':asdict(candidate)}


def artifact_hash(artifact):
    return hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate_artifact(artifact):
    if not isinstance(artifact,dict) or artifact.get('schema')!=3 or artifact.get('engine_sha256')!=version():raise ValueError('Artifact engine mismatch')
    Candidate(**artifact['candidate']).validate()
    from .adaptive_exit import VERSION as exit_version
    if artifact.get('threshold')!=.55 or artifact.get('max_holding_bars')!=0 or artifact.get('exit_policy')!=exit_version:raise ValueError('Unapproved artifact parameters')
    if artifact.get('model') is not None:
        from .learning import predict
        predict(artifact['model'],[0.0]*7)
    if len(json.dumps(artifact,allow_nan=False))>16000:raise ValueError('Artifact too large')
    return artifact


def approved_plan(bars,asof,artifact,*,price_asof=None):
    from .learning import predict
    validate_artifact(artifact)
    signal=plan(bars,asof,Candidate(**artifact['candidate']),price_asof=price_asof)
    signal_now=asof if price_asof is None else price_asof
    if signal and 0<=signal_now-(signal['signal_time']+900)<=900 and predict(artifact.get('model'),signal['learning_features'])>=artifact['threshold']:
        return signal
    return None


def size_and_target(candidate,entry,active,equity,spec,spread_slippage=None,commission=None,*,policy=None,exposure=None):
    from .auto_sizing import calculate
    return calculate(candidate,entry,active,equity,spec,policy=policy,exposure=exposure,
                     slippage=spread_slippage,commission=commission)['order']
