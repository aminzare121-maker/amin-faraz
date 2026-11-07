#!/usr/bin/env python3
"""Merge separate original-video ASR partitions by GLOBAL source chunk ID.

Reject any missing, duplicate, forged or mismatched source evidence. Produces a
course *review* file; original speaker/teacher identity cannot be inferred.
"""
import argparse
import json
from pathlib import Path

from artin_teacher_av_review_v5 import review_real_asr


def merge_private_shards(folder: Path, out: Path):
    source=folder/'manifest_redacted.json'
    if not source.is_file():
        raise FileNotFoundError('Source manifest was not carried by partition zero')
    manifest=json.loads(source.read_text(encoding='utf8'))
    files=sorted(folder.glob('part_*_unverified.json'))
    if len(files)!=len(manifest['parts']):
        raise ValueError('Missing or unexpected number of audio transcript shards')
    shards=[json.loads(p.read_text(encoding='utf8')) for p in files]
    allids=[s.get('global_chunk') for s in shards]
    if sorted(allids)!=list(range(1,len(manifest['parts'])+1)):
        raise ValueError('Missing, duplicate or misordered global five-minute chunks')
    reports=sorted(folder.glob('partition_*_status.json'))
    if len(reports)<1:raise ValueError('No job provenance')
    statuses=[json.loads(p.read_text(encoding='utf8')) for p in reports]
    indexes=[s.get('shard_index') for s in statuses]
    if len(indexes)!=len(set(indexes)) or sorted(indexes)!=list(range(len(statuses))):
        raise ValueError('Duplicate or missing partition provenance')
    ids=[]
    for st in statuses:
        if st.get('source_video_sha256')!=manifest['video_sha256']:
            raise ValueError('Partition came from a different source video')
        if st.get('partition_count')!=len(statuses):
            raise ValueError('Unexpected partition count')
        if st.get('completed_global_parts')!=st.get('expected_global_parts'):
            raise ValueError('Partition is incomplete')
        idx=st.get('shard_index')
        canonical=[n for n in range(1,len(manifest['parts'])+1)
                   if (n-1)%len(statuses)==idx]
        if st.get('expected_global_parts')!=canonical:
            raise ValueError('Partition assignment is not source-global modulo schedule')
        ids.extend(st.get('completed_global_parts',[]))
    if sorted(ids)!=list(range(1,len(manifest['parts'])+1)):
        raise ValueError('Partition ownership is incomplete or duplicated')
    review=review_real_asr(manifest,shards)
    if review['parts_missing_asr'] or review['parts_with_asr']!=len(manifest['parts']):
        raise RuntimeError('Audio coverage is incomplete after merge')
    if review['teacher_answers_human_verified'] or review['rules_executable'] or review['real_orders_allowed']:
        raise RuntimeError('Unreviewed ASR cannot authorize teacher rules')
    out.mkdir(parents=True,exist_ok=True)
    (out/'complete_unverified_qa_evidence.json').write_text(
         json.dumps(review,ensure_ascii=False,indent=2),encoding='utf8')
    summary={'schema':'artin_real_17_part_qa_source_merge_v5',
         'video_sha256':manifest['video_sha256'],
         'source_duration_seconds':manifest['duration_seconds'],
         'global_parts':len(manifest['parts']),
         'partitions':len(statuses),
         'audio_transcript_coverage_complete':True,
         'source_audio_hash_checked':True,
         'sampled_frames':review['sampled_frames_count'],
         'visual_caption_model_ran':False,
         'full_original_audio_human_reviewed':False,
         'question_candidates':len(review['possible_questions_and_following_utterances']),
         'suspect_speech_segments':len(review['suspect_asr_lines']),
         'cross_boundary_review_candidates':len(review.get('cross_boundary_asr_review',[])),
         'cross_boundary_conflicts_or_gaps':review.get('cross_boundary_conflicts',0),
         'possible_late_teacher_corrections':len(review['possible_later_corrections']),
         'technical_or_mixed_noise_review_candidates':len(review['classroom_noise_or_mixed_review']),
         'trading_topics_not_rules':len(review['teaching_topics_not_rules']),
         'candidate_rule_statements':len(review['rule_candidates']),
         'teacher_answers_verified':0,
         'student_typed_questions_verified':0,
         'confirmed_speaker_identities':0,
         'rules_executable':0,
         'broker_or_mt5_actions':0,
         'status':'FULL_ASR_COVERAGE_BUT_TEACHER_MEANING_UNVERIFIED'}
    (out/'merge_summary.json').write_text(
         json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print('ARTIN_FINAL_REAL_MERGE='+json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args()
    merge_private_shards(a.input,a.out)


if __name__=='__main__':main()
