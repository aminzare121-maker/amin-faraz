#!/usr/bin/env python3
"""Reconcile original board frame timestamps with machine ASR for selected Artin cases.

An image missing from an automatically assembled 'nearby' list may still be
present in the original frame archive. This records that distinction without
claiming any teacher semantics or trading rule.
"""
import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
FRAME_TIME=re.compile(r'_t([0-9]+)_board\.png$')

def audit(root):
    root=Path(root)
    with zipfile.ZipFile(root/'Artin_Six_Source_Semantic_Cases_20261109.zip') as candidates:
        cases=json.loads(candidates.read('six_semantic_source_cases.json'))
    with zipfile.ZipFile(root/'Artin_66_Original_Frames_SourceLinked_20261109.zip') as wrapper:
        raw=wrapper.read('66_original_source_frames.zip')
    out=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as originals:
        for c in cases:
            p=c['proof'];n=c['seq'];t=p['speech_time_seconds'];rid=c['id']
            src=f'session_{n:02d}_all_machine_speech_review.jsonl'
            rows=[json.loads(line) for line in (root/'EXTRACTED_25_SESSIONS'/src).read_text(encoding='utf8').splitlines() if line]
            matches=[r for r in rows if abs(r['start_seconds']-t)<0.065 and r.get('machine_text_unverified')==p['speech_literal_exact']]
            if len(matches)!=1:
                raise ValueError('no unique timed speech for '+rid)
            r=matches[0]
            frame=p['visual_manifest_frame_archive_path'];expected=p['visual_SHA256']
            actual=hashlib.sha256(originals.read(frame)).hexdigest()
            if actual!=expected:raise ValueError('original frame SHA mismatch for '+rid)
            m=FRAME_TIME.search(p['visual_original_source_path'])
            if not m: raise ValueError('original board filename has no timestamp for '+rid)
            original_frame_time=int(m.group(1))/1000
            delta=abs(float(t)-original_frame_time)
            if delta>8.01:raise ValueError('unacceptably large visual/speech delta for '+rid)
            auto_present=any(v.get('frame_sha256')==actual for v in r.get('visual_source_nearby',[]))
            out.append({'case_id':rid,'session':n,'speech_time_seconds':t,
                        'original_board_time_seconds':original_frame_time,
                        'abs_delta_seconds':round(delta,3),
                        'original_image_sha256_verified':True,
                        'speech_excerpt_matched_by_time':True,
                        'original_image_in_automatic_nearby_list':auto_present,
                        'supplement_required':not auto_present,
                        'original_artifact_id':p.get('source_visual_artifact_id'),
                        'visual_source_type':'board_source_frame',
                        'teacher_semantics_verified':False,'mt5_trade_allowed':False})
    return {'schema':'artin_visual_provenance_supplement_v1','cases':out,
            'verified_original_board_frames':len(out),
            'missing_from_automatic_nearby_index':sum(x['supplement_required'] for x in out),
            'semantic_rules_certified':0,'trading_allowed':False,
            'scope':'Source frame bytes + original timestamp from frame filename + timed ASR; does not prove the shown screen demonstrates the trading rule'}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    ns=a.parse_args();result=audit(ns.root)
    ns.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('verified_original_board_frames','missing_from_automatic_nearby_index','semantic_rules_certified')},ensure_ascii=False))