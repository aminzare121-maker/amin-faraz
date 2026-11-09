#!/usr/bin/env python3
"""Reconcile legacy Artin 26-slot ASR numbering with current 25-film queue.

This audit compares old lesson chunk start-times to original video durations and
checks mapped citations against original archived machine-ASR windows. It does
NOT equate ASR with independently verified teacher speech, and does not confer
permission to make a trading decision. No old source or queued media is edited.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from artin_13_source_coverage_audit import SOURCE_CITATIONS, load_source, inspect_window
from artin_teacher_citation_duration_guard import VIDEO_DURATION_SECONDS

# Start time of last NONEMPTY ASR chunk as reported in old repository's
# SOURCE_COVERAGE.json, Git blob fa955ed57b8e4a2f64588dda0752909b6d8263d5.
# Legacy session 1 had no ASR. The old numbering continues through session 26.
LEGACY_LAST_NONEMPTY_CHUNK_START={
 2:4800,3:4800,4:4800,5:4200,6:4200,7:4800,8:4200,
 9:4800,10:4200,11:3600,12:1200,13:4200,14:4200,15:3600,
 16:3600,17:3000,18:4200,19:4800,20:4800,21:4800,22:3000,
 23:4800,24:3600,25:3600,26:4800,
}
LEGACY_COVERAGE_SHA='fa955ed57b8e4a2f64588dda0752909b6d8263d5'
CURRENT_REGISTRY_SHA='5dec2c82c4e2a895bd6f51744d8967b9911f342e'
LEGACY_ENTRY_ENGINE_SHA='2998d66f933f1edad4eccf7fb574b9f14007cf35'


def validate_shift(delta:int, chunk_starts=LEGACY_LAST_NONEMPTY_CHUNK_START,
                   durations=VIDEO_DURATION_SECONDS):
    """Strict range comparison; nonempty 600s chunk can extend beyond its start."""
    if type(delta) is not int: raise TypeError('integer offset required')
    mapped={};invalid=[];unmapped=[]
    for old,chunk_start in sorted(chunk_starts.items()):
        if type(old) is not int or type(chunk_start) is not int or chunk_start<0:
            raise ValueError('invalid old session chunk index')
        current=old+delta
        if current not in durations:
            unmapped.append(old)
            continue
        duration=durations[current]
        if type(duration) not in (int,float) or duration<=0:raise ValueError('invalid video duration')
        if chunk_start>=duration:
            invalid.append({'old_session':old,'current_video':current,
                            'last_nonempty_chunk_start':chunk_start,'video_duration':duration})
        mapped[old]=current
    return {'offset':delta,'mapped':len(mapped),
            'unmapped_sessions':unmapped,'chunk_start_exceeds_video':invalid,
            'all_25_mapped_without_duration_conflict':len(mapped)==25 and not unmapped and not invalid,
            'original_media_identity_sha_verified':False}


def remap_citation(legacy_session:int,start:float,end:float,
                   *,offset=-1,durations=VIDEO_DURATION_SECONDS):
    if type(legacy_session) is not int or type(offset) is not int:
        raise ValueError('integer source ID and offset required')
    video=legacy_session+offset
    if video not in durations or type(start) not in (int,float) or type(end) not in (int,float):
        raise ValueError('unmapped legacy citation or invalid timestamp')
    if not (0<=start<end<=durations[video]):
        raise ValueError('timestamp exceeds current video duration')
    return (video,start,end)


def reconcile(root:Path|None=None,*,include_private=False,
              citations=SOURCE_CITATIONS,durations=VIDEO_DURATION_SECONDS,
              chunk_starts=LEGACY_LAST_NONEMPTY_CHUNK_START):
    candidate=validate_shift(-1,chunk_starts,durations)
    unshifted=validate_shift(0,chunk_starts,durations)
    shifted_plus_one=validate_shift(+1,chunk_starts,durations)
    if not candidate['all_25_mapped_without_duration_conflict']:
        raise ValueError('legacy source-to-video offset fails whole-course preflight')
    if not isinstance(citations,dict) or len(citations)==0:raise ValueError('source citations required')
    sessions=load_source(Path(root)) if root is not None else None
    rules=[];all_windows=[];source_map={}
    for rule,refs in citations.items():
        if not isinstance(rule,str) or not rule.strip() or not isinstance(refs,(tuple,list)) or not refs:
            raise ValueError('invalid source rules')
        out=[];new=[]
        for old,start,end in refs:
            video,a,b=remap_citation(old,start,end,offset=-1,durations=durations)
            record={'legacy_session':old,'current_queue_video':video,
                    'start_seconds':a,'end_seconds':b,
                    'mapped_citation_within_original_video_duration':True,
                    'mapping_basis':'LEGACY_NONEMPTY_ASR_CHUNK_BOUNDARY_AND_CANONICAL_VIDEO_DURATION',
                    'original_video_identity_sha_verified':False,
                    'teacher_semantics_verified':False,
                    'trade_permission':False}
            if sessions is not None:
                evidence=inspect_window(sessions,video,a,b,include_private=include_private)
                record.update({
                    'current_original_asr_overlap_rows':evidence['machine_transcript_overlap_rows'],
                    'current_original_asr_source_file_sha256':evidence['source_file_sha256'],
                    'current_original_asr_coverage_fraction':evidence['machine_transcript_time_coverage_fraction'],
                    'current_original_board_sha_refs':evidence['unique_board_sha_references'],
                    'current_transcript_status':('TIMED_MACHINE_ASR_PRESENT_NEEDS_AUDIO_REVIEW' if evidence['machine_transcript_overlap_rows']
                                                 else 'MISSING_TIMED_ASR_NEEDS_SOURCE_RECOVERY'),
                })
                if include_private:
                    record['machine_asr_excerpts_not_teacher_verified']=evidence.get('matched_machine_asr_excerpts',[])
            new.append([video,a,b]);out.append(record);all_windows.append(record)
        rules.append({'rule_id':rule,'source_citations':out,'citation_count':len(out),
                      'candidate_mapping_only':True,
                      'teacher_rule_verified':False,
                      'trade_permitted':False})
        source_map[rule]=new
    if len(source_map)!=13 or len(all_windows)!=24:
        raise ValueError('unexpected legacy engine source map size')
    return {'schema':'artin_v13_legacy_to_current_video_mapping_v1',
            'provenance':{'legacy_asr_coverage_blob_sha':LEGACY_COVERAGE_SHA,
                          'current_course_registry_blob_sha':CURRENT_REGISTRY_SHA,
                          'older_engine_blob_sha':LEGACY_ENTRY_ENGINE_SHA},
            'proposed_mapping':'old_session minus 1 for legacy ASR sessions 2..26',
            'legacy_session_1_had_no_asr':True,
            'whole_course_shift_comparison':{
                'minus_one':{k:v for k,v in candidate.items() if k!='original_media_identity_sha_verified'},
                'zero':{k:v for k,v in unshifted.items() if k!='original_media_identity_sha_verified'},
                'plus_one':{k:v for k,v in shifted_plus_one.items() if k!='original_media_identity_sha_verified'},
            },
            'mapped_current_queue_videos':25,
            'legacy_entry_rule_ids':len(source_map),'legacy_citation_windows':len(all_windows),
            'legacy_citation_windows_out_of_current_video_duration':0,
            'with_current_asr_overlap':(sum(w.get('current_original_asr_overlap_rows',0)>0 for w in all_windows)
                                       if sessions is not None else None),
            'without_current_asr_overlap':(sum(w.get('current_original_asr_overlap_rows',0)==0 for w in all_windows)
                                          if sessions is not None else None),
            'evidence_level':'TIMING_AND_MACHINE_ASR_CORROBORATED_ORIGINAL_MEDIA_SHA_NOT_VERIFIED',
            'candidate_source_map_not_auto_installed':source_map,
            'rules':rules,
            'source_file_modification_performed':False,
            'teacher_speaker_and_wording_independently_verified':False,
            'teacher_strategy_rules_certified':0,
            'teacher_to_engine_matches_certified':0,
            'm15_trade_backtest_authorized':False,
            'mt5_trade_permitted':False,
            'note':'This repairs the 26-vs-25 session indexing mismatch in a separate candidate source map. The six transcript-absent cited windows still need evidence; SHA equality of original film/audio and teacher lesson interpretation remain unverified.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--asr-root',type=Path)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--private',action='store_true')
    args=p.parse_args()
    r=reconcile(args.asr_root,include_private=args.private)
    args.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:r[k] for k in ('mapped_current_queue_videos','legacy_entry_rule_ids','legacy_citation_windows','legacy_citation_windows_out_of_current_video_duration','with_current_asr_overlap','without_current_asr_overlap','teacher_strategy_rules_certified')},ensure_ascii=False))

if __name__=='__main__': main()