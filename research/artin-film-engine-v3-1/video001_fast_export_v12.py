#!/usr/bin/env python3
"""Non-destructive V12 evidence rehydration from already SHA-verified V13 sources."""
import argparse,json,shutil,hashlib
from pathlib import Path
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser()
    for name in ('proof-path','source-path','asr-path','ocr-root','chat-index','board-root','temporal-index','chat-images','out'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--audio-workers',required=True,type=int)
    p.add_argument('--ocr-workers',required=True,type=int)
    a=p.parse_args();out=a.out.resolve()
    if out.exists():raise FileExistsError('Refusing overwrite of original review')
    proof=json.loads(a.proof_path.read_text());source=json.loads(a.source_path.read_text())
    if proof.get('original_source_video_sha256')!=source.get('source_video_sha256') or proof.get('source_evidence_loss')!=0 or proof.get('independent_hash_and_time_evidence_complete') is not True:
        raise ValueError('Unverified source')
    if a.audio_workers!=source['source_audio_worker_count'] or a.ocr_workers!=source['original_ocr_workers']:
        raise ValueError('Worker count mismatch')
    pairs=[('SOURCE_PROOF.json',a.proof_path),('SOURCE_SUMMARY.json',a.source_path),('ASR_REVIEW_UNVERIFIED.json',a.asr_path),('CHAT_INDEX.json',a.chat_index),('TEMPORAL_INDEX.json',a.temporal_index)]
    for label,path in pairs:
        if not path.is_file():raise FileNotFoundError(path)
    if not a.board_root.is_dir() or not a.chat_images.is_dir() or not a.ocr_root.is_dir():
        raise FileNotFoundError('Original board/chat/OCR folder missing')
    out.mkdir(parents=True)
    manifest=[]
    def copy(src,dst):
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        if sha(src)!=sha(dst):raise ValueError('Evidence byte mismatch: '+str(src))
        manifest.append({'path':dst.relative_to(out).as_posix(),'bytes':dst.stat().st_size,'sha256':sha(dst)})
    for name,path in pairs:copy(path,out/name)
    for name,root in [('ORIGINAL_BOARD',a.board_root),('ORIGINAL_CHAT',a.chat_images),('OCR_UNVERIFIED',a.ocr_root)]:
        for f in sorted(root.rglob('*')):
            if f.is_file():copy(f,out/name/f.relative_to(root))
    (out/'EVIDENCE_MANIFEST.json').write_text(json.dumps({'schema':'V12_REHYDRATED_UNVERIFIED_SOURCE_EVIDENCE','source_sha256':source['source_video_sha256'],'original_bytes_preserved':True,'teacher_semantics_verified':False,'files':manifest},ensure_ascii=False,indent=2))
    print('V12_REHYDRATED_SOURCE_FILES='+str(len(manifest)),flush=True)
if __name__=='__main__':main()
