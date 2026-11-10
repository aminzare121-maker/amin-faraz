#!/usr/bin/env python3
"""Create private 14-pair AV review from SHA-receipted ORIGINAL MP4s, never fake old WAV identity."""
from __future__ import annotations
import hashlib, html, io, json, subprocess, wave, zipfile
from artin_14_pair_time_identity import bind_pair
from pathlib import Path

BASE=Path('/mnt/data')
INPUT=BASE/'ARTIN_14_UNIQUE_PAIR_WAV_SOURCE_RECONCILIATION_PRIVATE_20261110.json'
ROOT=BASE/'artin_original_19_21'
OUT=BASE/'ARTIN_14_PAIRS_ORIGINAL_MP4_DERIVED_REVIEW_20261110.zip'
RECEIPTS={19:'164d6a5ef28b29e3500d4211b7a5954b95dd9fe1393d99d7e5806e693ca8dc03',21:'f63690d402f299d297110ff815b7fee9fcae8bb4927b9084e401488efaa3a1a3',20:'6db1d227430e99facea0ba6cc2931f04f70f67ed42d8f6abb0bb58f9e087e3a9'}
WINDOWS={('19','0efe686fad'):(3763,3802),('19','b96434bd99'):(4276,4331),('20','b071b5ba12'):(3363,3394),('21','d3ea03e2be'):(1896,1944)}
def digest(b):return hashlib.sha256(b).hexdigest()
def sh(cmd):return subprocess.check_output(cmd,stderr=subprocess.DEVNULL)
def make():
    data=json.loads(INPUT.read_text()); bysha={}; manifest={'schema':'artin_14_source_mp4_derived_listening_v1','unverified_teacher_semantics':True,'orders_authorized':0,'sources':[],'pairs':[],'original_mp4_video_sha_receipts':RECEIPTS,'old_original_wav_sha_not_claimed':True};files={}
    source_path={n:ROOT/f'session_{n}_original.mp4' for n in [19,20,21]}
    for n,p in source_path.items():
        if digest(p.read_bytes())!=RECEIPTS[n]:raise ValueError('Original MP4 SHA mismatch '+str(n))
    z=zipfile.ZipFile(BASE/'ARTIN_VIDEO20_3371_3383_SOURCE_AUDIO_REVIEW_20261110.zip')
    # Use original MP4 source for all lessons including lesson20; avoids confusing regenerated vs exact old WAV
    groups={(p['session'],p['source_audio_sha256']):[] for p in data['pair_details']}
    for i,p in enumerate(data['pair_details'],1):groups[(p['session'],p['source_audio_sha256'])].append((i,p))
    speech_index={}
    with zipfile.ZipFile(BASE/'files/ARTIN_25_SESSIONS_UNIFIED_10272_PRIVATE_20261110.zip') as src:
        for session in [19,20,21]:
            name=f'session_{session:02d}_unified_machine_speech_UNVERIFIED.jsonl'
            for ln in src.read(name).decode().splitlines():
                o=json.loads(ln);speech_index[(session,o.get('source_segment_id'))]=o
    for (session,oldhash),items in groups.items():
        win=WINDOWS[(str(session),oldhash[:10])]; clipname=f'original_mp4_decoded_audio/s{session}_{oldhash[:10]}_{win[0]}-{win[1]}.wav'
        tmppath=BASE/'artin_exact_audio_candidates'/f'group_s{session}_{oldhash[:10]}.wav'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(win[0]),'-t',str(win[1]-win[0]),'-i',str(source_path[session]),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(tmppath)],check=True)
        wav=tmppath.read_bytes()
        with wave.open(io.BytesIO(wav),'rb') as w:
            if w.getframerate()!=16000 or w.getnchannels()!=1 or w.getsampwidth()!=2 or abs(w.getnframes()/w.getframerate()-(win[1]-win[0]))>.05:raise ValueError('decoded WAV unexpectedly incomplete')
        files[clipname]=wav
        video_name=f'original_mp4_replay_video/s{session}_{oldhash[:10]}_{win[0]}-{win[1]}.mp4'
        video_out=BASE/'artin_exact_audio_candidates'/f'video_s{session}_{oldhash[:10]}.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(win[0]),'-t',str(win[1]-win[0]),'-i',str(source_path[session]),'-vf','scale=960:-2','-c:v','libx264','-preset','ultrafast','-crf','31','-c:a','aac','-b:a','64k','-movflags','+faststart',str(video_out)],check=True)
        files[video_name]=video_out.read_bytes()
        all_segments={}
        for idx,p in items:
            # A past report had shuffled ID/time lists; independently bind by exact source records.
            bind_pair(p,{sid:speech_index.get((session,sid)) for sid in p['segment_ids']})
            segs=[]
            for sid in p['segment_ids']:
                raw=speech_index.get((session,sid))
                if not raw:raise ValueError('original source speech segment missing: '+sid)
                if not any(abs(raw['start_seconds']-ts[0])<.1 and abs(raw['end_seconds']-ts[1])<.1 for ts in p['phrases']):raise ValueError('source ASR time not found in source pair')
                ts=(raw['start_seconds'],raw['end_seconds'])
                if raw['source_audio_sha256']!=oldhash:raise ValueError('original ASR audio SHA mismatch')
                if not(win[0]<=ts[0]<ts[1]<=win[1]):raise ValueError('clip coverage failure')
                all_segments[sid]={'id':sid,'start':ts[0],'end':ts[1],'machine_text_unverified':raw['machine_text_unverified']}
                segs.append(sid)
            if len(segs)!=len(p['phrases']) or len({(speech_index[(session,s)]['start_seconds'],speech_index[(session,s)]['end_seconds']) for s in segs})!=len(p['phrases']):raise ValueError('non-bijective source segment to time mapping')
            manifest['pairs'].append({'pair_number':idx,'session':session,'original_audio_sha256_historical':oldhash,'source_original_mp4_sha256':RECEIPTS[session],'audio_generated_from_original_mp4_file':clipname,'clip_seconds':list(win),'segment_ids':segs,'routes':p.get('routes',[]),'semantic_conflict_certified':False,'teacher_speaker_certified':False,'orders_authorized':0})
        frames=[]
        for sid,seg in sorted(all_segments.items(),key=lambda kv:kv[1]['start']):
            t=round((seg['start']+seg['end'])/2,2)
            imname=f'original_mp4_frames/s{session}_{oldhash[:10]}_{sid}_{t:.2f}.jpg'
            jpg=sh(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(t),'-i',str(source_path[session]),'-frames:v','1','-q:v','3','-f','image2','pipe:1'])
            if len(jpg)<1000:raise ValueError('empty image')
            files[imname]=jpg
            seg['image']=imname;seg['image_capture_time']=t;seg['image_sha256']=digest(jpg)
            frames.append(imname)
        manifest['sources'].append({'session':session,'source_mp4_sha256':RECEIPTS[session],'historical_original_wav_sha256':oldhash,'newly_decoded_wav_sha256':digest(wav),'clip':clipname,'video_clip':video_name,'video_clip_sha256':digest(files[video_name]),'clip_seconds':list(win),'audio_length_seconds':win[1]-win[0],'unique_speech_segments':list(all_segments.values()),'sampled_original_mp4_images':frames,'original_wav_sha256_exact_match':digest(wav)==oldhash,'teacher_visual_decision_certified':False})
    htmls=['<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>آرتین - ۱۴ جفت گفتار از MP4 اصلی</title><style>body{font-family:Tahoma,Arial,sans-serif;max-width:1080px;margin:auto;padding:20px;line-height:1.8;background:#f8fafc;color:#17202a}section{padding:15px;margin:16px 0;border:1px solid #cbd5e1;background:#fff;border-radius:10px}button{padding:8px;margin:4px;cursor:pointer}img{max-width:49%;margin:4px;border:1px solid #ddd}small{color:#52677b}audio{width:100%}</style></head><body><h1>بازبینی ۱۴ جفت: صوت و تصویر بازاستخراج‌شده از MP4 اصلی</h1><p><strong>مهم:</strong> منبع MP4 با رسید SHA-256 تایید شده، اما WAV جدید با هش تاریخی WAV یکسان اعلام نمی‌شود. متن گفتار ماشینی و نقش گوینده تاییدنشده است. هیچ تعارض واقعی/قانون معامله تایید نشده.</p>']
    for src in manifest['sources']:
        htmls.append(f'<section><h2>جلسه {src["session"]}؛ منبع تاریخی WAV {src["historical_original_wav_sha256"][:12]}…</h2><p>MP4 SHA: <code>{src["source_mp4_sha256"]}</code>؛ صوت WAV بازاستخراج شده: <code>{src["newly_decoded_wav_sha256"]}</code></p><video controls preload="metadata" style="width:100%;max-width:960px" src="{src["video_clip"]}"></video><audio controls preload="metadata" src="{src["clip"]}"></audio>')
        for seg in src['unique_speech_segments']:
            htmls.append(f'<div><button type="button" data-clip="{src["clip"]}" data-start="{seg["start"]-src["clip_seconds"][0]:.3f}" data-end="{seg["end"]-src["clip_seconds"][0]:.3f}">پخش {seg["start"]:.2f}–{seg["end"]:.2f}</button> <small>ماشینی و تاییدنشده: {html.escape(seg["machine_text_unverified"])}</small><details><summary>فریم اصلی داخل زمان عبارت</summary><img loading="lazy" src="{seg["image"]}"><p>زمان: {seg["image_capture_time"]} ثانیه؛ فریم به تنهایی اثبات تصمیم مدرس نیست.</p></details></div>')
        htmls.append('</section>')
    htmls.append('<script>let endAt=null;let setting=false;document.querySelectorAll("button[data-clip]").forEach(b=>b.addEventListener("click",()=>{let a=b.closest("section").querySelector("audio");a.pause();setting=true;a.currentTime=Number(b.dataset.start);endAt=Number(b.dataset.end);a.play().catch(()=>{});}));document.querySelectorAll("audio").forEach(a=>{a.addEventListener("timeupdate",()=>{if(endAt!==null && a.currentTime>=endAt){a.pause();endAt=null;}});a.addEventListener("seeking",()=>{if(!setting)endAt=null;});a.addEventListener("seeked",()=>{setting=false;});});</script></body></html>')
    files['index.html']='\n'.join(htmls).encode('utf-8');files['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode();
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as out:
        for name,b in files.items():out.writestr(name,b)
    with zipfile.ZipFile(OUT) as out:
        bad=out.testzip();assert bad is None
    print(json.dumps({'packet':str(OUT),'size':OUT.stat().st_size,'source_groups':len(manifest['sources']),'unique_pairs':len(manifest['pairs']),'total_unique_segments':sum(len(s['unique_speech_segments']) for s in manifest['sources']),'original_mp4_frame_images':sum(len(s['sampled_original_mp4_images']) for s in manifest['sources']),'source_sha_receipts_verified':True,'exact_old_wav_shas_matched':sum(s['original_wav_sha256_exact_match'] for s in manifest['sources']),'semantics_verified':False},ensure_ascii=False))
    (BASE/'ARTIN_14_PAIRS_MP4_SOURCE_RECOVERY_PRIVATE_20261110.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':make()