"""Read-only citation/frame grounding audit. No teacher semantic certification.

Scene labels are human observations pinned to verified original frame SHA256s.
Unobserved time is never silently inferred from a nearby screenshot.
"""
import hashlib
import json
import math
import zipfile
from collections import Counter


def build_audit(board_zip, pinned_doc, citation_doc, transition_after=4215, transition_by=4245):
    pins = pinned_doc['frames']
    if not pins or len({p['time_seconds'] for p in pins}) != len(pins):
        raise ValueError('missing or repeated pinned timestamps')
    with zipfile.ZipFile(board_zip) as z:
        for p in pins:
            time = p['time_seconds']
            if type(time) not in (int, float) or not math.isfinite(time):
                raise ValueError('non-finite frame timestamp')
            if p['archive_member'] not in z.namelist():
                raise ValueError('missing original frame')
            digest = hashlib.sha256(z.read(p['archive_member'])).hexdigest()
            if digest != p['sha256']:
                raise ValueError('original frame digest mismatch')
    if not transition_after < transition_by:
        raise ValueError('invalid transition bracket')
    by_time = {p['time_seconds']: p for p in pins}
    if by_time.get(transition_after, {}).get('observed_scene') != 'educational_schematic':
        raise ValueError('missing pre-transition scene anchor')
    if by_time.get(transition_by, {}).get('observed_scene') != 'historical_price_chart':
        raise ValueError('missing post-transition scene anchor')

    session20 = [c for c in citation_doc['citations'] if c['session'] == 20]
    if not session20:
        raise ValueError('no session20 source citations')
    records = []
    for c in session20:
        start, end = c['source_start_seconds'], c['source_end_seconds']
        if not (math.isfinite(start) and math.isfinite(end) and start < end):
            raise ValueError('invalid citation time')
        inside = sorted((p for p in pins if start <= p['time_seconds'] <= end), key=lambda p: p['time_seconds'])
        # A screenshot at a moment cannot prove the state at any other moment.
        categories = sorted({p['observed_scene'] for p in inside})
        touches_transition_uncertainty = start < transition_by and end > transition_after
        if not inside:
            status = 'NO_DIRECT_FRAME'
        elif touches_transition_uncertainty or len(categories) > 1:
            status = 'SCENE_AMBIGUOUS'
        else:
            status = 'SAMPLED_FRAME_ONLY'
        prior = max((p for p in pins if p['time_seconds'] < start), key=lambda p: p['time_seconds'], default=None)
        after = min((p for p in pins if p['time_seconds'] > end), key=lambda p: p['time_seconds'], default=None)
        records.append({
            'citation_index': c['citation_index'], 'route_id': c['route_id'],
            'session': 20, 'start_seconds': start, 'end_seconds': end,
            'frames_strictly_inside': [{'seconds': p['time_seconds'], 'sha256': p['sha256'],
                'observed_scene': p['observed_scene']} for p in inside],
            'nearby_prior_frame_seconds_not_evidence': prior['time_seconds'] if prior else None,
            'nearby_later_frame_seconds_not_evidence': after['time_seconds'] if after else None,
            'observed_scene_classes': categories,
            'touches_unknown_transition_interval': touches_transition_uncertainty,
            'classification': status,
            'teacher_audio_meaning_verified': False,
            'observed_trade_sequence_verified': False,
            'trade_action': 'NO_TRADE'
        })
    counts = Counter(x['classification'] for x in records)
    return {'schema': 'artin_video20_citation_vs_19_hashed_frames_v1',
        'verified_pinned_frames': len(pins), 'session20_citations': len(records),
        'transition_after_seconds': transition_after,
        'transition_at_or_before_seconds': transition_by,
        'classification_counts': dict(counts), 'cases': records,
        'verified_teacher_decisions': 0, 'mt5_orders_authorized': 0}


def main():
    import argparse
    from pathlib import Path
    p = argparse.ArgumentParser()
    p.add_argument('board_zip'); p.add_argument('pinned_labels_json'); p.add_argument('citation_metadata_json'); p.add_argument('output_json')
    a = p.parse_args()
    result = build_audit(a.board_zip,
        json.loads(Path(a.pinned_labels_json).read_text(encoding='utf-8')),
        json.loads(Path(a.citation_metadata_json).read_text(encoding='utf-8')))
    Path(a.output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'cases'}, ensure_ascii=False))

if __name__ == '__main__':
    main()