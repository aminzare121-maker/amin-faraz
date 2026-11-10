#!/usr/bin/env python3
"""Attempt exact historical source WAV reconstruction from SHA-receipted MP4s.

Never treats PCM similarity or source video identity as old WAV hash equivalence.
Only an exact SHA-256 match upgrades a source's status. No trading/semantic claims.
"""
import hashlib, subprocess, json, wave, io
from pathlib import Path
ROOT=Path('/mnt/data/artin_original_19_21')
OUT=Path('/mnt/data/artin_exact_audio_reconstructed')
OUT.mkdir(exist_ok=True)
EXPECTED={
  's19_0efe':(19,3588,3912,'0efe686fad25071c0116250072dfb555d74cff65640f33f59e44dbfc7fac81e1'),
  's19_b964':(19,4188,4512,'b96434bd9989bce5096fe24ae7c4d8419475d0a23235aea6022bfaddec65ab20'),
  's21_d3ea':(21,1788,2112,'d3ea03e2be921aa3db944ab3d2f43402cf85639345bd32d53497d0259f1f3df2'),
}
def sha(data):return hashlib.sha256(data).hexdigest()
def revise_header(original):
    # Calibrated against independent archived WAV from lesson 20:
    # same PCM, older libavformat software tag. WAV LIST tag fixed-width.
    b=bytearray(original)
    target=b'ISFT\r\x00\x00\x00Lavf61.7.103\x00\x00'
    found=b.find(target)
    if found<0 or b.find(target,found+1)>=0:
        raise ValueError('expected unique FFmpeg 61 software tag not found')
    substitute=b'ISFT\x0e\x00\x00\x00Lavf60.16.100\x00'
    if len(target)!=len(substitute):raise ValueError('header size mismatch')
    b[found:found+len(target)]=substitute
    return bytes(b)

def main():
    entries=[]
    for key,(ses,start,end,target) in EXPECTED.items():
        p=OUT/f'{key}_ffmpeg61.wav'
        command=['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-i',str(ROOT/f'session_{ses}_original.mp4'),'-t',str(end-start),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(p)]
        subprocess.run(command,check=True)
        data=p.read_bytes();patched=revise_header(data)
        with wave.open(io.BytesIO(patched),'rb') as w:
            frames=w.getnframes();duration=frames/w.getframerate()
        match=(sha(patched)==target)
        if match:
            q=OUT/f'{key}_EXACT_SHA_MATCH.wav';q.write_bytes(patched)
        entries.append({'key':key,'session':ses,'source_clip_seconds':[start,end],'declared_old_wav_sha256':target,'derived_wav_sha256':sha(data),'patched_old_encoder_header_sha256':sha(patched),'matches_historical_wav_sha256':match,'duration_seconds':duration,'exact_restored_path':str(OUT/f'{key}_EXACT_SHA_MATCH.wav') if match else None})
        print(json.dumps(entries[-1],ensure_ascii=False),flush=True)
    report={'schema':'artin_historical_wav_header_calibration_v1','calibration_source':'Session 20 archived part12 shows PCM exactly matched and only 8-byte Lavf tag difference','results':entries,'source_wav_sha_exact_restored_count':sum(x['matches_historical_wav_sha256'] for x in entries),'semantic_verification':False,'orders_authorized':0}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
if __name__=='__main__':main()