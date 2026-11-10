#!/usr/bin/env python3
"""Annotate 14 original Artin AV review pairs with fail-closed lexical-only triage.
Copies every media asset byte-identically. No independent speech transcription,
no teacher rules, no chart execution, no broker integration.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import zipfile
from collections import Counter
from pathlib import Path

TRANSLATIONS={
  'FALSE_LEXICAL_FLIP_BOTH_WORDINGS_NEGATED':'دو عبارتِ متن ماشینی هر دو منفی‌اند؛ اختلاف واژگانیِ گزارش قدیم نادرست است',
  'NONCOMPARABLE_ACTION_CLAIM_IN_MACHINE_TEXT':'یک عبارت، تصمیم صریح مثبت ورود نیست؛ مقایسه به‌عنوان دو تصمیم متضاد معتبر نیست',
  'CONTEXT_DEPENDENT_OPPOSITE_WORDING_NOT_VERIFIED_CONFLICT':'جهت عبارت‌ها متفاوت است اما شرایط نمودار، نقش گوینده و صحت گفتار تأیید نشده‌اند',
  'UNRESOLVED_LEXICAL_CASE':'عبارت مبهم است و نیاز به بررسی شنیداری و تصویری دارد'
}
SCREEN={
 'TRADINGVIEW_XAUUSD_15M_ILLUSTRATED_CANDLES':'نمودار شماتیک XAUUSD در تایم‌فریم ۱۵ دقیقه',
 'WEBINAR_ROOM_NO_TRADING_CHART_VISIBLE':'صفحه وبینار؛ در فریم‌های این بازه نمودار معاملاتی دیده نمی‌شود',
 'TRADINGVIEW_ILLUSTRATED_SINGLE_CANDLE':'نمودار شماتیک XAUUSD با نمونه کندل',
 'TRADINGVIEW_EURUSD_15M_ANNOTATED_CHART':'نمودار EURUSD در تایم‌فریم ۱۵ دقیقه؛ نه نمودار طلا'
}

def build(old_zip:Path,triage_path:Path,new_zip:Path):
    report=json.loads(triage_path.read_text(encoding='utf-8'))
    cases=report.get('cases',[])
    if len(cases)!=14 or report['summary']['teacher_rules_certified']!=0 or report['summary']['mt5_trades_authorized']!=0:
        raise ValueError('Invalid or trading-enabled semantic triage')
    if len({(x['session'],tuple(sorted(u['segment_id'] for u in x['utterances']))) for x in cases})!=14:
        raise ValueError('Duplicate pair in triage')
    rows=[]
    for p in sorted(cases,key=lambda c:c['pair_number_original']):
        status=p['v2_wording_status']; screen=p['screen_type_visually_observed'];u=p['utterances']
        if status not in TRANSLATIONS or screen not in SCREEN or any(v['independently_heard'] or v['speaker_identity_verified'] for v in u):
            raise ValueError('Unknown source/false semantic approval')
        href=f"#source-{p['session']}-{p['source_wav_sha256'][:10]}"
        interval='؛ '.join(f"{x['start_seconds']:.2f}–{x['end_seconds']:.2f}" for x in u)
        transcript=' | '.join(x['machine_text_unverified'] for x in u)
        rows.append('<tr><td>%d</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td><a href="%s">گوش‌دادن و دیدن منبع</a></td></tr>'%
          (p['pair_number_original'],p['session'],html.escape(interval),html.escape(transcript),
           html.escape(TRANSLATIONS[status]+'؛ '+SCREEN[screen]),html.escape(href,quote=True)))
    intro='''<section id="triage-v2" style="border:1px solid #94a3b8;background:#fff"><h2>ارزیابی دقیق ۱۴ جفت — اصلاح موتور واژگانی</h2>
<p><strong>متن ماشینی است و مستقلاً با شنیدن صدای مدرس تأیید نشده.</strong>
«ورود نکردم» در موتور پیشین مثبت تشخیص داده می‌شد؛ این خطا اصلاح شده است. هیچ‌کدام مجوز معامله یا تأیید معنای مدرس نیستند.</p>
<p>نتیجه: ۱ خطای تشخیص منفی، ۴ جفت غیرقابل‌قیاس به‌عنوان دو تصمیم صریح، ۹ جفت نیازمند تطبیق دقیق شرایط.</p>
<p>هش چهار WAV مادر و نمونه‌های PCM چهار برش با آرشیو اصلی منطبق؛ ۱۶ تصویر یکتا با SHA-256 اصلی تأیید شده‌اند.</p>
<div style="overflow-x:auto"><table border="1" cellpadding="7" style="width:100%;border-collapse:collapse"><thead><tr><th>شماره</th><th>جلسه</th><th>زمان گفتار</th><th>واژه‌های ماشینی</th><th>وضعیت موقت</th><th>منبع</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<p>برای هر مورد روی «گوش‌دادن و دیدن منبع» بزنید؛ داخل بخش منبع، کل ویدئو و برش‌های زمان‌دارِ همان عبارت موجود است. مشاهده صفحه به معنی تأیید معنا نیست.</p></section>'''
    with zipfile.ZipFile(old_zip) as z:
        names=z.namelist()
        if names.count('index.html')!=1 or names.count('manifest.json')!=1:
            raise ValueError('Original review layout mismatch')
        old_html=z.read('index.html').decode('utf-8')
        old_manifest=json.loads(z.read('manifest.json'))
        if len(old_manifest.get('pairs',[]))!=14:
            raise ValueError('Original pair count changed')
        # Anchor original source groups without modifying their video/audio controls.
        final_html=old_html
        for source in old_manifest['sources']:
            sess=source['session']; sha=source['historical_original_wav_sha256'][:10]
            needle='<section><h2>جلسه '+str(sess)+'؛ منبع تاریخی WAV '+sha
            if final_html.count(needle)!=1:
                raise ValueError('Exact source HTML section missing or repeated')
            final_html=final_html.replace(needle, '<section id="source-'+str(sess)+'-'+sha+'"><h2>جلسه '+str(sess)+'؛ منبع تاریخی WAV '+sha,1)
        if '<body>' not in final_html:raise ValueError('No HTML body')
        final_html=final_html.replace('<body>','<body>'+intro,1)
        combined=dict(old_manifest)
        combined['lexical_triage_v2']={
          'summary':report['summary'],
          'private_triage_file':'ARTIN_14_MACHINE_CONFLICT_SEMANTIC_TRIAGE_PRIVATE_20261110.json',
          'independent_teacher_meaning_certified':False,
          'orders_authorized':0}
        with zipfile.ZipFile(new_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as out:
            for n in names:
                if n=='index.html':raw=final_html.encode('utf-8')
                elif n=='manifest.json':raw=(json.dumps(combined,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
                else:raw=z.read(n)
                out.writestr(n,raw)
            out.writestr('ARTIN_14_MACHINE_CONFLICT_SEMANTIC_TRIAGE_PRIVATE_20261110.json',
                (json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    with zipfile.ZipFile(old_zip) as z0,zipfile.ZipFile(new_zip) as z1:
        if z1.testzip():raise ValueError('Final ZIP CRC error')
        for n in names:
            if n in ('index.html','manifest.json'):continue
            if hashlib.sha256(z0.read(n)).digest()!=hashlib.sha256(z1.read(n)).digest():
                raise ValueError('Changed original source media')
        new_html=z1.read('index.html').decode()
        if new_html.count('href="#source-')!=14 or new_html.count('id="source-')!=4:
            raise ValueError('Unlinked case/source sections')
    return {'schema':'artin_14_lexical_triage_review_packet_v2','cases':14,'source_groups':4,
        'original_media_bytes_preserved':True,'machine_wording_corrections':report['summary']['classification_counts'],
        'teacher_meaning_verified':False,'orders_authorized':0,
        'private_archive_sha256':hashlib.sha256(new_zip.read_bytes()).hexdigest()}

def main():
    p=argparse.ArgumentParser();p.add_argument('prior_zip',type=Path);p.add_argument('triage_json',type=Path)
    p.add_argument('new_zip',type=Path);p.add_argument('receipt_json',type=Path)
    a=p.parse_args();r=build(a.prior_zip,a.triage_json,a.new_zip)
    a.receipt_json.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False))
if __name__=='__main__':main()