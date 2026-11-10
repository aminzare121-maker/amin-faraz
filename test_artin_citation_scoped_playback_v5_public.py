"""Public, entirely synthetic 6-window fixture for Artin review-player v5.
No private audio or instructor speech is included.
"""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from artin_citation_scoped_playback_v5 import transform,OLD_HANDLER

def source_fixture(path):
    windows=[];sections=[]
    for i in range(1,7):
        key=f'ARTIN-RESTORED-{i:02d}'
        base=float(i*100)
        segments=[];buttons=[]
        for k in range(7):
            if k==0:a,b=base+0,base+2;scope='crosses_boundary'
            elif k==1:a,b=base+9,base+11;scope='crosses_boundary'
            else:a=base+2+(k-2)*1.4;b=a+1;scope='fully_inside'
            sid=f'synthetic_{i}_{k}'
            segments.append({'id':sid,'start':a,'end':b,'text_unverified':'synthetic fixture',
                'citation_scope':scope,'inside_citation_from':max(a,base+1),
                'inside_citation_until':min(b,base+10)})
            css='edge' if scope=='crosses_boundary' else 'whole'
            offset=a-(base-1)
            buttons.append(f'<button class="asr scope-{css}" data-citation-scope="{scope}" onclick="seek(this)" data-file="synthetic_{i}.wav" data-offset="{offset:.3f}"><span class="tt">{a:.2f}–{b:.2f}</span> synthetic fixture<span class="scope-note">synthetic</span></button>')
        windows.append({'id':key,'clip':f'synthetic_{i}.wav','start':base+1,'end':base+10,
            'audio_start':base-1,'audio_end':base+12,'asr':segments})
        sections.append(f'<section><h2>{key} synthetic</h2><audio data-file="synthetic_{i}.wav"></audio>'+''.join(buttons)+'</section>')
    html='<html><h1>Synthetic audio review</h1>'+''.join(sections)+'<script>'+OLD_HANDLER+'</script></html>'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps({'schema':'artin_6_original_av_review_v4_per_utterance_scope','windows':windows}))
        z.writestr('index.html',html)
        for i in range(1,7):z.writestr(f'synthetic_{i}.wav',b'FAKE-WAV-NO-REAL-AUDIO')

class SyntheticV5Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.src=Path(self.temp.name)/'synthetic.zip'
        self.out=Path(self.temp.name)/'new.zip';source_fixture(self.src)
    def test_all_42_buttons_and_12_boundary_clamps(self):
        result=transform(self.src,self.out)
        self.assertEqual((result['buttons'],result['boundary_replays_clamped']),(42,12))
        self.assertEqual(result['orders_authorized'],0)
        with zipfile.ZipFile(self.out) as z:
            h=z.read('index.html').decode()
        self.assertEqual(h.count('data-play-start='),42)
        self.assertIn('audio.addEventListener(\'timeupdate\'',h)
    def test_never_mutates_source_media(self):
        transform(self.src,self.out)
        with zipfile.ZipFile(self.src) as old,zipfile.ZipFile(self.out) as new:
            for i in range(1,7):self.assertEqual(old.read(f'synthetic_{i}.wav'),new.read(f'synthetic_{i}.wav'))
    def test_reprocessing_fails_closed(self):
        transform(self.src,self.out)
        with self.assertRaises(ValueError):transform(self.out,Path(self.temp.name)/'third.zip')
    def test_invalid_manifest_rejected(self):
        changed=Path(self.temp.name)/'bad.zip'
        with zipfile.ZipFile(self.src) as old,zipfile.ZipFile(changed,'w') as bad:
            for name in old.namelist():
                blob=old.read(name)
                if name=='manifest.json':
                    d=json.loads(blob);d['windows'][0]['asr'][0]['citation_scope']='fully_inside'
                    blob=json.dumps(d).encode()
                bad.writestr(name,blob)
        with self.assertRaises(ValueError):transform(changed,self.out)
if __name__=='__main__':unittest.main()