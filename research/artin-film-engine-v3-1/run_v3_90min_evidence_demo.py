"""A real 90-minute synthetic VIDEO with model responses MOCKED, never teacher evidence."""
from __future__ import annotations
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from artin_vision_scan import scan_vision
from artin_course_compiler import compile_course
from artin_film_pipeline import validate_model_events

SOURCE_ROOT=Path('/mnt/data/artin_90min_test_20261107/PRIVATE_RUN')
VIDEO=Path('/mnt/data/artin_90min_test_20261107/synthetic_full_90min.mp4')
OUT_ROOT=Path('/mnt/data/Artin_Film_Engine_V3/PRIVATE_V3_INTEGRATION')


def demo():
    OUT_ROOT.mkdir(parents=True,exist_ok=True)
    if not VIDEO.exists():
        raise FileNotFoundError('Input test video missing')
    # Reuse the exact previous 18-chunk manifest and its synthetic transcript;
    # new v3 vision runs from original mp4, not on screenshots manufactured by the mock.
    for name in ('manifest.json','unified_timeline.json','audit_report.json',
                 'rule_candidate_graph.json','artin_engine_handoff.json','noise_quarantine.json'):
        shutil.copy2(SOURCE_ROOT/name,OUT_ROOT/name)
    def fake_vision(model,prompt,frames=None,endpoint=None,system_prompt=None,**kwargs):
        req=json.loads(prompt)
        return {'observations':[{'frame_id':f['frame_id'],'scene_type':'UNKNOWN',
            'visible_text_candidate':'','visual_description_candidate':'MOCK: synthetic visual input',
            'related_to_trading_candidate':False} for f in req['frames']]}
    with patch('artin_vision_scan.ollama_json',side_effect=fake_vision):
        result=scan_vision(OUT_ROOT,'MOCK_ONLY_NO_REAL_MODEL',workers=3,
                           step_seconds=60,max_images_per_request=4)
    assert len(result)==18
    summary=json.loads((OUT_ROOT/'visual_scan_summary.json').read_text(encoding='utf8'))
    assert summary['chunks_scanned']==18
    assert summary['frames_extracted']>=80
    assert summary['full_teacher_video_understood_and_verified'] is False
    compiled=compile_course({'lessons':[{'session':21,'folder':str(OUT_ROOT)}]},expected_sessions=26)
    assert compiled['supplied_lessons']==1
    assert len(compiled['missing_sessions'])==25
    assert compiled['rules_approved']==0
    assert compiled['live_or_demo_orders_sent']==0
    out={'schema':'artin_v3_real_video_mock_models_test_v1',
         'real_video_bytes_processed':VIDEO.stat().st_size,
         'input_duration_seconds':float(json.loads((OUT_ROOT/'manifest.json').read_text())['source_duration']),
         'real_video_file_used':True,
         'chunk_count':len(result),
         'frames_physically_extracted_from_video':summary['frames_extracted'],
         'visual_model_was_real':False,
         'asr_model_was_real':False,
         'transcripts_were_synthetic':True,
         'visual_predictions_were_mocked':True,
         'visual_reference_checks_passed':True,
         'course_compiler_supplied_lessons':compiled['supplied_lessons'],
         'course_compiler_topics':compiled['candidate_topics'],
         'missing_classroom_sessions':len(compiled['missing_sessions']),
         'teacher_verified_rules':0,'orders_sent':0,
         'conclusion':'Video sampling and course record compilation work; true Persian speech/vision understanding NOT verified.'}
    (OUT_ROOT/'INTEGRATION_RESULT.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (OUT_ROOT/'COURSE_CANDIDATES_PRIVATE.json').write_text(json.dumps(compiled,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':demo()
