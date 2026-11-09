#!/usr/bin/env python3
"""Package source-timed Artin teaching candidates for independent human review.

PRIVATE outputs may include transcribed user-supplied lesson speech. Do not
commit them to a public repository. No order is authorized by this tool.
"""
import argparse
import hashlib
import json
from bisect import bisect_left
from pathlib import Path
from artin_full_review_queue import build, load, norm, CONDITIONS


def packetize(root):
    root=Path(root)
    private, index=build(root)
    rows=load(root)
    packets=[];flags={"short_speech_fragment":0,"no_nearby_image":0,"context_only_condition":0,"literal_condition":0}
    for case in private['cases']:
        n=case['session'];start=case['time_start_seconds'];end=case['time_end_seconds']
        corpus=rows[n]; times=[x['start'] for x in corpus]
        i=bisect_left(times,start)
        # Avoid treating OCR or ASR words as verified teacher utterances.
        nearby=[r for r in corpus[max(0,i-100):min(len(corpus),i+110)]
                if r['end']>=start-22 and r['start']<=end+38]
        # Include at most 4000 characters to prevent large downstream prompts.
        loc=[{"start":round(r['start'],2),"end":round(r['end'],2),
              "unverified_machine_text":r['text'],"machine_segment_id":r['segment']}
             for r in nearby if r.get('text')]
        loc=loc[:60]
        raw=norm(case['speech_machine_candidate'])
        literal_conditional=any(term in raw for term in CONDITIONS)
        contextual=case['conditional_or_hypothetical_cue'] and not literal_conditional
        short=len(raw.split())<4
        no_visual=len(case['visual_candidates'])==0
        flags['short_speech_fragment']+=short
        flags['no_nearby_image']+=no_visual
        flags['context_only_condition']+=contextual
        flags['literal_condition']+=literal_conditional
        packet={
            'case_id':case['case_id'],'session':n,
            'speech_start_seconds':start,'speech_end_seconds':end,
            'source_audio_sha256':case['source_anchor']['source_audio_sha256'],
            'source_video_sha256_if_available':case['source_anchor']['source_video_sha256_if_available'],
            'source_segment_id':case['source_anchor']['segment_id'],
            'teaching_scenario_is_not_disqualified_by_hypothetical_wording':True,
            'market_example_type_candidate':case['candidate_class'],
            'literal_condition_in_selected_segment':literal_conditional,
            'conditional_keyword_only_in_surrounding_context':contextual,
            'short_fragment_needs_context':short,
            'visual_within_8s_available':not no_visual,
            'visual_source_candidates':case['visual_candidates'],
            'spoken_context_unverified':loc,
            'concept_topics_candidates':case['topics_for_review_only'],
            'teacher_audio_diarization_independently_verified':False,
            'literal_wording_confirmed_against_audio':False,
            'chart_image_meaning_verified':False,
            'entry_exit_exceptions_order_verified':False,
            'cross_lesson_correction_verified':False,
            'teacher_decision_expected':None,'motor_decision_observed':None,
            'motor_replay_verdict':'BLOCKED_SOURCE_SEMANTICS_UNVERIFIED',
            'approval_to_trade':False,
        }
        packets.append(packet)
    if len(packets)!=150 or len({x['case_id'] for x in packets})!=150:
        raise ValueError('Unexpected number of candidates; do not claim full coverage')
    if sorted({x['session'] for x in packets})!=list(range(1,26)):
        raise ValueError('Missing session in review packet')
    public={
        'schema':'artin_review_packets_25_v1',
        'machine_speech_sessions':25,'review_packets_count':len(packets),
        'flag_counts':flags,
        'clarification':'A conditional marker somewhere in nearby speech does not prove this exact segment states a trading rule or a hypothetical example.',
        'original_source_audio_listening_completed':False,
        'teacher_expected_decisions_verified':0,
        'engine_replays_against_teacher_verified':0,
        'mt5_trading_authorized':False,
        'all_cases_source_anchored':all(bool(c['source_audio_sha256']) for c in packets),
        'sessions':[{'session':n,'cases':sum(x['session']==n for x in packets),
                     'short':sum(x['session']==n and x['short_fragment_needs_context'] for x in packets),
                     'no_visual':sum(x['session']==n and not x['visual_within_8s_available'] for x in packets)}
                    for n in range(1,26)]}
    return {'schema':'artin_private_review_packets_25_v1','packets':packets,
            'source':'/بهروز private ASR/OCR archive; NOT the verified teacher transcript',
            'teacher_semantics_verified':False,'allow_mt5_trading':False}, public


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--private-out',type=Path,required=True)
    p.add_argument('--public-out',type=Path,required=True)
    a=p.parse_args()
    private,public=packetize(a.root)
    a.private_out.write_text(json.dumps(private,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    a.public_out.write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(public,ensure_ascii=False))
if __name__=='__main__':main()