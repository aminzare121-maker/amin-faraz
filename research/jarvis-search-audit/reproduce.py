"""Extract only the existing pure search function; never import/launch the app."""
import ast
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

source = Path('C:/Users/Pixel/Documents/Codex/2026-10-22/zip-chatgpt/work/v58_10_offline_candidate/Jarvis58_New_Integrated_Preview.py')
raw = source.read_bytes()
tree = ast.parse(raw.decode('utf-8-sig'))
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'find_files')
with tempfile.TemporaryDirectory() as temp:
    roots = [Path(temp) / 'first', Path(temp) / 'second']
    for root in roots:
        root.mkdir()
    for i in range(3):
        (roots[0] / f'unrelated{i}.txt').write_text('synthetic')
    (roots[1] / 'needle.txt').write_text('synthetic target')
    namespace = dict(Path=Path, os=os, time=time, allowed_roots=lambda: roots,
                     MAX_VISITS=2, MAX_RESULTS=20, TEXT_EXTS=set(), DOC_EXTS=set(), PDF_EXTS=set())
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    original = namespace['find_files']('needle.txt')
    namespace['allowed_roots'] = lambda: roots[::-1]
    reversed_result = namespace['find_files']('needle.txt')
    result = dict(source_sha256=hashlib.sha256(raw).hexdigest(), synthetic=True,
                  original_order_matches=len(original['matches']),
                  reversed_order_matches=len(reversed_result['matches']),
                  reproduced=not original['matches'] and len(reversed_result['matches']) == 1,
                  installed_app_changed=False, app_imported=False, fixed=False)
    assert result['reproduced']
    Path(__file__).with_name('reproduction.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
