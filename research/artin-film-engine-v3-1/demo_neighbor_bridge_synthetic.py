#!/usr/bin/env python3
"""Run BOTH model stages on already prepared 18-chunk SYNTHETIC data.

All semantic events are invented for this test; the local model function is
mocked. This proves context plumbing, not any Persian lesson comprehension.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from unittest.mock import patch
import artin_film_pipeline as artin


def run(root: Path):
    root=Path(root).resolve()
    manifest=artin.load_manifest(root)
    if len(manifest['chunks']) != 18 or abs(manifest['source_duration']-5400)>0.2:
        raise ValueError('Require a prepared synthetic 90-minute 18-part fixture')
    def mock(model, prompt, frames=None, endpoint=None, system_prompt=None, **kwargs):
        data=json.loads(prompt)
        chunk=data['chunk']
        if 'segments' in data:
            return {'anchors':[{'source_id':s['id'], 'exact_quote':s['text'],
                 'kind': ('QUESTION' if chunk==1 else 'ANSWER' if chunk==2 and s['start']<310
                          else 'CORRECTION' if chunk==18 else 'CLASSROOM_NOISE' if 'اینترنت قطع' in s['text']
                          else 'RULE')}
                          for s in data['segments']]}
        previous=data['adjacent_five_minute_context']['previous']
        events=[]
        for s in data['transcript']:
            if not data['core_start']<=s['start']<data['core_end']:
                continue
            kind=('QUESTION' if chunk==1 else 'ANSWER' if chunk==2 and s['start']<310
                  else 'CORRECTION' if chunk==18 else 'RULE')
            item={'kind':kind,'source_ids':[s['id']], 'exact_quote':s['text'],
                  'rule_label':'قانون فرضی' if kind in ('RULE','CORRECTION') else '',
                  'decision':'BUY' if kind=='RULE' else 'NO_TRADE' if kind=='CORRECTION' else 'UNKNOWN',
                  'conditions':[]}
            if kind=='ANSWER' and previous['anchors']:
                item['related_context_ids']=[previous['anchors'][0]['id']]
            events.append(item)
        return {'events':events}
    with patch.object(artin,'ollama_json',side_effect=mock):
        caps=artin.build_context_capsules(root,'MOCK_SYNTHETIC',workers=6)
        out=artin.analyze(root,'MOCK_SYNTHETIC',workers=6,require_capsules=True)
    summary=artin.merge(root)
    if summary['candidate_rule_groups']!=1 or summary['possible_later_corrections']!=1:
        raise AssertionError('Failed to carry distant teacher-rule example through 18 chunks')
    if summary['possible_question_answer_links']!=1 or summary['cross_chunk_context_review_edges']!=1:
        raise AssertionError('Failed to link cross-boundary question/answer example')
    if summary['teacher_rules_approved']!=0 or summary['artin_rule_ready']:
        raise AssertionError('Synthetic model cannot approve teacher rules')
    result={'mode':'SYNTHETIC_MOCK_NO_TEACHER_AUDIO_OR_ACTUAL_LLM_UNDERSTANDING',
            'chunks':len(manifest['chunks']),
            'first_pass_context_capsules':len(caps),
            'second_pass_neighbor_analyses':len(out),
            'q_and_a_links':summary['possible_question_answer_links'],
            'distant_correction_links':summary['possible_later_corrections'],
            'neighbor_context_edges':summary['cross_chunk_context_review_edges'],
            'quarantined_noise':summary['quarantined_classroom_noise'],
            'teacher_verified_rules':0,'orders_sent':0}
    artin.atomic_json(root/'SYNTHETIC_NEIGHBOR_PASS_REPORT.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(run(args.out),ensure_ascii=False,indent=2))
