#!/usr/bin/env python3
"""Preserve original 103-second AV, build an evidence-ordered nine-pair teacher review.

All speech text is ASR UNVERIFIED. No teacher rule or trade is approved.
"""
from __future__ import annotations
import hashlib, html, io, json, re, wave, zipfile
from collections import Counter
from pathlib import Path

OPEN_IDS=(2,3,5,7,9,10,12,13,14)
REF_NOTES={
 19:{
  'chart':'XAUUSD', 'timeframe':'15m',
  'scene':'TradingView shows a schematic XAUUSD candle illustration, a blue zigzag, gray price band and red/green illustrative candles. Selection/annotation handles are repositioned across compared times.',
  'decision_review':'Are the conditions described for the red illustrative candle, the green illustrative candle, and the bar close the same hypothetical state? The frames do not prove that.',
  },
 21:{
  'chart':'EURUSD', 'timeframe':'15m',
  'scene':'TradingView shows EURUSD 15m, a downward break through a gray band and later changing selected horizontal line/rectangle levels. Several chart views are panned or annotated.',
  'decision_review':'Check the instructor\'s use of marubozu and candle close at the same referent; ASR wording is unreliable. No direct transfer of EURUSD-specific demonstration to XAUUSD.'
  }
}
REVIEW_FLAGS={
 'asr_75f20a08d03d0f34a402d3b5':'CONDITIONAL_NEGATIVE_IF_CLOSE',
 'asr_a5861a27824306d243b7beb3':'NEGATIVE_CLAIM_CONTEXT_MISSING',
 'asr_9547712adda0a68e4bbc935f':'POSITIVE_CLAIM_CONTEXT_MISSING',
 'asr_de7803476c6a715c938db9b1':'POSITIVE_CLAIM_CONTEXT_MISSING',
 'asr_b58dac6689a08dd5a1f6044d':'NEGATIVE_CLAIM_ASR_GARBLED',
 'asr_ca4236043bd0b39e6bce225d':'POSITIVE_CLAIM_ASR_GARBLED_MARUBOZU',
 'asr_5fce6f249e004a2b06749e03':'NEGATIVE_CLAIM_CONTEXT_MISSING',
 'asr_8c2847b85d75233330fedb72':'QUESTION_LIKE_MIXED_CLAIM_ASR_GARBLED',
 'asr_a7fa4433bb92a52ff93d9048':'POSITIVE_CLAIM_CONTEXT_MISSING',
}

def checksum(blob):return hashlib.sha256(blob).hexdigest()

def compile_review(archive, triage, receipt):
 if receipt['private_zip_sha256']!=checksum(archive):raise ValueError('source original-review package SHA mismatch')
 cases=[c for c in triage['cases'] if c['pair_number_original'] in OPEN_IDS]
 if len(cases)!=9 or {c['pair_number_original'] for c in cases}!=set(OPEN_IDS):raise ValueError('nine exact pairs required')
 unique={}
 for c in cases:
  if c['v2_wording_status']!='CONTEXT_DEPENDENT_OPPOSITE_WORDING_NOT_VERIFIED_CONFLICT':raise ValueError('unexpected case class')
  for seg in c['utterances']:
   sid=seg['segment_id']
   record={**seg,'session':c['session'],'review_flag':REVIEW_FLAGS.get(sid)}
   if record['review_flag'] is None:raise ValueError('unrecognized speaker segment: '+sid)
   if sid in unique and record!=unique[sid]:raise ValueError('duplicate source segment has inconsistent identity')
   unique[sid]=record
 if len(unique)!=9:raise ValueError('exactly 9 unique utterances expected')
 with zipfile.ZipFile(io.BytesIO(archive)) as z:
  if z.testzip() is not None:raise ValueError('corrupt original archive')
  assets=[n for n in z.namelist() if n.endswith(('.jpg','.wav','.mp4'))]
  if len(assets)!=15:raise ValueError('original AV asset count mismatch')
  sources={}
  for group in receipt['source_groups']:
   sess=group['session']
   if sess not in (19,21):raise ValueError('unexpected source')
   wblob=z.read(group['clip'])
   with wave.open(io.BytesIO(wblob),'rb') as w:
    if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(16000,1,2):raise ValueError('wrong sound format')
    frames=w.getnframes(); pcm=w.readframes(frames)
    if len(pcm)!=frames*2:raise ValueError('short PCM file')
    expected=group['clip_seconds'][1]-group['clip_seconds'][0]
    if abs(frames/16000-expected)>.002:raise ValueError('unexpected sound duration')
   sources[sess]={**group,'audio_excerpt_sha256':checksum(wblob),'video_excerpt_sha256':checksum(z.read(group['video_clip'])),**REF_NOTES[sess]}
  for seg in unique.values():
   if not(seg['start_seconds']<=seg['source_frame_time']<=seg['end_seconds']):raise ValueError('frame outside utterance')
   if checksum(z.read(seg['source_frame']))!=seg['source_frame_sha256']:raise ValueError('frame SHA mismatch')
   group=sources[seg['session']]
   if not(group['clip_seconds'][0] <= seg['start_seconds'] < seg['end_seconds'] <= group['clip_seconds'][1]):raise ValueError('utterance outside original playable WAV')
   seg['audio_relative_from_seconds']=round(seg['start_seconds']-group['clip_seconds'][0],2)
   seg['audio_relative_until_seconds']=round(seg['end_seconds']-group['clip_seconds'][0],2)
  result_cases=[]
  for c in sorted(cases,key=lambda x:x['pair_number_original']):
   pair=[unique[x['segment_id']] for x in c['utterances']]
   pair.sort(key=lambda x:x['start_seconds'])
   result_cases.append({'pair':c['pair_number_original'],'session':c['session'],'route_ids':c['route_ids'],
      'utterance_ids':[x['segment_id'] for x in pair],
      'relative_timing_seconds':[round(x['start_seconds']-sources[c['session']]['clip_seconds'][0],2) for x in pair],
      'action_compare_status':'SAME_TEACHER_SPEAKER_AND_SAME_CHART_REFERENT_NOT_VERIFIED',
      'visual_delta_directly_observed':REF_NOTES[c['session']]['scene'],
      'semantic_verdict':'UNRESOLVED_NOT_A_CONFIRMED_CONTRADICTION',
      'trade_authorized':False})
   
 out={'schema':'artin_9_conflict_pairs_consolidated_to_two_original_AV_decision_episodes_v1',
     'original_packet_sha256':checksum(archive),'source_group_count':2,
     'total_duration_seconds':sum(s['clip_seconds'][1]-s['clip_seconds'][0] for s in sources.values()),
     'source_media_assets_byte_preserved':len(assets),'nine_unique_speech_segments':len(unique),
     'candidate_pairs':len(result_cases),
     'source_groups':[{**s,'episode':'XAUUSD schematic candle comparison' if sid==19 else 'EURUSD breakdown annotation comparison',
       'machine_speech':[x for x in sorted(unique.values(),key=lambda y:y['start_seconds']) if x['session']==sid]}
       for sid,s in sorted(sources.items())],
     'pairs':result_cases,
     'source_acoustic_content_verified_as_original':True,'original_Persian_words_independently_heard':False,
     'speaker_identity_independently_verified':False,'teacher_semantics_verified':False,
     'same_chart_trade_situation_verified_for_any_pair':False,
     'XAUUSD_transfer_from_EURUSD_authorized':False,
     'mt5_orders_authorized':0}
 return out, assets

CSS='''body{background:#f6f7fa;color:#1f2733;font:16px Tahoma,Arial,sans-serif;line-height:1.75;margin:0 auto;padding:20px;max-width:1100px}h1,h2{color:#202d47}section{background:white;border:1px solid #ddd;border-radius:12px;margin:16px 0;padding:20px}table{width:100%;border-collapse:collapse}td,th{border:1px solid #ddd;padding:9px;text-align:right}video{width:100%;max-height:480px}audio{width:100%}.item{border-bottom:1px solid #e5e7eb;padding:10px 0}.item img{width:100%;max-width:650px;display:block;margin:10px 0}button{border:1px solid #789;background:#e9eef5;border-radius:7px;padding:8px;cursor:pointer}small{color:#555}code{direction:ltr} .warning{border-right:5px solid #a66;padding-right:12px}'''
JS='''let bounds={};function playAt(n,a,b){const el=document.getElementById('sound'+n);bounds[n]=b;el.currentTime=a;el.play();}for(const n of [19,21]){const a=document.getElementById('sound'+n);a.addEventListener('timeupdate',()=>{if(bounds[n]!==undefined && a.currentTime>=bounds[n]){a.pause();delete bounds[n];}});a.addEventListener('seeked',()=>{if(bounds[n]!==undefined && a.currentTime>bounds[n]+.5) delete bounds[n];});}'''

def html_review(report):
 parts=['<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>آرتین | دو پرونده تصمیم از ۹ جفت</title><style>',CSS,'</style></head><body><h1>بازبینی دو پرونده تصمیم از ۹ جفت آرتین</h1>',
  '<section class="warning"><b>هشدار اعتبار:</b> صدا و تصویر از منبع اصلی بازیابی و تطبیق شده‌اند، اما متن‌های پایین خروجی تشخیص ماشینی و تأییدنشده هستند. گوینده و منظور مدرس معلوم نشده‌اند و این صفحه دستور معامله نیست.</section>']
 for group in report['source_groups']:
  session=group['session'];p=group['clip_seconds']
  parts+=['<section><h2>جلسه ',str(session),' — ',html.escape(group['chart']),' / ۱۵ دقیقه</h2><p>',html.escape(group['scene']),'</p><p><b>سؤال بازبینی:</b> ',html.escape(group['decision_review']),'</p>',
     '<video controls preload="metadata" src="'+html.escape(group['video_clip'],quote=True)+'"></video>',
     '<audio id="sound'+str(session)+'" controls preload="metadata" src="'+html.escape(group['clip'],quote=True)+'"></audio>']
  for s in group['machine_speech']:
   a=s['audio_relative_from_seconds'];b=s['audio_relative_until_seconds']
   parts+=['<div class="item"><div><small>ثانیه ',f'{s["start_seconds"]:.2f}', ' تا ',f'{s["end_seconds"]:.2f}',' | ',html.escape(s['review_flag']),'</small></div>',
    '<p>',html.escape(s['machine_text_unverified']),'</p>',
    f'<button onclick="playAt({session},{a},{b})">پخش فقط این عبارت (متن تأییدنشده)</button>',
    '<img loading="lazy" src="',html.escape(s['source_frame'],quote=True),'" alt="تصویر اصلی در زمان همان گفتار"></div>']
  parts+=['</section>']
 parts+=['<section><h2>مقایسه ۹ جفت</h2><table><thead><tr><th>جفت</th><th>درس</th><th>شناسه دو عبارت</th><th>وضعیت</th></tr></thead><tbody>']
 for c in report['pairs']:
  parts+=['<tr><td>',str(c['pair']),'</td><td>',str(c['session']),'</td><td><small>',html.escape(' / '.join(c['utterance_ids'])),'</small></td><td>یکسانی شرایط تصمیم و نقش گوینده تأیید نشده</td></tr>']
 parts+=['</tbody></table><p>نتیجه: هیچ تناقض قطعی یا قانون معاملاتی تأیید نشد. دو قطعه ویدئو جای ۹ بازبینی تکراری را می‌گیرند.</p></section><script>',JS,'</script></body></html>']
 return ''.join(parts).encode('utf-8')

def build(source_file, triage_file, receipt_file, output_zip, output_report):
 source=Path(source_file).read_bytes();triage=json.loads(Path(triage_file).read_text());receipt=json.loads(Path(receipt_file).read_text());report,assets=compile_review(source,triage,receipt)
 Path(output_report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 with zipfile.ZipFile(io.BytesIO(source)) as zin,zipfile.ZipFile(output_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as zout:
  for name in assets:zout.writestr(name,zin.read(name))
  zout.writestr('review.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  zout.writestr('index.html',html_review(report))
 return report

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('original_zip');p.add_argument('triage_json');p.add_argument('receipt_json');p.add_argument('output_zip');p.add_argument('report_json');a=p.parse_args()
 r=build(a.original_zip,a.triage_json,a.receipt_json,a.output_zip,a.report_json)
 print(json.dumps({'unique_utterances':r['nine_unique_speech_segments'],'pairs':r['candidate_pairs'],'source_episodes':r['source_group_count'],'orders':0}))