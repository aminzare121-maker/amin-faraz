#!/usr/bin/env python3
"""Compare independent Persian printed-chat OCR on multiple authentic frames.

Only image-hash-verified text candidates, NEVER teacher identity or verified
strategy rules. OCR model loaded once. Raw student names/text stay private.
"""
import argparse
import json
from pathlib import Path
import time
from artin_persian_chat_ocr_trial_v7 import trial

SAMPLES=[
 {'id':'first_greeting',
  'source':'b001_s01_g000001_t0000015000_chat.png',
  'sha256':'1b080e3ca7a982f86380fe51f93537ef805789810386aa4b5085c598a6be058e',
  'roi':(.04,.14,.72,.23)},
 {'id':'microphone_problem',
  'source':'b001_s07_g000007_t0001965000_chat.png',
  'sha256':'26f7524e93268d9d764cd89b3f9804d22c002bea5e306b627be43a722d03d52f',
  'roi':(.1,.245,.94,.32)},
 {'id':'typed_question',
  'source':'b001_s12_g000012_t0003315000_chat.png',
  'sha256':'3645f5b17a14c51e50de059b2c255a23ed492e08cb070608244a0da2baf1a291',
  'roi':(.04,.8,.94,.92)}]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    source=a.input_dir.resolve()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    engine=None
    def reused_engine(**kwargs):
        nonlocal engine
        if engine is None:
            from paddleocr import PaddleOCR
            engine=PaddleOCR(**kwargs)
        return engine
    results=[]
    t=time.monotonic()
    for sample in SAMPLES:
        name=sample['source']
        if '/' in name or '\\' in name: raise ValueError('Disallowed unsafe filename')
        safe=trial(source/name,out/sample['id'],sample['sha256'],
                   roi=sample['roi'],ocr_factory=reused_engine)
        results.append({'id':sample['id'],
                        'source_frame_sha256':sample['sha256'],
                        'provisional_lines':safe['text_lines_candidate'],
                        'time_seconds':safe['runtime_seconds'],
                        'actual_text_human_verified':False})
    summary={'schema':'artin_persian_chat_ocr_batch_v7',
             'source_video_sha256':'b23c618eb63af8c91c77d9a451411091bf7f5a57edbc0b6fdc20e01b86bcc8ff',
             'original_frames_with_ocr':len(results),
             'summary':results,'elapsed_total_seconds':round(time.monotonic()-t,2),
             'independent_ground_truth_reference_checked':False,
             'characters_error_rate':None,
             'trade_rules_verified':0,'status':'UNVERIFIED_OCR_MULTI_SAMPLE'}
    (out/'batch_safe_summary.json').write_text(
        json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print('ARTIN_PERSIAN_OCR_BATCH='+json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
