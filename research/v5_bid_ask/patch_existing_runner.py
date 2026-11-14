"""Patch copy of original V5 pullback_engine.py; NEVER edit frozen source.
Usage: python patch_existing_runner.py INPUT_ENGINE.py OUTPUT_ENGINE.py
Place quote_math.py beside OUTPUT_ENGINE.py before running the copy.
"""
import sys
from pathlib import Path
if len(sys.argv)!=3:raise SystemExit(__doc__)
src,dst=map(Path,sys.argv[1:])
text=src.read_text(encoding="utf8")
needle1="closed_profit=side*(d.close.iat[j]-px)"
needle2="proposed=d.close.iat[j]-side*max(dist*.65,float(a.iat[j])*.7)"
assert text.count(needle1)==1, "original profit expression changed; manual review required"
assert text.count(needle2)==1, "original stop expression changed; manual review required"
text=text.replace(needle1,"closed_profit=closed_bar_profit_per_oz(side,float(d.close.iat[j]),spr,px)")
text=text.replace(needle2,"proposed=trailing_candidate(side,float(d.close.iat[j]),spr,max(dist*.65,float(a.iat[j])*.7))")
text=text.replace("periods={'train':","from quote_math import closed_bar_profit_per_oz, trailing_candidate\nperiods={'train':",1)
if src.resolve()==dst.resolve():raise SystemExit("Never overwrite original runner")
dst.write_text(text,encoding="utf8")
print("patched",dst)
