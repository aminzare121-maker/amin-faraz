"""Waveform alignment check; no transcription or listening claim."""
import sys,json,argparse
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir',type=Path,required=True,help='Local session directory containing media.mp4 and audio.flac')
parser.add_argument('--package-dir',type=Path,help='Optional existing site-packages directory; installs nothing')
args=parser.parse_args()
if args.package_dir:sys.path.insert(0,str(args.package_dir))
import av,numpy as np
root=Path(__file__).resolve().parent
source=args.source_dir
def extract(path,start,duration):
    rate=8000; samples=np.zeros(round(duration*rate),dtype=np.float64)
    with av.open(str(path)) as c:
        s=c.streams.audio[0];c.seek(int(start/s.time_base),stream=s,backward=True)
        res=av.AudioResampler(format='s16',layout='mono',rate=rate)
        for f in c.decode(s):
            if float(f.time)>start+duration+1:break
            for a in res.resample(f):
                offset=round((float(a.time)-start)*rate)
                lo=max(0,-offset);hi=min(a.samples,len(samples)-offset)
                if hi>lo:samples[offset+lo:offset+hi]=a.to_ndarray().reshape(-1)[lo:hi]
    return samples
rows=[]
for start in (533,730,2484):
    # Search +/-250ms at 0.5ms resolution. The extra margins avoid padding edges.
    video=extract(source/'media.mp4',start-.25,10.5)[::4]
    audio=extract(source/'audio.flac',start,10)[::4]
    audio=audio-audio.mean();scores=[]
    for shift in range(1001):
        candidate=video[shift:shift+len(audio)];candidate=candidate-candidate.mean()
        scores.append(float(np.dot(audio,candidate)/(np.linalg.norm(audio)*np.linalg.norm(candidate))))
    best=int(np.argmax(scores))
    rows.append({'start_seconds':start,'duration_seconds':10,'video_offset_relative_to_flac_seconds':(best-500)/2000,'normalized_correlation':scores[best],'correlation_at_zero_offset':scores[500]})
result={'method':'PCM waveform correlation; 8kHz mono decimated to 2kHz; lag search +/-0.25s, step0.0005s','windows':rows,'audio_semantics_verified':False,'max_abs_offset_seconds':max(abs(r['video_offset_relative_to_flac_seconds']) for r in rows)}
(root/'TIME_ALIGNMENT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

