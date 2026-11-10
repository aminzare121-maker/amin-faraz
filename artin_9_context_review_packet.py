#!/usr/bin/env python3
"""Reduce 14 ASR lexical candidate pairs to two original AV windows for 9 unresolved pairs.
Source video/audio/images are copied without re-encoding. No semantic certification.
"""
from __future__ import annotations
import html
import hashlib
import json
import zipfile
from pathlib import Path

STATUS='CONTEXT_DEPENDENT_OPPOSITE_WORDING_NOT_VERIFIED_CONFLICT'


def build(source_zip:Path,triage_json:Path,output_zip:Path):
    triage=json.loads(triage_json.read_text(encoding='utf-8'))
    active=sorted((c for c in triage['cases'] if c['v2_wording_status']==STATUS),key=lambda c:(c['session'],c['pair_number_original']))
    if len(active)!=9 or {c['session'] for c in active}!={19,21}:
        raise ValueError('Exactly nine unresolved pairs in original 19/21 source groups expected')
    with zipfile.ZipFile(source_zip) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        sources={s['historical_original_wav_sha256']:s for s in manifest['sources']}
        allowed={c['source_wav_sha256'] for c in active}
        if len(allowed)!=2:raise ValueError('9 pairs no longer map to exactly two original WAVs')
        include=set()
        for sha in allowed:
            src=sources[sha]
            include.update([src['clip'],src['video_clip']])
            for seg in src['unique_speech_segments']:
                include.add(seg['image'])
        if len(include)!=15:raise ValueError('Expected 2 videos + 2 WAVs + 11 unique frames')
        all_members=set(archive.namelist())
        if not include.issubset(all_members):raise ValueError('Original media incomplete')
        cards=[]
        for sha in sorted(allowed,key=lambda h:sources[h]['session']):
            s=sources[sha];sess=s['session'];lo,hi=s['clip_seconds']
            these=[p for p in active if p['source_wav_sha256']==sha]
            note=('نمونه مربوط به نمودار آموزشی XAUUSD است.' if sess==19 else
                  'نمودار EURUSD است؛ این نمونه به‌تنهایی اجازه انتقال قانون به XAUUSD نمی‌دهد.')
            body=f'<section><h2>جلسه {sess} — {hi-lo} ثانیه ویدئوی اصلی</h2><p>{note}</p>'
            body+=f'<video controls preload="metadata" src="{html.escape(s["video_clip"],quote=True)}"></video>'
            body+=f'<audio controls preload="metadata" src="{html.escape(s["clip"],quote=True)}"></audio>'
            lookup={x['id']:x for x in s['unique_speech_segments']}
            for c in these:
                body+=f'<article><h3>اختلاف احتمالی #{c["pair_number_original"]} — تأیید معنایی: انجام‌نشده</h3>'
                body+='<p>جهت واژه‌ها متفاوت است؛ بدون شنیدن مستقل گفتار، نقش گوینده و شرایط دقیق نمودار، هیچ تضاد قابل‌اثباتی وجود ندارد.</p>'
                for u in sorted(c['utterances'],key=lambda x:x['start_seconds']):
                    src=lookup[u['segment_id']]
                    st=u['start_seconds']-lo;en=u['end_seconds']-lo
                    if not (0<=st<en<=hi-lo):raise ValueError('Outside original clip')
                    label=html.escape(u['machine_text_unverified'])
                    name=html.escape(src['image'],quote=True)
                    body+=(f'<div><button type="button" data-start="{st:.3f}" data-end="{en:.3f}">'
                           f'شنیدن {u["start_seconds"]:.2f}–{u["end_seconds"]:.2f}</button>'
                           f'<span> متن ماشینی، تأییدنشده: {label}</span>'
                           f'<details><summary>فریم همان لحظه</summary><img src="{name}" loading="lazy">'
                           f'<small>زمان تصویر: {u["source_frame_time"]:.2f}</small></details></div>')
                body+='</article>'
            cards.append(body+'</section>')
        head='''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>آرتین — ۹ اختلاف واژگانی، دو ویدئوی اصلی</title><style>body{font-family:Tahoma,Arial,sans-serif;background:#f5f7fa;color:#172334;max-width:1000px;margin:auto;padding:16px;line-height:1.9}section{background:white;border:1px solid #b7c2d1;border-radius:10px;margin:16px 0;padding:16px}article{border-top:1px solid #cbd5e1;margin:16px 0;padding-top:10px}video,audio{display:block;width:100%;max-width:900px;margin:12px 0}img{max-width:98%;height:auto}button{padding:8px 12px;margin:8px 4px;cursor:pointer}small{display:block;color:#526577}details{padding:5px}</style></head><body><h1>آرتین: ۹ مورد نیازمند بررسی شرایط واقعی</h1><p>این فایل از دو ویدئوی اصلی تهیه شده است: جلسه ۱۹، ۵۵ ثانیه؛ جلسه ۲۱، ۴۸ ثانیه. مجموع ۱۰۳ ثانیه. اصل صوت/ویدئو/تصاویر بدون تغییر باقی مانده است.</p><p><strong>تمام متن‌ها خروجی ماشینی هستند. نه نقش گوینده مستقل بررسی شده، نه ورود و خروج مدرس یا انطباق موتور تأیید شده. هیچ معامله‌ای مجاز نیست.</strong></p>'''
        tail='''<script>let activeAudio=null,boundEnd=null,setting=false;for(const b of document.querySelectorAll('button[data-start]'))b.addEventListener('click',()=>{const a=b.closest('section').querySelector('audio');for(const other of document.querySelectorAll('audio'))if(other!==a)other.pause();a.pause();activeAudio=a;boundEnd=Number(b.dataset.end);setting=true;a.currentTime=Number(b.dataset.start);a.play().catch(()=>{});});for(const a of document.querySelectorAll('audio')){a.addEventListener('timeupdate',()=>{if(a===activeAudio&&boundEnd!==null&&a.currentTime>=boundEnd){a.pause();boundEnd=null;}});a.addEventListener('seeking',()=>{if(!setting&&a===activeAudio)boundEnd=null;});a.addEventListener('seeked',()=>{setting=false;});}</script></body></html>'''
        index=(head+''.join(cards)+tail).encode('utf-8')
        output_manifest={
            'schema':'artin_nine_unresolved_original_av_review_v1',
            'source_groups':[{k:src[k] for k in ('session','source_mp4_sha256','historical_original_wav_sha256','clip_seconds','clip','video_clip')}
                              for sha in sorted(allowed,key=lambda h:sources[h]['session']) for src in [sources[sha]]],
            'open_case_numbers':[x['pair_number_original'] for x in active],
            'unique_source_frames':len([x for x in include if x.endswith('.jpg')]),
            'original_media_preserved':True,
            'speaker_verified':False,'teacher_meaning_verified':False,'orders_authorized':0}
        with zipfile.ZipFile(output_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
            out.writestr('index.html',index)
            out.writestr('manifest.json',json.dumps(output_manifest,ensure_ascii=False,indent=2)+'\n')
            for name in sorted(include):out.writestr(name,archive.read(name))
        with zipfile.ZipFile(output_zip) as result:
            if result.testzip() is not None:raise ValueError('Damaged output ZIP')
            for name in include:
                if hashlib.sha256(archive.read(name)).digest()!=hashlib.sha256(result.read(name)).digest():
                    raise ValueError('Original media bytes were changed')
            rendered=result.read('index.html').decode('utf-8')
            if rendered.count('data-start=')!=18 or rendered.count('<article>')!=9 or rendered.count('<video ' )!=2:
                raise ValueError('Missing review cases/buttons')
        return {**output_manifest,'original_media_assets':len(include),
                'private_zip_sha256':hashlib.sha256(output_zip.read_bytes()).hexdigest()}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('original_zip',type=Path);p.add_argument('triage_json',type=Path);p.add_argument('output_zip',type=Path);p.add_argument('receipt_json',type=Path)
    a=p.parse_args();receipt=build(a.original_zip,a.triage_json,a.output_zip)
    a.receipt_json.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))