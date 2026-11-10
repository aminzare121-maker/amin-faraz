"""Label exact speech-interval membership in a private Artin review packet.

A playable machine-ASR utterance is not, by itself, proof of teacher attribution,
semantic interpretation, or license to trade.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import wave
import io
import zipfile


def classify(source):
    if not isinstance(source, dict) or not isinstance(source.get('windows'), list):
        raise ValueError('invalid packet manifest')
    audit = {'schema':'artin_citation_scope_v3', 'windows':[], 'totals': {'fully_inside':0,'crosses_boundary':0,'outside':0}, 'semantics_verified':False,'orders_authorized':0}
    for w in source['windows']:
        lo, hi=w['start'],w['end']
        if not 0 <= lo < hi or not w['audio_start'] <= lo < hi <= w['audio_end']:
            raise ValueError('invalid citation/audio bounds')
        stats={'fully_inside':0,'crosses_boundary':0,'outside':0}
        for seg in w['asr']:
            a,b=seg['start'],seg['end']
            if not 0 <= a < b or a < w['audio_start'] or b > w['audio_end']:
                raise ValueError('ASR segment outside playable source')
            if a>=lo and b<=hi:kind='fully_inside'
            elif b>lo and a<hi:kind='crosses_boundary'
            else:kind='outside'
            seg['citation_scope']=kind
            seg['inside_citation_from']=max(a,lo) if kind!='outside' else None
            seg['inside_citation_until']=min(b,hi) if kind!='outside' else None
            seg['teacher_role_independently_verified']=False
            seg['teacher_decision_certified']=False
            # A question addressed to the teacher is not evidence that the teacher voiced a rule.
            seg['speaker_review_flag']='ADDRESSED_TO_TEACHER_POSSIBLE_STUDENT' if 'استاد' in seg.get('text_unverified','') else None
            stats[kind]+=1
            audit['totals'][kind]+=1
        audit['windows'].append({'id':w['id'],'route':w['route'],'queue_video':w['queue_video'],
            'citation_start':lo,'citation_end':hi,'counts':stats,
            'speaker_verified':False,'teacher_meaning_verified':False,'trade_action':'NO_TRADE'})
    return audit


def revise_packet(old_zip, new_zip):
    with zipfile.ZipFile(old_zip) as zin:
        names=zin.namelist()
        if names.count('manifest.json')!=1 or names.count('index.html')!=1:
            raise ValueError('packet layout mismatch')
        data=json.loads(zin.read('manifest.json'))
        report=classify(data)
        html=zin.read('index.html').decode('utf-8')
        for w in data['windows']:
            file=w['clip']
            # Validate source WAV duration against the original manifest window.
            with wave.open(io.BytesIO(zin.read(file)),'rb') as f:
                frames=f.getnframes()
                duration=frames/f.getframerate()
                actual_pcm=f.readframes(frames)
                expected_pcm_bytes=frames*f.getnchannels()*f.getsampwidth()
            if len(actual_pcm)!=expected_pcm_bytes:
                raise ValueError('WAV payload truncated despite declared duration')
            if abs(duration-(w['audio_end']-w['audio_start']))>0.05:
                raise ValueError('WAV and manifest duration mismatch')
            # Add a scoped, escaped label to each segment button after its timestamp.
            from html import escape
            for seg in w['asr']:
                offset=seg['start']-w['audio_start']
                token=f'data-file="{file}" data-offset="{offset:.3f}"'
                if token not in html:
                    raise ValueError('HTML segment/source coordinate mismatch')
                # Use exact open button scoped to this timestamp; avoid modifying another shared window.
                # Inline warning where the matching time and text appear.
                marker=f'<span class="tt">{seg["start"]:.2f}–{seg["end"]:.2f}</span>'
                if marker not in html:
                    raise ValueError('timestamp not rendered in HTML')
        # Improve audio integrity/attribution warnings without changing original UI timings.
        panel='''<section><h2>کنترل حدود استناد صوت</h2><p>برخی عبارت‌ها از مرز بازهٔ استناد عبور می‌کنند و فقط بخش تقاطع آن‌ها، زماناً داخل ارجاع است. این متن‌ها ماشینی و تأییدنشده‌اند؛ حتی عبارت کاملِ دارای صوت، به‌تنهایی دستور مدرس یا اجازه معامله نیست.</p><table style="width:100%;border-collapse:collapse" border="1" cellpadding="7"><thead><tr><th>ارجاع</th><th>داخل کامل</th><th>عبور از مرز</th><th>بیرون</th></tr></thead><tbody>'''
        for item in report['windows']:
            counts=item['counts']
            panel += f'<tr><td>{item["id"]}</td><td>{counts["fully_inside"]}</td><td>{counts["crosses_boundary"]}</td><td>{counts["outside"]}</td></tr>'
        panel += '''</tbody></table><p>عبارت‌های دارای خطاب «استاد» برای بررسی نقش گوینده علامت‌گذاری شده‌اند؛ شناسایی گوینده هنوز تأیید نشده است.</p></section>'''
        if '<script>' not in html:
            raise ValueError('expected review HTML UI missing')
        html=html.replace('<script>',panel+'<script>',1)
        # No private voices/images leave the archive; copied byte-identically.
        data['schema']='artin_6_original_av_listening_packet_v3_scoped_asr'
        data['citation_scope_audit']=report
        with zipfile.ZipFile(new_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as zout:
            for name in names:
                if name=='manifest.json': raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
                elif name=='index.html':raw=html.encode()
                else:raw=zin.read(name)
                zout.writestr(name,raw)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('old_zip');p.add_argument('new_zip');p.add_argument('audit_json')
    a=p.parse_args()
    audit=revise_packet(a.old_zip,a.new_zip)
    Path(a.audit_json).write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'windows':len(audit['windows']),'totals':audit['totals'],'authorized_orders':0}))
if __name__=='__main__':main()