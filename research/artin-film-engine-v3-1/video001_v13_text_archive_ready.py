#!/usr/bin/env python3
"""V13 text-only archiver after source, ASR, student-chat OCR and board OCR proof.

Atomic output, source byte preservation, SHA256 for each text output, strict
fail-closed verification. This does NOT transport to ChatGPT Library; archival
storage transfer and independent semantic verification are separate stages.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,time,zipfile
from pathlib import Path

TEXT_EXT={'.json','.jsonl','.txt','.srt','.vtt','.md','.csv','.tsv'}
MAGAZINE=re.compile(r'^[a-z][a-z0-9-]{2,50}$')
QUEUE=re.compile(r'^video-q-[0-9]{4}-[a-z0-9-]{4,64}$')

def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def readj(p):return json.loads(Path(p).read_text(encoding='utf8'))

def collect(root,prefix,*,require=True):
    root=Path(root).resolve()
    if not root.is_dir():raise FileNotFoundError(f'ARCHIVE_SOURCE_DIRECTORY_MISSING:{prefix}')
    fs=sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in TEXT_EXT)
    if require and not fs:raise ValueError(f'ARCHIVE_TEXT_CATEGORY_MISSING:{prefix}')
    return [(f'{prefix}/{p.relative_to(root).as_posix()}',p) for p in fs]

def package(out,magazine_id,queue_id,source_summary,source_proof,asr_root,ocr_root,board_ocr_root,verified_export_root):
    if not MAGAZINE.fullmatch(magazine_id) or not QUEUE.fullmatch(queue_id):raise ValueError('INVALID_REGISTERED_VIDEO_ID')
    out=Path(out).resolve()
    if out.exists() or out.with_name(out.name+'.part').exists():raise FileExistsError('RAW_ARCHIVE_NEVER_OVERWRITTEN')
    start=time.monotonic()
    source=readj(source_summary);proof=readj(source_proof)
    sha=source.get('source_video_sha256')
    if not (isinstance(sha,str) and len(sha)==64 and sha==proof.get('original_source_video_sha256')
        and source.get('source_integrity_verified') is True and proof.get('source_evidence_loss')==0
        and proof.get('independent_hash_and_time_evidence_complete') is True):
        raise ValueError('NOT_SOURCE_VERIFIED')
    original_chat=source.get('original_chat_images_selected',0)
    original_board=source.get('original_board_frames',0)
    all_parts=source.get('source_global_audio_chunks',0)
    if any(type(n)!=int or n<=0 for n in (original_chat,original_board,all_parts)):
        raise ValueError('ORIGINAL_SOURCE_COUNTS_MISSING')
    board=readj(Path(board_ocr_root)/'board_ocr_candidates_PRIVATE.json')
    if (board.get('source_video_sha256')!=sha or board.get('frames_processed')!=original_board
        or board.get('missing_frames')!=0 or len(board.get('results',[]))!=original_board):
        raise ValueError('BOARD_OCR_INCOMPLETE_OR_MISATTRIBUTED')
    # Every OCR partition must be present and marked complete. Existing raw
    # JSON bytes are copied exactly, never edited or partially reconstructed.
    expected_ocr=source.get('original_ocr_workers')
    # Strict verifier adds hardlinks to the same OCR JSON files. Count one
    # partition per worker instead of treating aliases as duplicate evidence.
    ocr_base=Path(ocr_root)
    ocr_files=[]
    for i in range(expected_ocr):
        canonical=ocr_base/f'video001-fast-ocr-{i}'/'full_chat_ocr_candidates_PRIVATE.json'
        matches=[p for p in ocr_base.glob(f'*-ocr-{i}/full_chat_ocr_candidates_PRIVATE.json')]
        if canonical.is_file():ocr_files.append(canonical)
        elif len(matches)==1:ocr_files.append(matches[0])
        else:raise ValueError(f'MISSING_OR_AMBIGUOUS_OCR_WORKER:{i}')
    if len(ocr_files)!=expected_ocr:raise ValueError('MISSING_OCR_TEXT_PARTITION')
    observed=[]
    for p in ocr_files:
        doc=readj(p)
        if doc.get('complete') is not True:raise ValueError('OCR_TEXT_PARTITION_UNFINISHED')
        observed.extend(row.get('frame_id') for row in doc.get('results',[]))
    if len(observed)!=original_chat or len(observed)!=len(set(observed)):
        raise ValueError('OCR_IMAGE_TEXT_COVERAGE_OR_DUPLICATION')
    if proof.get('original_five_minute_audio_parts')!=all_parts:
        raise ValueError('SPEECH_SOURCE_COVERAGE_MISMATCH')
    categories=[
      ('speech_asr_raw',asr_root),
      ('student_chat_ocr_raw',ocr_root),
      ('board_ocr_raw',board_ocr_root),
      ('verified_export_and_review_text_only',verified_export_root),
    ]
    allfiles=[]
    for category,root in categories:allfiles.extend(collect(root,category))
    idx={}
    for path,src in allfiles:
        if path in idx:raise ValueError('DUPLICATE_INTERNAL_ARCHIVE_PATH')
        idx[path]=src
    out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_name(out.name+'.part')
    written=[]
    try:
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
            for name,p in sorted(idx.items()):
                payload=p.read_bytes()
                digest=sha_bytes(payload)
                z.writestr(name,payload)
                written.append({'path':name,'size_bytes':len(payload),'sha256':digest})
            manifest={'schema':'ARTIN_V13_BEHROOZ_RAW_MACHINE_TEXT_UNVERIFIED_V1',
              'magazine_id':magazine_id,'queue_id':queue_id,
              'source_video_sha256':sha,'source_audio_parts':all_parts,
              'source_chat_ocr_images':original_chat,'source_board_ocr_images':original_board,
              'independently_verified_teacher_rules':0,
              'visual_chart_actions_completely_described':False,
              'raw_text_source_modified':False,
              'text_entry_count':len(written),'files':written}
            z.writestr('ORIGINAL_SOURCE_PROVENANCE_SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf8'))
        with zipfile.ZipFile(tmp) as z:
            if z.testzip():raise ValueError('ARCHIVE_CRC_FAILED')
            for p in written:
                if sha_bytes(z.read(p['path']))!=p['sha256']:
                    raise ValueError('ARCHIVE_EXTRACTED_TEXT_BYTES_CHANGED')
        tmp.replace(out)
    finally:
        if tmp.exists():tmp.unlink()
    seconds=round(time.monotonic()-start,3)
    result={'schema':'ARTIN_V13_TEXT_ARCHIVE_READY_RECEIPT_V1',
      'magazine_id':magazine_id,'queue_id':queue_id,
      'source_video_sha256':sha,'archive_text_only':True,'archive_bytes':out.stat().st_size,
      'archive_sha256':sha_bytes(out.read_bytes()),'archive_members':len(written),
      'archive_pack_and_local_verification_seconds':seconds,
      'target_under_60_met':seconds<60,
      'stored_in_chatgpt_library':False,
      'semantic_truth_human_verified':False}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for flag in ['out','source-summary','source-proof','asr-root','ocr-root','board-ocr-root','export-root']:
        p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--magazine-id',required=True);p.add_argument('--queue-id',required=True)
    a=p.parse_args()
    result=package(a.out,a.magazine_id,a.queue_id,a.source_summary,a.source_proof,a.asr_root,a.ocr_root,a.board_ocr_root,a.export_root)
    p=a.out.with_suffix('.safe_receipt.json');p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('V13_BEHROOZ_TEXT_ARCHIVE_READY='+json.dumps(result),flush=True)