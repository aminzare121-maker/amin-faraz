"""Reconstruct two machine-ASR polarity candidates using exact original video20 part12 WAV.
No teacher meaning, speaker identity, chart decision or trade authorization is inferred.
"""
from __future__ import annotations
import hashlib, io, json, re, wave, zipfile
from pathlib import Path
from html import escape

SOURCE_SHA='b071b5ba121ade3771a3048150b4361fec2755cee9788e7424e52d422eab00f8'
SOURCE_START=3288.0
SOURCE_END=3612.0
EXCERPT_START=3363.0
EXCERPT_END=3394.0
EVENT_IDS=('asr_390070bbb485b0bb574bafeb','asr_7ee805e35a39c8684cc7e2dc')
IMAGE_TIMES=(3345,3375,3405)

def digest(b):return hashlib.sha256(b).hexdigest()

def render(audio_zip:Path,board_zip:Path,conflict_report:Path,out_zip:Path):
    data=json.loads(conflict_report.read_text('utf-8'))
    route=next(r for r in data['routes'] if r['route_id']=='BREAK_VERY_STRONG_RETEST')
    pair=next(p for p in route['candidate_polarity_flips'] if {p['first_segment_id'],p['second_segment_id']}==set(EVENT_IDS))
    events=[e for e in route['events'] if e['source_segment_id'] in EVENT_IDS]
    if len(events)!=2 or any(e['source_audio_sha256']!=SOURCE_SHA for e in events):raise ValueError('source ASR identity mismatch')
    if pair['session']!=20:raise ValueError('wrong session identity')
    with zipfile.ZipFile(audio_zip) as z:
        wav=z.read('audio/batch_001/part_12.wav')
        meta=json.loads(z.read('fast_av_manifest.json'))
    part=next(p for p in meta['parts'] if p.get('chunk')==12)
    if digest(wav)!=SOURCE_SHA or part['audio_sha256']!=SOURCE_SHA:raise ValueError('original audio SHA does not match original manifest and ASR')
    if (float(part['cut_start']),float(part['cut_end']))!=(SOURCE_START,SOURCE_END):raise ValueError('source cut does not match')
    with wave.open(io.BytesIO(wav),'rb') as w:
        if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(16000,1,2):raise ValueError('unexpected WAV format')
        if w.getnframes()!=round((SOURCE_END-SOURCE_START)*16000):raise ValueError('unexpected WAV source length')
        a=round((EXCERPT_START-SOURCE_START)*16000)
        n=round((EXCERPT_END-EXCERPT_START)*16000)
        w.setpos(a);pcm=w.readframes(n)
        if len(pcm)!=n*2:raise ValueError('truncated PCM')
    output=io.BytesIO()
    with wave.open(output,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm)
    clip=output.getvalue()
    frames=[]
    with zipfile.ZipFile(board_zip) as z:
        for t in IMAGE_TIMES:
            matching=[name for name in z.namelist() if re.fullmatch(rf'frames/.*_t{t*1000:010d}_original\.jpg',name)]
            if len(matching)!=1:raise ValueError(f'original frame {t} is missing or ambiguous')
            raw=z.read(matching[0]);frames.append((t,raw,digest(raw)))
    manifest={'schema':'artin_session20_one_polarity_pair_original_av_v1','video':20,'route':'BREAK_VERY_STRONG_RETEST','citation_index':14,
       'pair_ids':list(EVENT_IDS),'source_audio_sha256':SOURCE_SHA,'original_audio_cut':[SOURCE_START,SOURCE_END],
       'excerpt_source_window':[EXCERPT_START,EXCERPT_END],'excerpt_sha256':digest(clip),
       'events':sorted(events,key=lambda e:e['start_seconds']),
       'reference_frames':[{'second':t,'sha256':h,'file':f'frame_{t}.jpg','position':'INSIDE_ASR' if any(e['start_seconds']<=t<=e['end_seconds'] for e in events) else 'OUTSIDE_BOTH_ASR'} for t,b,h in frames],
       'original_words_verified':False,'teacher_speaker_verified':False,'teacher_chart_decision_verified':False,'semantic_conflict_resolved':False,'orders_authorized':0}
    rows=[]
    for e in manifest['events']:
        a=e['start_seconds']-EXCERPT_START;b=e['end_seconds']-EXCERPT_START
        rows.append(f'<section><p><b>{e["start_seconds"]:.2f}–{e["end_seconds"]:.2f}</b> — متن ماشینی تأییدنشده: {escape(e["text_unverified"])}</p><button data-start="{a:.3f}" data-end="{b:.3f}">پخش فقط این عبارت</button></section>')
    img=''.join(f'<figure><img width="310" alt="Original video20 frame at {t}s" src="frame_{t}.jpg"><figcaption>فریم {t} ثانیه — خارج از هر دو عبارت؛ فقط زمینه تصویری</figcaption></figure>' for t,b,h in frames)
    html=f'''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>آرتین - بازبینی اختلاف گفتار جلسه ۲۰</title><style>body{{font:18px sans-serif;max-width:950px;margin:3rem auto;padding:1rem;line-height:1.8}}section,figure{{border:1px solid #aaa;padding:1rem;border-radius:9px}}figure{{display:inline-block}}button{{padding:10px}}</style><h1>بازبینی مستقل یک جفت عبارت، جلسه ۲۰</h1><p><strong>هش صوت اصلی با فهرست منبع مطابقت دارد.</strong> متن گفتار ماشینی است؛ گوینده، تصمیم مدرس و تعارض معنایی تأیید نشده‌اند.</p><audio id="audio" src="source_video20_part12_excerpt.wav" controls preload="metadata"></audio>{''.join(rows)}<h2>فریم‌های نمونه اطراف</h2><p>هیچ‌کدام از این سه فریم در محدوده زمانیِ دقیق دو عبارت قرار ندارد.</p>{img}<script>const a=document.querySelector('#audio');let stop=null;document.querySelectorAll('button[data-start]').forEach(b=>b.onclick=()=>{{stop=Number(b.dataset.end);a.currentTime=Number(b.dataset.start);a.play();}});a.addEventListener('timeupdate',()=>{{if(stop!==null&&a.currentTime>=stop){{a.pause();stop=null;}}}});a.addEventListener('seeking',()=>{{stop=null}});</script></html>'''
    with zipfile.ZipFile(out_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('index.html',html);z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr('source_video20_part12_excerpt.wav',clip)
        for t,b,h in frames:z.writestr(f'frame_{t}.jpg',b)
    return manifest

if __name__=='__main__':
    p=render(Path('/mnt/data/files/AUDIO_11.zip'),Path('/mnt/data/files/BOARD_IMAGES.zip'),Path('/mnt/data/files/ARTIN_13_DECISION_CONFLICT_REVIEW_PRIVATE_20261110.json'),Path('/mnt/data/ARTIN_VIDEO20_3371_3383_SOURCE_AUDIO_REVIEW_20261110.zip'))
    Path('/mnt/data/ARTIN_VIDEO20_3371_3383_PRIVATE_MANIFEST_20261110.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
    print(json.dumps({k:p[k] for k in ('pair_ids','source_audio_sha256','excerpt_sha256','reference_frames','semantic_conflict_resolved','orders_authorized')},ensure_ascii=False))