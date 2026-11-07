"""Write only the explicit synthetic example input in the current folder."""
import json
from pathlib import Path
from examples import demo_document
if __name__=='__main__':
    Path('SYNTHETIC_INPUT.json').write_text(json.dumps(demo_document(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('SYNTHETIC_INPUT.json: synthetic observations only; no market data or orders.')
