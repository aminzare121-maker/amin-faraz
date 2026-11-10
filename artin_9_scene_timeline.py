#!/usr/bin/env python3
"""Build a source-hash-pinned 1-Hz visual scene timeline for two Artin episodes.

This tool detects changes in the ON-SCREEN PIXELS only. It does NOT transcribe
Persian, certify a speaker, infer a teacher rule or authorize trading.

The private source ZIP is expected to contain two video excerpts and nine
machine-ASR utterances. No external network, broker or MT5 connection is used.
"""
from __future__ import annotations
import argparse, hashlib, io, json, math, zipfile
from collections import defaultdict
from html import escape
from pathlib import Path

SOURCE_DURATIONS = {19: (4276, 4331), 21: (1896, 1944)}
SOURCE_PAIR_IDS = {2,3,5,7,9,10,12,13,14}
THRESHOLD = 0.08  # 8% of sampled chart area pixels differ by > 30 intensity
PIXEL_DELTA = 30


def sha(b): return hashlib.sha256(b).hexdigest()


def valid_float(v): return type(v) in (float, int) and math.isfinite(v)


def source_gate(data):
    if not isinstance(data,dict) or not isinstance(data.get('source_groups'),list):
        raise ValueError('invalid report')
    if len(data['source_groups'])!=2 or {g.get('session') for g in data['source_groups']}!=set(SOURCE_DURATIONS):
        raise ValueError('wrong source video groups')
    if len(data.get('pairs', []))!=9 or {p.get('pair') for p in data['pairs']}!=SOURCE_PAIR_IDS:
        raise ValueError('wrong pairs')
    for key in ('original_Persian_words_independently_heard', 'speaker_identity_independently_verified',
                'teacher_semantics_verified','same_chart_trade_situation_verified_for_any_pair',
                'XAUUSD_transfer_from_EURUSD_authorized'):
        if data.get(key) is not False: raise ValueError('unearned teacher semantic claim')
    if data.get('mt5_orders_authorized')!=0: raise ValueError('trading not authorized')
    ids={}
    for g in data['source_groups']:
        sess=g['session'];left,right=SOURCE_DURATIONS[sess]
        if g.get('clip_seconds')!=[left,right]:raise ValueError('wrong source interval')
        if len(g.get('machine_speech', []))!=({19:4,21:5}[sess]):raise ValueError('speech count mismatch')
        for u in g['machine_speech']:
            k=u['segment_id'];a=u['start_seconds'];b=u['end_seconds']
            if k in ids or not (valid_float(a) and valid_float(b) and left<=a<b<=right):raise ValueError('speech identity or time invalid')
            ids[k]=(sess,a,b)
    for p in data['pairs']:
        s=p['session'];u,v=p['utterance_ids']
        if not (u in ids and v in ids and ids[u][0]==ids[v][0]==s and ids[u][1]<ids[v][1]):
            raise ValueError('pair violates source identity or order')
    return ids


def build_decision_context(data, per_second):
    """Pure deterministic event/pair linkage, suitable for public synthetic tests."""
    ids=source_gate(data)
    if set(per_second)!=set(SOURCE_DURATIONS):raise ValueError('wrong scan sessions')
    output={'schema':'artin_9_pair_screen_change_evidence_v1',
            'sampling_interval_seconds':1, 'chart_pixel_change_threshold':THRESHOLD,
            'pixel_difference_intensity_threshold':PIXEL_DELTA,
            'teacher_utterances_acoustically_verified':False,
            'teacher_rules_semantically_certified':False,'mt5_orders_authorized':0,
            'screen_change_is_not_teacher_decision':True,'episodes':[], 'pairs':[]}
    group_map={g['session']:g for g in data['source_groups']}
    for sess in sorted(SOURCE_DURATIONS):
        t0,t1=SOURCE_DURATIONS[sess]; samples=per_second[sess]
        if len(samples)!=(t1-t0):raise ValueError('must have exactly one sample per original second')
        events=[]; old=-math.inf
        for sample in samples:
            t=sample['second']; frac=sample['changed_fraction']
            if not (type(t) is int and t0<=t<t1 and valid_float(frac) and 0<=frac<=1 and t>old):
                raise ValueError('invalid sample')
            old=t
            if frac>=THRESHOLD:
                events.append({'second':t,'changed_fraction':round(frac,4),'kind':'SAMPLED_PIXEL_CHANGE_NOT_TEACHER_DECISION'})
        if [s['second'] for s in samples]!=list(range(t0,t1)):raise ValueError('second index not complete')
        utterances=[]
        for u in group_map[sess]['machine_speech']:
            in_speech=[e['second'] for e in events if u['start_seconds']<=e['second']<=u['end_seconds']]
            utterances.append({'segment_id':u['segment_id'],'start_seconds':u['start_seconds'],
                               'end_seconds':u['end_seconds'], 'sampled_screen_change_during_speech':in_speech,
                               'words_acoustically_verified':False,'teacher_meaning_verified':False})
        output['episodes'].append({'session':sess,'clip_seconds':[t0,t1],'chart':group_map[sess]['chart'],
                                   'sampled_frames':len(samples),'candidate_pixel_change_count':len(events),
                                   'candidate_changes':events,'utterances':utterances,
                                   'source_video_sha256':group_map[sess]['video_excerpt_sha256']})
    for p in sorted(data['pairs'],key=lambda x:x['pair']):
        sess=p['session'];first,second=[ids[i] for i in p['utterance_ids']]
        ev=next(g['candidate_changes'] for g in output['episodes'] if g['session']==sess)
        between=[x['second'] for x in ev if first[2]<x['second']<second[1]]
        during=[x['second'] for x in ev if first[1]<=x['second']<=second[2]]
        output['pairs'].append({'pair':p['pair'],'session':sess,'utterance_ids':p['utterance_ids'],
                                'seconds_between_utterances':round(second[1]-first[2],3),
                                'intervening_sampled_screen_changes':between,
                                'sampled_changes_from_first_to_second':during,
                                'visually_identical_chart_state_verified':False,
                                'confirmed_teacher_contradiction':False,
                                'teacher_semantics_verified':False,'trade_authorized':False})
    return output


def sample_original_video(source_bytes,start,end):
    import cv2, numpy as np, tempfile, os
    # OpenCV requires seekable file; write only to a transient local file.
    f=tempfile.NamedTemporaryFile(suffix='.mp4',delete=False)
    try:
        f.write(source_bytes);f.close()
        cap=cv2.VideoCapture(f.name)
        if not cap.isOpened():raise ValueError('source MP4 cannot be opened')
        samples=[]; candidates=[];prev=None
        for absolute_t in range(start,end):
            relative=absolute_t-start
            cap.set(cv2.CAP_PROP_POS_MSEC,relative*1000)
            ok,frame=cap.read()
            if not ok: raise ValueError(f'cannot decode 1-Hz frame at {absolute_t}')
            h,w=frame.shape[:2]
            # ROI: visible chart; cropping excludes browser toolbars/sidebar.
            crop=frame[int(h*.17):int(h*.91),int(w*.02):int(w*.83)]
            reduced=cv2.resize(crop,(385,235),interpolation=cv2.INTER_AREA)
            frac=float(np.mean(np.max(cv2.absdiff(prev,reduced),axis=2)>PIXEL_DELTA)) if prev is not None else 0.
            samples.append({'second':absolute_t,'changed_fraction':frac})
            if frac>=THRESHOLD:
                ok,enc=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,89])
                if not ok:raise ValueError('cannot encode derived video frame')
                candidates.append((absolute_t,enc.tobytes()))
            prev=reduced
        cap.release()
        return samples,candidates
    finally:
        try:os.unlink(f.name)
        except FileNotFoundError:pass


def run(source_zip:Path, result_zip:Path, report_file:Path):
    from artin_9_episode_validation import validate_package
    validate_package(source_zip)
    with zipfile.ZipFile(source_zip) as z:
        original_names=z.namelist()
        data=json.loads(z.read('review.json'))
        source_gate(data)
        scans={}; frames={}
        for g in data['source_groups']:
            media=z.read(g['video_clip'])
            if sha(media)!=g['video_excerpt_sha256']:raise ValueError('source MP4 SHA mismatch')
            start,end=g['clip_seconds'];scan,events=sample_original_video(media,start,end)
            scans[g['session']]=scan
            for sec,b in events:
                frames[f'scene_changes/s{g["session"]}_{sec}.jpg']=b
        report=build_decision_context(data,scans)
        report['source_packet_sha256']=sha(source_zip.read_bytes())
        report['source_video_MP4_bytes_preserved']=True
        report['source_media_asset_count']=15
        report['new_source_video_derived_keyframes']=len(frames)
        report['private_machine_transcript_in_public_report']=False
        report_file.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        html='''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>بازبینی تغییرات تصویری آرتین</title><style>body{font:16px Tahoma,Arial;background:#f5f5f5;max-width:1080px;margin:auto;padding:18px;color:#1d1d1d} section{background:white;padding:16px;margin:12px 0;border-radius:10px}img{width:100%;max-width:640px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;padding:8px}.muted{color:#9b360b}</style></head><body><h1>ترتیب زمانی تغییرات دیده‌شده در فیلم اصلی</h1><p class="muted">هشدار: تفاوت پیکسل‌های صفحه به معنی تفاوت تصمیم معاملاتی نیست. متن گفتار ماشینی هنوز مستقلاً شنیده نشده؛ هیچ دستور معامله‌ای تأیید نشده است.</p><p><a href="review-original.html">باز کردن صفحه اصلی پخش صوت و فیلم</a></p>'''
        for g in report['episodes']:
            html+=f'<section><h2>جلسه {g["session"]} — {escape(g["chart"])} — {g["clip_seconds"][0]} تا {g["clip_seconds"][1]} ثانیه</h2><p>بررسی یک تصویر در هر ثانیه؛ {g["candidate_pixel_change_count"]} تغییر تصویری بزرگ‌تر از آستانه نمونه‌برداری یافت شد. این زمان‌ها دقت یک‌ثانیه‌ای دارند.</p><table><thead><tr><th>زمان فیلم اصلی</th><th>سهم پیکسل‌های تغییرکرده</th><th>تصویر استخراج‌شده از فیلم اصلی</th></tr></thead><tbody>'
            for e in g['candidate_changes']:
                p=f'scene_changes/s{g["session"]}_{e["second"]}.jpg'
                html+=f'<tr><td>{e["second"]}</td><td>{100*e["changed_fraction"]:.1f}٪</td><td><a href="{p}"><img loading="lazy" src="{p}" alt="فریم {e["second"]}"></a></td></tr>'
            html+='</tbody></table></section>'
        html+='<section><h2>تغییرات تصویری میان دو عبارت هر مقایسه</h2><table><thead><tr><th>جفت</th><th>جلسه</th><th>ثانیه‌های تغییر ثبت‌شده بین دو عبارت</th><th>وضعیت معنایی</th></tr></thead><tbody>'
        for p in report['pairs']:
            change_txt=', '.join(str(x) for x in p['intervening_sampled_screen_changes']) or 'بیش از آستانه ۸٪ یافت نشد'
            html+=f'<tr><td>{p["pair"]}</td><td>{p["session"]}</td><td>{escape(change_txt)}</td><td>تأییدنشده؛ بدون مجوز معامله</td></tr>'
        html+='</tbody></table></section><p>تمام فایل‌های صوتی، ویدئویی و تصاویر اولیه عیناً کپی شده‌اند. تصاویر اضافه‌شده صرفاً از فایل MP4 اصلی گرفته شده‌اند.</p></body></html>'
        with zipfile.ZipFile(result_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as out:
            for name in original_names:
                content=z.read(name)
                if name=='index.html':name='review-original.html'
                out.writestr(name,content)
            out.writestr('index.html',html.encode('utf8'))
            out.writestr('screen_timeline_private.json',report_file.read_bytes())
            for name,b in sorted(frames.items()):out.writestr(name,b)
        # Ensure source bytes preserved for every original media asset.
        with zipfile.ZipFile(result_zip) as fixed:
            for name in original_names:
                next_name='review-original.html' if name=='index.html' else name
                if sha(fixed.read(next_name))!=sha(z.read(name)):
                    raise ValueError(f'source archive member changed: {name}')
        return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('report',type=Path)
    x=p.parse_args();d=run(x.source,x.output,x.report)
    print(json.dumps({'sessions':len(d['episodes']),'pairs':len(d['pairs']),'events':sum(len(e['candidate_changes']) for e in d['episodes']),'new_keyframes':d['new_source_video_derived_keyframes'],'teacher_certified':False,'trades':0}))