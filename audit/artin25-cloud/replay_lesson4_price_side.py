"""Replay real lesson-four price-side examples. Evidence audit only; no broker access."""
from decimal import Decimal
import json,pathlib
SOURCE='322755df7d9bb32811f99529df5f71bb8081ef333c3566e8ecc3111c208173bb'
CASES=[
 dict(id='S4_SELL_NEGATIVE',seconds='2020.69',symbol='EURUSD.st',side='SELL',entry='1.17901',bid='1.17893',ask='1.17904',displayed_profit='-3'),
 dict(id='S4_SELL_POSITIVE',seconds='2228.79',symbol='EURUSD.st',side='SELL',entry='1.17901',bid='1.17886',ask='1.17897',displayed_profit='4'),
 dict(id='S4_BUY_NEGATIVE',seconds='2228.79',symbol='GBPUSD.st',side='BUY',entry='1.35691',bid='1.35671',ask='1.35682',displayed_profit='-20')
]
def sign(x):return (x>0)-(x<0)
def replay(case):
 entry,bid,ask=(Decimal(case[k]) for k in ('entry','bid','ask'))
 if ask<bid:raise ValueError('INVALID_QUOTE_ORDER')
 if case['side']=='SELL':delta=entry-ask;quote_side='ASK'
 elif case['side']=='BUY':delta=bid-entry;quote_side='BID'
 else:raise ValueError('UNKNOWN_SIDE')
 observed=sign(Decimal(case['displayed_profit']))
 return dict(case,quote_side=quote_side,predicted_sign=sign(delta),observed_sign=observed,pass_=sign(delta)==observed)
def main():
 results=[replay(c) for c in CASES]
 if not all(r['pass_'] for r in results):raise AssertionError('ACTUAL_TEACHER_EXAMPLE_MISMATCH')
 wrong=sign(Decimal(CASES[0]['entry'])-Decimal(CASES[0]['bid']))
 if wrong==sign(Decimal(CASES[0]['displayed_profit'])):raise AssertionError('EXAMPLE_NOT_DISCRIMINATIVE')
 output=dict(status='THREE_OBSERVED_EXAMPLE_SIGNS_REPLAYED',source_video_sha256=SOURCE,source_image_artifact=13699771519,results=results,wrong_sell_bid_control_rejected=True,blind_or_heldout_test=False,amount_formula_verified=False,fees_and_slippage_verified=False,full_session_semantic_verified=False,all_25_sessions_semantic_verified=False,orders_sent=0,broker_connection=False,engine_ready=False)
 pathlib.Path('replay_output').mkdir(exist_ok=True)
 pathlib.Path('replay_output/lesson4_price_side_replay.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
 print(json.dumps(dict(real_examples_passed=len(results),negative_control_rejected=True,orders_sent=0,engine_ready=False)))
if __name__=='__main__':main()
