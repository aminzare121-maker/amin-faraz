"""V13 sampled classroom-board OCR. Preserve every source image and machine output.
No human verification, chart-action semantics, or verified teacher rules asserted.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, subprocess, time
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as fp:
        for block in iter(lambda:fp.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def process(board_root,output,*,workers=6,ocr_fn=None):
    board_root=Path(board_root).resolve();output=Path(output).resolve()
    if output.exists() and any(output.iterdir()):raise FileExistsError('BOARD_OCR_MUST_NOT_OVERWRITE_ANY_EXISTING_OUTPUT')
    if board_root==output or board_root.is_relative_to(output) or output.is_relative_to(board_root):
        raise ValueError('BOARD_OCR_OUTPUT_INSIDE_SOURCE')
    if not 1<=workers<=12:raise ValueError('INVALID_OCR_WORKER_COUNT')
    index=json.loads((board_root/'visual_timeline_v6.json').read_text(encoding='utf-8'))
    if index.get('schema')!='artin_classroom_visual_v6' or not index.get('rows'):
        raise ValueError('INVALID_V13_BOARD_SOURCE_INDEX')
    source_sha=index.get('source_video_sha256')
    if not isinstance(source_sha,str) or len(source_sha)!=64:raise ValueError('SOURCE_SHA_REQUIRED')
    inputs=[]
    for row in index['rows']:
        ref=row.get('board',{});rel=ref.get('path');digest=ref.get('sha256')
        if not isinstance(rel,str) or not isinstance(digest,str) or len(digest)!=64:raise ValueError('INVALID_BOARD_REF')
        file=(board_root/rel).resolve()
        if not file.is_relative_to(board_root) or not file.is_file() or sha(file)!=digest:
            raise ValueError('BOARD_IMAGE_SHA_MISMATCH')
        inputs.append((row,file,digest))
    ids=[x[0]['frame_id'] for x in inputs]
    if len(ids)!=len(set(ids)):raise ValueError('DUPLICATE_BOARD_SOURCE_FRAME')
    def predict(item):
        row,path,digest=item
        if ocr_fn is not None:
            candidate=ocr_fn(path)
        else:
            cmd=['tesseract',str(path),'stdout','-l','fas+eng','--psm','11']
            env={**os.environ,'OMP_THREAD_LIMIT':'1'}
            q=subprocess.run(cmd,capture_output=True,timeout=35,env=env)
            if q.returncode:raise RuntimeError('BOARD_TESSERACT_FAILED')
            candidate=q.stdout.decode('utf-8','replace')
        if not isinstance(candidate,str):raise TypeError('OCR_NOT_STRING')
        return {'frame_id':row['frame_id'],'time_original_video_seconds':row['time_seconds'],
         'source_frame_sha256':digest,'source_video_sha256':source_sha,
         'model':'tesseract-5/fas+eng/psm11','machine_text_raw':candidate,
         'state':'OCR_TEXT_CANDIDATE_UNVERIFIED' if candidate.strip() else 'OCR_NO_READABLE_TEXT_UNVERIFIED',
         'human_verified':False,'chart_action_semantics_verified':False,'speaker_verified':False,'teacher_rule_verified':False}
    tic=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results=list(pool.map(predict,inputs))
    if len(results)!=len(inputs) or any(results[i]['frame_id']!=ids[i] for i in range(len(ids))):
        raise ValueError('BOARD_OCR_ORDER_OR_COVERAGE_DRIFT')
    if any(sha(file)!=digest for _,file,digest in inputs):raise ValueError('BOARD_ORIGINAL_CHANGED_DURING_OCR')
    output.mkdir(parents=True,exist_ok=True)
    receipt={'schema':'V13_BOARD_TEXT_OCR_ALL_SAMPLED_SOURCE_FRAMES_V1',
        'source_video_sha256':source_sha,'sample_frames_total':len(inputs),
        'frames_processed':len(results),'missing_frames':0,'sample_seconds':index.get('sample_seconds'),
        'human_verified':False,'chart_action_semantics_verified':False,
        'elapsed_seconds':round(time.monotonic()-tic,3),'results':results}
    (output/'board_ocr_candidates_PRIVATE.json').write_text(json.dumps(receipt,ensure_ascii=False),encoding='utf-8')
    safe={k:v for k,v in receipt.items() if k!='results'}
    (output/'board_ocr_safe_summary.json').write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ARTIN_BOARD_OCR_SAMPLED_UNVERIFIED='+json.dumps(safe),flush=True)
    return safe

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--workers',type=int,default=6)
    a=p.parse_args();process(a.board_root,a.out,workers=a.workers)