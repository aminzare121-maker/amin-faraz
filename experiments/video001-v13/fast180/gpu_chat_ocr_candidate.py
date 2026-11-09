"""V13 optional GPU-only raw chat OCR candidate. Never changes any input evidence.

This candidate does NOT verify semantics, teacher intent, board/chart understanding,
or human accuracy and DOES NOT claim 180-second full-film throughput.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path


def sha(path: Path) -> str:
    d=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            d.update(chunk)
    return d.hexdigest()


def validate_index(index: dict, images: Path):
    if index.get('schema') != 'artin_change_selected_chat_v8':
        raise ValueError('Original change-selected index expected')
    source_hash=index.get('source_video_sha256')
    if not isinstance(source_hash,str) or len(source_hash)!=64:
        raise ValueError('Source SHA missing')
    rows=index.get('rows')
    if not isinstance(rows,list) or not rows: raise ValueError('No source frames')
    prev=-1.0;ids=set();selected=[]
    for row in rows:
        t=row.get('time_seconds');frame_id=row.get('frame_id');img=row.get('chat')
        if not isinstance(t,(int,float)) or t<=prev or not isinstance(frame_id,str) or frame_id in ids:
            raise ValueError('Missing or duplicate original frame/time')
        if not isinstance(img,dict):raise ValueError('Missing chat source image')
        file=(images/img.get('path','')).resolve()
        if not file.is_relative_to(images.resolve()) or not file.is_file():
            raise ValueError('Image missing or outside evidence root')
        expected=img.get('sha256')
        if expected!=sha(file): raise ValueError('Source screenshot SHA mismatch')
        selected.append((row,file,expected));prev=t;ids.add(frame_id)
    return source_hash,selected


def output_to_object(res):
    """Keep the engine's exact OCR payload (not reformat, filter or sort its lines)."""
    if isinstance(res,dict):return res
    data=getattr(res,'json',None)
    if callable(data):data=data()
    if isinstance(data,dict):return data
    raise TypeError('PaddleOCR result lacks accessible original JSON object; refuse approximation')


def run(index_path,images,out,*,batch_size=8,gpu_index=0,model_factory=None):
    index=json.loads(Path(index_path).read_text(encoding='utf8'))
    images=Path(images).resolve();out=Path(out).resolve()
    if type(batch_size) is not int or not 1<=batch_size<=32:raise ValueError('Bad batch size')
    if type(gpu_index) is not int or gpu_index<0: raise ValueError('Bad device')
    source,chosen=validate_index(index,images)
    if out.exists():raise FileExistsError('NEVER overwrite original raw or existing derived output')
    if out.is_relative_to(images) or images.is_relative_to(out):
        raise ValueError('Result must be stored outside the source images directory')
    if model_factory is None:
        import paddle
        if not str(paddle.device.get_device()).startswith('gpu'):
            raise RuntimeError('CUDA Paddle GPU unavailable. Refuse silent CPU fallback')
        from paddleocr import PaddleOCR
        model_factory=lambda: PaddleOCR(lang='fa',device=f'gpu:{gpu_index}',
            use_doc_orientation_classify=False,use_doc_unwarping=False,
            use_textline_orientation=False)
    model=model_factory()
    # Working directory is new; abort on any failure without a false COMPLETE receipt.
    out.mkdir(parents=True,exist_ok=False)
    records=[]
    try:
        for start in range(0,len(chosen),batch_size):
            block=chosen[start:start+batch_size]
            pred=model.predict([str(p) for _,p,_ in block])
            results=list(pred)
            if len(results)!=len(block):raise ValueError('Missing/reordered GPU OCR response count')
            for (row,path,expected),response in zip(block,results):
                if sha(path)!=expected:raise ValueError('Image changed during OCR inference')
                raw=output_to_object(response)
                if not isinstance(raw,dict):raise ValueError('Invalid raw OCR object')
                # Re-identification, never silently trust a matching array length alone.
                probe=raw.get('res',raw)
                if isinstance(probe,dict) and probe.get('input_path') is not None:
                    if Path(str(probe['input_path'])).resolve()!=path:
                        raise ValueError('OCR response/input path ordering mismatch')
                record={'frame_id':row['frame_id'],
                        'time_original_video_seconds':row['time_seconds'],
                        'source_frame_sha256':expected,
                        'source_video_sha256':source,
                        'paddle_raw_unmodified':raw,
                        'human_verified':False,
                        'speaker_verified':False,
                        'teacher_answer_verified':False}
                dest=out/('frame_%06d_OCR_RAW.json'%len(records))
                with dest.open('x',encoding='utf8') as f:
                    json.dump(record,f,ensure_ascii=False)
                    f.write('\n')
                records.append({'frame_id':row['frame_id'],'file':dest.name,'sha256':sha(dest)})
        index_out={'source_video_sha256':source,'frames_total':len(chosen),
            'raw_frames_saved':len(records),'model':'PaddleOCR fa GPU candidate',
            'all_source_sha_verified':True,'human_qa_accuracy_verified':False,
            'board_and_actions_textualized':False,'full_film_extracted':False,'records':records}
        with (out/'complete_manifest.json').open('x',encoding='utf8') as f:
            json.dump(index_out,f,ensure_ascii=False,indent=2)
        return index_out
    except BaseException:
        # Refuse to claim success. Existing partial raw outputs preserved for inspection.
        (out/'INCOMPLETE_OCR_REVIEW_REQUIRED.flag').write_text('Partial OCR; no complete result.\n',encoding='utf8')
        raise


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--index',type=Path,required=True)
    ap.add_argument('--images',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--gpu-index',type=int,default=0)
    ap.add_argument('--batch-size',type=int,default=8)
    a=ap.parse_args()
    result=run(a.index,a.images,a.out,batch_size=a.batch_size,gpu_index=a.gpu_index)
    print(json.dumps({'raw_frames_saved':result['raw_frames_saved'],
       'source_sha_verified':True,'full_90_min_extraction_proven':False}))

if __name__=='__main__':main()