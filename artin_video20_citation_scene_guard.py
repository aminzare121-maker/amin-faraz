"""Pinned-source original-image audit for the video 20 scene boundary.

This module does not automatically classify a visual or certify the teacher's rule.
Classification labels come from human inspection, tied to original SHA-256 bytes.
"""
import hashlib
import json
import math
import re
import zipfile
from pathlib import Path

RE = re.compile(r'^frames/.+_t(\d+)_original\.jpg$')


def verify_boundary(archive, labels):
    if not isinstance(labels, list) or len(labels) < 2:
        raise ValueError('At least two pinned original frame labels required')
    seen = set()
    with zipfile.ZipFile(archive) as z:
        members = {}
        for name in z.namelist():
            m = RE.match(name)
            if m:
                t = int(m.group(1)) / 1000
                if t in members:
                    raise ValueError('Duplicate frame timestamps in source archive')
                members[t] = name
        verified = []
        for entry in labels:
            t = entry.get('time_seconds')
            if type(t) not in (int, float) or not math.isfinite(t) or t in seen:
                raise ValueError('Invalid/duplicate frame time')
            seen.add(t)
            expected_name = entry.get('archive_member')
            if members.get(t) != expected_name:
                raise ValueError('Source frame identity mismatch')
            digest = hashlib.sha256(z.read(expected_name)).hexdigest()
            if digest != entry.get('sha256'):
                raise ValueError('Source frame SHA-256 mismatch')
            category = entry.get('observed_scene')
            if category not in {'educational_schematic', 'historical_price_chart', 'other_screen'}:
                raise ValueError('Unsupported human-scene observation')
            verified.append({'time_seconds':t,'archive_member':expected_name,
                            'sha256':digest,'observed_scene':category})
    verified.sort(key=lambda x:x['time_seconds'])
    schematic = [r for r in verified if r['observed_scene']=='educational_schematic']
    chart = [r for r in verified if r['observed_scene']=='historical_price_chart']
    if not schematic or not chart:
        raise ValueError('No observed scene transition')
    last_schematic = max(schematic,key=lambda r:r['time_seconds'])
    first_chart = min(chart,key=lambda r:r['time_seconds'])
    if last_schematic['time_seconds']>=first_chart['time_seconds']:
        raise ValueError('Observed scenes do not form transition interval')
    interior = [r for r in verified if last_schematic['time_seconds']<r['time_seconds']<first_chart['time_seconds']]
    if interior:
        raise ValueError('Unreviewed categories between transition endpoints')
    return {'schema':'artin_video20_pinned_original_visual_boundary_v1',
            'verified_original_frame_count':len(verified),
            'transition_observation':{'after_seconds':last_schematic['time_seconds'],
                                      'at_or_before_seconds':first_chart['time_seconds'],
                                      'exact_transition_time_known':False},
            'frames':verified,'teacher_audio_meaning_verified':False,
            'teacher_order_decision_verified':False,'trade_orders_authorized':0}


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('board_images_zip');p.add_argument('pinned_human_labels_json');p.add_argument('output_json')
    x=p.parse_args()
    doc=verify_boundary(x.board_images_zip,json.loads(Path(x.pinned_human_labels_json).read_text(encoding='utf8'))['frames'])
    Path(x.output_json).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in doc.items() if k!='frames'}))
if __name__=='__main__':main()