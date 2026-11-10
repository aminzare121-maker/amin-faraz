"""Limit button-initiated audio to the verified citation intersection.

Context remains accessible through the original audio player's controls. Original
audio and image bytes are never modified. Timed machine ASR is NOT a semantic
or speaker certification; no trade can be authorized by this transformation.
"""
import hashlib
import json
from pathlib import Path
import re
import zipfile

BUTTON_RE = re.compile(r'<button\s+class="asr\s+scope-(whole|edge|outside)"\s+data-citation-scope="(fully_inside|crosses_boundary|outside)"\s+onclick="seek\(this\)"\s+data-file="([^"]+)"\s+data-offset="([^"]+)"([^>]*)>(.*?)</button>', re.DOTALL)
SECTION_RE = re.compile(r'(<section><h2>(ARTIN-RESTORED-\d\d)\b.*?</section>)', re.DOTALL)
OLD_HANDLER = "function seek(button){let name=button.dataset.file;let audio=button.closest('section').querySelector('audio');if(audio.dataset.file!==name)return;if(!audio)return;audio.currentTime=Number(button.dataset.offset);audio.play().catch(()=>{});audio.scrollIntoView({behavior:'smooth',block:'center'})}"
NEW_HANDLER = """function seek(button){
  const section=button.closest('section');
  if(!section)return;
  const audio=section.querySelector('audio');
  if(!audio || audio.dataset.file!==button.dataset.file)return;
  const start=Number(button.dataset.playStart),end=Number(button.dataset.playEnd);
  if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>audio.duration+0.05&&Number.isFinite(audio.duration))return;
  audio.dataset.stopAt=String(end);
  audio.dataset.expectedSeek=String(start);
  audio.currentTime=start;
  audio.play().catch(()=>{});
  audio.scrollIntoView({behavior:'smooth',block:'center'});
}
document.querySelectorAll('audio').forEach(audio=>{
  audio.addEventListener('timeupdate',()=>{
    const stop=Number(audio.dataset.stopAt);
    if(audio.dataset.stopAt && Number.isFinite(stop) && audio.currentTime>=stop-0.015){
      audio.pause(); delete audio.dataset.stopAt;
    }
  });
  // A manual seek cancels scoped replay; the button's own seek is exempt.
  audio.addEventListener('seeking',()=>{
    const expected=Number(audio.dataset.expectedSeek);
    const initiatedByButton=audio.dataset.expectedSeek && Math.abs(audio.currentTime-expected)<0.075;
    delete audio.dataset.expectedSeek;
    if(!initiatedByButton)delete audio.dataset.stopAt;
  });
});"""

def transform(input_zip, output_zip):
    with zipfile.ZipFile(input_zip) as original:
        names=original.namelist()
        if len(set(names))!=len(names) or names.count('manifest.json')!=1 or names.count('index.html')!=1:
            raise ValueError('invalid or duplicate ZIP members')
        data=json.loads(original.read('manifest.json'))
        if data.get('schema')!='artin_6_original_av_review_v4_per_utterance_scope':
            raise ValueError('requires v4 input')
        windows=data['windows']
        if len(windows)!=6 or len({w['id'] for w in windows})!=6:
            raise ValueError('invalid six source windows')
        section_map={w['id']:w for w in windows}
        html=original.read('index.html').decode('utf-8')
        if html.count(OLD_HANDLER)!=1:
            raise ValueError('unexpected playback code; refusing unsafe rewrite')
        if 'data-play-start=' in html or 'data-stop-at=' in html:
            raise ValueError('already converted; refuse duplicate metadata')
        touched=set(); button_count=0; clipped=0
        def patch_section(match):
            nonlocal button_count,clipped
            source,identity=match.group(1),match.group(2)
            if identity not in section_map or identity in touched:
                raise ValueError('duplicate or unrecognized section')
            touched.add(identity)
            w=section_map[identity]
            segs=w['asr'];position=0
            def patch_button(b):
                nonlocal position,button_count,clipped
                if position>=len(segs):raise ValueError('extra button')
                seg=segs[position];position+=1
                css,status,filename,offset,attrs,body=b.groups()
                if filename!=w['clip'] or abs(float(offset)-(seg['start']-w['audio_start']))>0.001:
                    raise ValueError('button points at wrong source or offset')
                if status!=seg['citation_scope'] or css!={'fully_inside':'whole','crosses_boundary':'edge','outside':'outside'}[status]:
                    raise ValueError('citation status mismatch')
                if f'{seg["start"]:.2f}–{seg["end"]:.2f}' not in body:
                    raise ValueError('displayed utterance time mismatch')
                if status=='outside':
                    # No buttons with outside content in the current six source windows.
                    raise ValueError('unverifiable out-of-citation button cannot be cited')
                lo=max(seg['start'],w['start']);hi=min(seg['end'],w['end'])
                if hi<=lo or lo<w['audio_start'] or hi>w['audio_end']:
                    raise ValueError('invalid citation intersection')
                play_start=lo-w['audio_start'];play_end=hi-w['audio_start']
                if play_end<=play_start:raise ValueError('empty playable region')
                if status=='crosses_boundary':clipped+=1
                button_count+=1
                return b.group(0).replace('data-offset="'+offset+'"',
                    f'data-offset="{offset}" data-play-start="{play_start:.3f}" data-play-end="{play_end:.3f}" data-source-id="{seg["id"]}"',1)
            source,n=re.subn(BUTTON_RE,patch_button,source)
            if n!=len(segs):raise ValueError('missing utterance buttons')
            return source
        html,num=re.subn(SECTION_RE,patch_section,html)
        if num!=6 or touched!=set(section_map) or button_count!=42 or clipped!=12:
            raise ValueError('source coverage count discrepancy')
        html=html.replace(OLD_HANDLER,NEW_HANDLER,1)
        annotation='<p><strong>پخش دکمه‌های گفتار فقط به بخش داخل بازهٔ استناد محدود است؛ برای شنیدن متن کامل و زمینه از کنترل پخش فایل صوتی استفاده کنید. تمام متن‌ها و نقش گوینده هنوز تأییدنشده‌اند.</strong></p>'
        html=html.replace('</h1>','</h1>'+annotation,1)
        data['schema']='artin_6_original_av_review_v5_scoped_button_playback'
        data['v5']={'buttons':button_count,'scope_clipped_buttons':clipped,
                    'button_replay_limited_to_citation':True,
                    'native_full_audio_player_unchanged':True,
                    'teacher_speech_verified':False,'trades_authorized':0}
        with zipfile.ZipFile(output_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as out:
            for name in names:
                if name=='index.html':raw=html.encode('utf-8')
                elif name=='manifest.json':raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
                else:raw=original.read(name)
                out.writestr(name,raw)
        with zipfile.ZipFile(output_zip) as saved:
            if saved.testzip() is not None or set(saved.namelist())!=set(names):
                raise ValueError('output damaged')
            for name in names:
                if name not in ('index.html','manifest.json'):
                    if hashlib.sha256(saved.read(name)).digest()!=hashlib.sha256(original.read(name)).digest():
                        raise ValueError('original media bytes changed')
        return {'source_windows':6,'buttons':button_count,'boundary_replays_clamped':clipped,
                'original_multimedia_unchanged':True,'teacher_semantics_verified':False,'orders_authorized':0}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('input_zip');p.add_argument('output_zip');p.add_argument('audit_json')
    a=p.parse_args()
    result=transform(a.input_zip,a.output_zip)
    Path(a.audit_json).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result))