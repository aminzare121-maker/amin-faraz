"""V13 executable opt-in: one FFmpeg video decode produces the original 1 Hz chat
change stream AND 30-second high-resolution board samples in parallel.

Does not mutate the movie, replace the V12 original frames, or claim OCR or
board interpretation. Quality equivalence must be verified before adoption.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

FRAME_SIZE=64*160


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as fp:
        for block in iter(lambda:fp.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def probe_duration(video):
    cmd=['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(video)]
    return float(subprocess.check_output(cmd,text=True).strip())


def run(video,out,expected_sha,*,duration=None,board_sample_s=30):
    if board_sample_s!=30:
        raise ValueError('CURRENT_CANDIDATE_ONLY_PRESERVES_30_SECOND_BOARD_GRID')
    video=Path(video).resolve();out=Path(out).resolve()
    if not video.is_file() or not expected_sha or len(expected_sha)!=64:
        raise ValueError('ORIGINAL_VIDEO_AND_SHA_REQUIRED')
    if out==video or out==video.parent or video.is_relative_to(out) or out.is_relative_to(video):
        raise ValueError('OUTPUT_MUST_NOT_TOUCH_ORIGINAL_MOVIE')
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('REFUSE_OVERWRITE_OR_REUSE_OF_EXISTING_VISUAL_EVIDENCE')
    if sha(video)!=expected_sha:
        raise ValueError('VIDEO_SOURCE_SHA_MISMATCH')
    actual=probe_duration(video)
    if duration is not None and abs(actual-float(duration))>.1:
        raise ValueError('VIDEO_SOURCE_DURATION_MISMATCH')
    out.mkdir(parents=True,exist_ok=True);board=out/'board_uninterpreted'
    board.mkdir(exist_ok=True)
    filt=("[0:v:0]split=2[c][b];"
          "[c]fps=1,crop=iw*0.19:ih*0.84:iw*0.71:ih*0.11,"
          "scale=64:160:flags=fast_bilinear,format=gray[chat];"
          "[b]select=if(isnan(prev_selected_t)\\,gte(t\\,15)\\,gte(t-prev_selected_t\\,30))[sample]")
    cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-i',str(video),
         '-filter_complex',filt,
         '-map','[chat]','-f','rawvideo','-pix_fmt','gray','pipe:1',
         '-map','[sample]','-fps_mode','vfr','-q:v','3',str(board/'board_frame_%06d.jpg')]
    started=time.monotonic()
    pipe=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    rows=[];last=None;selected_at=-30;count=0;chat_digest=hashlib.sha256()
    try:
        while True:
            buf=pipe.stdout.read(FRAME_SIZE)
            if not buf:break
            if len(buf)!=FRAME_SIZE:
                raise ValueError('TRUNCATED_CHAT_GRAY_SOURCE')
            chat_digest.update(buf)
            if last is None:metric=1.0
            else: metric=sum(abs(a-b) for a,b in zip(last,buf))/(255*FRAME_SIZE)
            selected=(last is None or metric>=.02 or count-selected_at>=30)
            if selected:selected_at=count
            rows.append({'second':count,'change_score':round(metric,6),
                         'change_above_threshold':metric>=.02,
                         'source_frame_selected':selected})
            count+=1;last=buf
    except BaseException:
        pipe.kill();pipe.communicate()
        raise
    err=pipe.communicate()[1]
    if pipe.returncode:
        raise RuntimeError('ONE_PASS_FFMPEG_FAILED: '+err.decode('utf8','replace')[-500:])
    boards=sorted(board.glob('board_frame_*.jpg'))
    expected_boards=math.ceil(actual/board_sample_s)
    extra_seek=0
    nominal=[15+30*i for i in range(len(boards))]
    # The final short 30s region has no t=15s midpoint: capture its own
    # real last visual frame via ONE bounded seek, never omit it silently.
    if len(boards)==expected_boards-1 and actual%board_sample_s>0:
        start=(expected_boards-1)*board_sample_s
        segment=actual-start
        target=min(actual-max(.05,min(1.0,segment/4)),start+board_sample_s/2)
        dest=board/f'board_frame_{expected_boards:06d}.jpg'
        cmd_tail=['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                  '-ss',str(round(target,3)),'-i',str(video),
                  '-frames:v','1','-q:v','3',str(dest)]
        subprocess.run(cmd_tail,check=True,capture_output=True,timeout=90)
        if not dest.is_file() or dest.stat().st_size<200:
            raise ValueError('FINAL_PARTIAL_BOARD_FRAME_UNAVAILABLE')
        extra_seek=1
        nominal.append(round(target,3))
        boards=sorted(board.glob('board_frame_*.jpg'))
    if len(boards)!=expected_boards:
        # This is an intentionally fail-closed pilot. Partial final 30s
        # section must never disappear unnoticed.
        raise ValueError(f'PARTIAL_BOARD_GRID_COUNT: {len(boards)} vs {expected_boards}')
    if count < math.floor(actual):
        raise ValueError(f'ONE_SECOND_CHAT_SCAN_INCOMPLETE: {count} vs {math.floor(actual)}')
    if sha(video)!=expected_sha:
        raise ValueError('SOURCE_MUTATED_DURING_SINGLE_PASS_SCAN')
    result={'schema':'video001_v13_one_pass_visual_candidate_v1',
        'video_sha256':expected_sha,'duration_seconds':actual,
        'chat_frames_one_second':count,'highres_board_frames':len(boards),
        'original_chat_gray_stream_sha256':chat_digest.hexdigest(),
        'board_frames_sha256':[sha(frame) for frame in boards],
        'board_timestamps_nominal_seconds':nominal,
        'tail_source_seeks':extra_seek,
        'change_selected_chat_frames':sum(x['source_frame_selected'] for x in rows),
        'ffmpeg_full_movie_video_decode_passes':1,
        'original_video_unchanged':True,'image_meaning_verified':False,
        'all_typed_messages_verified':False,'model_ocr_ran':False,
        'quality_equivalence_with_v12_proven':False,
        'elapsed_seconds':round(time.monotonic()-started,3)}
    (out/'one_pass_candidate_review_only.json').write_text(json.dumps(result,indent=2))
    (out/'original_chat_change_timestamps_review_only.json').write_text(json.dumps(rows))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    a=p.parse_args()
    z=run(a.video,a.out,a.expected_sha256)
    print('V13_ONE_PASS_VISUAL_CANDIDATE='+json.dumps(z),flush=True)

if __name__=='__main__':main()