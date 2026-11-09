#!/usr/bin/env python3
"""Produce 100% machine-ASR evidence inventory across 25 privately stored Artin lessons.

This index is a REVIEW INVENTORY, not human verification. All 25 lesson
speech rows retain source hashes, timestamps, raw text, and nearby visual
references, without marking a teacher strategy rule or a motor decision as
verified. Example/hypothetical language is never auto-rejected.

Usage: python artin_full_coverage_index.py --root PRIVATE_FOLDER \
    --out PRIVATE_ZIP --summary PUBLIC_SUMMARY_JSON
"""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from artin_full_review_queue import load, TOPIC_TERMS, CONDITIONS, norm


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def manifest_and_files(root):
    lessons = load(Path(root))
    if sorted(lessons) != list(range(1, 26)):
        raise ValueError('Exactly 25 ordered lesson sources required')
    files = {}
    stats = []
    all_refs = set()
    total = 0
    condition_total = 0
    visual_total = 0
    for session in range(1, 26):
        rows = lessons[session]
        if not rows:
            raise ValueError(f'Empty speech source in lesson {session}')
        packed = []
        last_start = -1
        for i, row in enumerate(rows):
            start, end = row['start'], row['end']
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or start < 0 or end < start:
                raise ValueError(f'Invalid time in lesson {session} row {i}')
            if start < last_start:
                raise ValueError(f'Out-of-order source in lesson {session} row {i}')
            last_start = start
            if len(row['audio_sha']) != 64:
                raise ValueError(f'Invalid source audio SHA in lesson {session} row {i}')
            text = norm(row['text'])
            payload = f'{session}|{i}|{start:.3f}|{end:.3f}|{row["audio_sha"]}|{row.get("segment")}'
            cid = 'ARTIN-EV-' + hashlib.sha256(payload.encode('utf8')).hexdigest()[:20]
            if cid in all_refs:
                raise ValueError(f'Duplicate candidate ID {cid}')
            all_refs.add(cid)
            found_conditions = [term for term in CONDITIONS if term in text]
            topics = [topic for topic, terms in TOPIC_TERMS.items() if any(term in text for term in terms)]
            vis = [{
                'kind': v.get('kind'), 'time_seconds': v.get('time'),
                'frame_sha256': v.get('sha'), 'reference': v.get('file'),
                'delta_seconds': v.get('delta_seconds')
            } for v in row['raw_visual'] if abs(v.get('delta_seconds', 1000)) <= 8]
            entry = {
                'record_id': cid, 'session': session, 'row': i,
                'start_seconds': start, 'end_seconds': end,
                'machine_text_unverified': text,
                'source_segment_id': row.get('segment'),
                'source_audio_sha256': row['audio_sha'],
                'source_video_sha256_if_available': row.get('video_sha'),
                'visual_source_nearby': vis,
                'literal_condition_markers': found_conditions,
                'possible_topics_review_only': topics,
                'hypothetical_case_not_rejected_as_invalid': True,
                'observed_historical_trade_proven': False,
                'independent_speaker_and_wording_review_passed': False,
                'teacher_meaning_verified': False,
                'teacher_entry_exit_exception_order_verified': False,
                'cross_session_meaning_review_passed': False,
                'engine_decision_compared_to_teacher': False,
                'trade_permitted': False,
                'status': 'NOT_SEMANTICALLY_REVIEWED',
            }
            packed.append(json.dumps(entry, ensure_ascii=False, separators=(',', ':')))
            condition_total += bool(found_conditions)
            visual_total += bool(vis)
        b = ('\n'.join(packed) + '\n').encode('utf8')
        name = f'session_{session:02d}_all_machine_speech_review.jsonl'
        files[name] = b
        stats.append({'session': session, 'rows': len(rows), 'file': name, 'sha256': sha256(b),
                      'rows_with_direct_condition_marker': sum(bool([x for x in CONDITIONS if x in norm(r['text'])]) for r in rows),
                      'rows_with_nearby_visual': sum(bool(r['raw_visual']) for r in rows)})
        total += len(rows)
    if total != 10235 or len(all_refs) != total:
        raise ValueError(f'Source changed: {total} rows; do not claim frozen baseline 10235')
    manifest = {
        'schema': 'artin_source_complete_review_inventory_v1',
        'privacy': 'PRIVATE; machine speech and visual references remain in user Library',
        'source_set': 'Behrooz ASR/OCR ZIP of original 25 submitted lessons',
        'session_count': 25, 'machine_speech_rows_covered': total,
        'rows_with_direct_condition_marker': condition_total,
        'rows_with_nearby_visual': visual_total,
        'all_rows_source_linked': True,
        'independently_verified_teacher_rules': 0,
        'engine_decisions_checked_against_original_teacher': 0,
        'all_evidence_machine_unverified': True,
        'mt5_trade_authorized': False,
        'files': stats,
        'scope': 'Completeness and provenance of machine speech rows; not an independent semantic review',
    }
    files['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    return manifest, files


def build(root, dest, summary):
    manifest, files = manifest_and_files(root)
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in files.items():
            z.writestr(name, data)
    with zipfile.ZipFile(dest) as z:
        if len(z.namelist()) != 26:
            raise ValueError('A 25-session archive and manifest is required')
        for name, data in files.items():
            if z.read(name) != data:
                raise ValueError('Archive round-trip differs: ' + name)
    Path(summary).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--summary', type=Path, required=True)
    args = p.parse_args()
    result = build(args.root, args.out, args.summary)
    print(json.dumps({'sessions': result['session_count'], 'rows': result['machine_speech_rows_covered'],
                      'condition_rows': result['rows_with_direct_condition_marker'],
                      'visual_rows': result['rows_with_nearby_visual'],
                      'meaning_verified': False, 'trading_allowed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()