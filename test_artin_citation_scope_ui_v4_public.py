"""Offline synthetic-only tests for CI; private teacher speech and audio never shipped."""
import copy
from html import escape
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from artin_citation_scope_ui_v4 import render_v4


def source_zip(path):
    windows=[]
    parts=[]
    for k in range(1,7):
        wid=f'ARTIN-RESTORED-{k:02d}'
        audio=f'synthetic-{k}.wav'
        start=float(k*100);end=start+10
        asr=[{'id':f's{k}','start':start-1,'end':start+1,'text_unverified':'مثال فرضی',
              'audio_excerpt_truncated':False}]
        windows.append({'id':wid,'route':'SYNTHETIC','queue_video':20,'clip':audio,
             'start':start,'end':end,'audio_start':start-4,'audio_end':end+4,'asr':asr})
        parts.append(f'<section><h2>{wid} — SYNTHETIC</h2><div class="segments">'
                     f'<button class="asr" onclick="seek(this)" data-file="{audio}" '
                     f'data-offset="3.000"><span class="tt">{start-1:.2f}–{start+1:.2f}</span> '
                     f'{escape("مثال فرضی")}</button></div></section>')
    page='<html><head><style>.asr{display:block}</style></head><body><h1>test</h1>'+''.join(parts)+'</body></html>'
    manifest={'windows':windows,'orders_authorized':0}
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
        z.writestr('index.html',page)
        for k in range(1,7):z.writestr(f'synthetic-{k}.wav',bytes([k])*20)

class SyntheticTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.p=Path(self.tmp.name)/'input.zip'
        self.out=Path(self.tmp.name)/'output.zip'
        source_zip(self.p)
    def tearDown(self):self.tmp.cleanup()
    def test_success_marks_six_boundary_utterances(self):
        r=render_v4(self.p,self.out)
        self.assertEqual(r['counts']['crosses_boundary'],6)
        self.assertEqual(r['orders_authorized'],0)
        with zipfile.ZipFile(self.out) as z:
            self.assertEqual(z.read('index.html').decode().count('data-citation-scope='),6)
    def test_tampered_text_rejected(self):
        with zipfile.ZipFile(self.p) as z:
            items={n:z.read(n) for n in z.namelist()}
        items['index.html']=items['index.html'].replace('مثال فرضی'.encode(), 'تغییر'.encode(),1)
        with zipfile.ZipFile(self.p,'w') as z:
            for n,b in items.items():z.writestr(n,b)
        with self.assertRaises(ValueError):render_v4(self.p,self.out)
    def test_asset_bytes_unchanged(self):
        render_v4(self.p,self.out)
        with zipfile.ZipFile(self.p) as a,zipfile.ZipFile(self.out) as b:
            for k in range(1,7):
                n=f'synthetic-{k}.wav'
                self.assertEqual(a.read(n),b.read(n))
    def test_no_duplicate_annotations(self):
        render_v4(self.p,self.out)
        with self.assertRaises(ValueError):render_v4(self.out,self.p)
if __name__=='__main__':unittest.main()