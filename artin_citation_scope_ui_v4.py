"""Render citation-scope warnings *at each playable utterance* in the Artin review packet.

Integrity-only, fail-closed. This NEVER confirms an instructor's wording/meaning or trading.
Private original WAV/image bytes are copied unchanged from the input ZIP.
"""
import hashlib
from html import escape
import io
import json
from pathlib import Path
import re
import wave
import zipfile
from artin_citation_scope_packet_v3 import classify

SECTION_RE = re.compile(r'(<section><h2>(ARTIN-RESTORED-\d\d)\b.*?</section>)', re.DOTALL)
BUTTON_RE = re.compile(r'<button\s+class="asr"\s+[^>]*data-file="([^"]+)"\s+data-offset="([^"]+)"[^>]*><span\s+class="tt">([^<]+)</span>(.*?)</button>', re.DOTALL)


def render_v4(original_zip, output_zip):
    with zipfile.ZipFile(original_zip) as source:
        if source.namelist().count('manifest.json') != 1 or source.namelist().count('index.html') != 1:
            raise ValueError('missing/duplicate review manifest or HTML')
        old = json.loads(source.read('manifest.json'))
        data = json.loads(json.dumps(old, ensure_ascii=False))
        audit = classify(data)
        if len(data['windows']) != 6:
            raise ValueError('expected the original six windows')
        page = source.read('index.html').decode('utf-8')
        # Rejection of prior transformation prevents quietly duplicated labels.
        if 'data-citation-scope=' in page:
            raise ValueError('already annotated or modified button')
        by_id = {w['id']: w for w in data['windows']}
        if len(by_id) != len(data['windows']):
            raise ValueError('duplicate citation IDs')
        seen_sections = set()
        rendered_buttons = 0
        counts = {'fully_inside': 0, 'crosses_boundary': 0, 'outside': 0}

        def section_replace(match):
            nonlocal rendered_buttons
            section, identity = match.group(1), match.group(2)
            if identity not in by_id or identity in seen_sections:
                raise ValueError('unexpected/duplicated citation section')
            seen_sections.add(identity)
            w = by_id[identity]
            spoken = w['asr']
            pointer = 0

            def button_replace(button_match):
                nonlocal pointer, rendered_buttons
                if pointer >= len(spoken):
                    raise ValueError('more buttons than ASR utterances')
                seg = spoken[pointer]
                pointer += 1
                filename, offset_str, span, button_text = button_match.groups()
                expected_offset = seg['start'] - w['audio_start']
                expected_span = f"{seg['start']:.2f}–{seg['end']:.2f}"
                if (filename != w['clip'] or offset_str != f'{expected_offset:.3f}'
                        or span != expected_span):
                    raise ValueError('audio button identity/timestamp mismatch')
                # Verify displayed speech content, not just its timestamp. Preserve exact original text.
                if button_text.strip() not in (escape(seg['text_unverified'], quote=False).strip(),
                        escape(seg['text_unverified'], quote=False).strip() +
                        ' [صوت اصلی این جمله بازیابی شد؛ متن ماشینی هنوز تأیید نشده است]'):
                    raise ValueError('displayed machine speech mismatches original manifest')
                status = seg['citation_scope']
                counts[status] += 1
                rendered_buttons += 1
                if status == 'fully_inside':
                    label = 'تمام عبارت در بازهٔ استناد'
                    css = 'scope-whole'
                elif status == 'crosses_boundary':
                    label = (f'عبارت مرزی؛ فقط {seg["inside_citation_from"]:.2f} تا '
                             f'{seg["inside_citation_until"]:.2f} داخل استناد است')
                    css = 'scope-edge'
                else:
                    label = 'صرفاً زمینهٔ گفتار؛ خارج از بازهٔ استناد'
                    css = 'scope-outside'
                role = (' | نقش گوینده بررسی شود' if seg['speaker_review_flag'] else
                        ' | گوینده هنوز تأیید نشده')
                # Explicit untrusted-automated-transcript warning for all segments.
                badge = (f'<span class="scope-note" aria-label="وضعیت استناد">'
                         f'{escape(label + role)}</span>')
                whole = button_match.group(0)
                whole = whole.replace('class="asr"', f'class="asr {css}" data-citation-scope="{status}"', 1)
                whole = whole.replace('</button>', badge + '</button>', 1)
                return whole

            changed, num = BUTTON_RE.subn(button_replace, section)
            if num != len(spoken) or pointer != len(spoken):
                raise ValueError('a speech segment missing its unique matching button')
            return changed

        page, nsections = SECTION_RE.subn(section_replace, page)
        if nsections != 6 or seen_sections != set(by_id):
            raise ValueError('not all original citation sections were found')
        if counts != audit['totals'] or rendered_buttons != sum(counts.values()):
            raise ValueError('rendered counts disagree with source audit')
        style = ('.scope-note{display:block;margin-top:5px;font:12px/1.6 Tahoma,Arial;'
                 'color:#6a3941;border-top:1px dashed #c3cbd5;padding-top:4px}'
                 '.scope-edge{border:2px solid #b96a23;background:#fff5eb}'
                 '.scope-outside{border:2px solid #a13c3c;background:#fff0f0}'
                 '.scope-whole .scope-note{color:#486151}')
        if '</style>' not in page:
            raise ValueError('review UI has no style element')
        page = page.replace('</style>', style + '</style>', 1)
        # Strong, near-top disclaimer to prevent interpreting badge as semantic approval.
        if '<h1>' not in page:
            raise ValueError('review UI has no heading')
        note = '<p><strong>برچسب‌ها فقط محدودهٔ زمانی استناد را نشان می‌دهند، نه درستی متن، هویت مدرس یا اجازه معامله.</strong></p>'
        page = page.replace('</h1>', '</h1>' + note, 1)
        data['schema'] = 'artin_6_original_av_review_v4_per_utterance_scope'
        data['citation_scope_audit'] = audit
        data['v4_rendering'] = {'rendered_buttons': rendered_buttons, 'sections': nsections,
                                'counts': counts, 'speaker_identity_verified': False,
                                'teacher_semantics_certified': False, 'orders_authorized': 0}
        with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as dest:
            for filename in source.namelist():
                if filename == 'manifest.json':
                    payload = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
                elif filename == 'index.html':
                    payload = page.encode()
                else:
                    payload = source.read(filename)
                dest.writestr(filename, payload)
        # Byte-for-byte original multimedia verification (not merely ZIP item names).
        with zipfile.ZipFile(output_zip) as dest:
            if set(source.namelist()) != set(dest.namelist()) or dest.testzip() is not None:
                raise ValueError('output packet ZIP corrupt or source objects missing')
            for filename in source.namelist():
                if filename not in ('index.html', 'manifest.json'):
                    if hashlib.sha256(source.read(filename)).digest() != hashlib.sha256(dest.read(filename)).digest():
                        raise ValueError('original media content modified')
        return {'schema': 'artin_scope_ui_v4_result', 'sections': nsections,
                'rendered_buttons': rendered_buttons, 'counts': counts,
                'original_multimedia_unchanged': True,
                'teacher_words_verified': False, 'orders_authorized': 0}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('input_zip');p.add_argument('output_zip');p.add_argument('result_json')
    args=p.parse_args()
    report=render_v4(args.input_zip,args.output_zip)
    Path(args.result_json).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
if __name__ == '__main__':main()