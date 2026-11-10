"""Exact-source catalog for 14 unique provisional ASR polarity pairs.

Does not interpret speech, infer teacher rules, or authorize orders.
Unknown original WAVs remain unresolved even if some other archive overlaps in time.
"""
from __future__ import annotations
import argparse, hashlib, json, wave, io, zipfile
from collections import defaultdict
from pathlib import Path


def index_sources(archives):
    indexed = {}
    for path in archives:
        with zipfile.ZipFile(path) as z:
            wav_names = [n for n in z.namelist() if n.endswith('.wav')]
            if len(wav_names) != 1:
                raise ValueError('archive must have exactly one original WAV')
            name=wav_names[0]
            raw=z.read(name)
            sha=hashlib.sha256(raw).hexdigest()
            with wave.open(io.BytesIO(raw)) as wav:
                if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=16000:
                    raise ValueError('unexpected WAV shape')
                frames=wav.getnframes()
                actual=wav.readframes(frames)
                if len(actual)!=frames*wav.getnchannels()*wav.getsampwidth():
                    raise ValueError('truncated original WAV payload')
                duration=frames/wav.getframerate()
            manifest=json.loads(z.read('fast_av_manifest.json'))
            matches=[part for part in manifest.get('parts',[]) if part.get('audio')==name]
            if len(matches)!=1:raise ValueError('ambiguous original manifest member')
            item=matches[0]
            if item.get('audio_sha256') != sha:raise ValueError('manifest SHA differs from WAV')
            if abs((item['cut_end']-item['cut_start'])-duration)>.03:
                raise ValueError('original audio timebase differs from WAV duration')
            if sha in indexed:raise ValueError('duplicate SHA in scanned archives')
            indexed[sha]={'member':name,'start_seconds':item['cut_start'],'end_seconds':item['cut_end'], 'sha256':sha,
                          'archive_name':Path(path).name,'video_sha256':manifest.get('video_sha256')}
    return indexed


def reconcile(conflicts, source_index):
    if conflicts.get('summary',{}).get('candidate_polarity_flip_pairs')!=16:
        raise ValueError('unexpected 16-pair source document')
    pairs={}
    occurrences=0
    refs=defaultdict(list)
    for route in conflicts['routes']:
        events={e['source_segment_id']:e for e in route['events']}
        for p in route['candidate_polarity_flips']:
            occurrences+=1
            ids=tuple(sorted((p['first_segment_id'],p['second_segment_id'])))
            key=(p['session'],)+ids
            if key in pairs:
                refs[key].append(route['route_id']);continue
            if any(s not in events for s in ids):raise ValueError('pair segment absent from original route events')
            a,b=(events[s] for s in ids)
            if a['session']!=p['session'] or b['session']!=p['session']:
                raise ValueError('citation session mismatch')
            if a['source_audio_sha256']!=b['source_audio_sha256']:
                raise ValueError('two phrases are NOT from the same original WAV')
            sha=a['source_audio_sha256']
            source=source_index.get(sha)
            spans=sorted([(e['start_seconds'],e['end_seconds']) for e in (a,b)])
            if any(t1>=t2 for t1,t2 in spans):raise ValueError('invalid timed phrase')
            available=bool(source and all(source['start_seconds']<=x and y<=source['end_seconds'] for x,y in spans))
            pairs[key]={'session':p['session'],'segment_ids':list(ids),'source_audio_sha256':sha,
                        'phrases':spans,'source_status':'EXACT_SOURCE_SHA_AND_INTERVAL_MATCH' if available else 'UNRESOLVED_ORIGINAL_WAV',
                        'matched_archive':source['archive_name'] if available else None}
            refs[key].append(route['route_id'])
    if occurrences!=16 or len(pairs)!=14:raise ValueError('expected 16 occurrences, 14 distinct pairs')
    groups=defaultdict(lambda:{'pairs':0,'route_names':set(),'status':'UNRESOLVED_ORIGINAL_WAV','source_archive':None,'session':None})
    for key,item in pairs.items():
        g=groups[item['source_audio_sha256']]
        g['pairs']+=1
        g['route_names'].update(refs[key]);g['session']=item['session']
        if item['source_status']=='EXACT_SOURCE_SHA_AND_INTERVAL_MATCH':
            g['status']=item['source_status'];g['source_archive']=item['matched_archive']
    result={'schema':'artin_exact_source_14_unique_conflict_pairs_v1',
        'total_route_pair_occurrences':occurrences,'unique_pairs':len(pairs),
        'unique_source_wavs':len(groups),
        'source_groups':[{'session':v['session'],'source_audio_sha256':sha,'unique_pairs':v['pairs'],
             'routes':sorted(v['route_names']),'status':v['status'],'archive':v['source_archive']} for sha,v in sorted(groups.items(),key=lambda x:x[1]['session'])],
        'pair_details':[dict(p, routes=sorted(refs[k])) for k,p in sorted(pairs.items())],
        'speech_independently_heard':False,'teacher_rules_verified':0,'orders_authorized':0}
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--archive',action='append',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    data=reconcile(json.loads(args.input.read_text()),index_sources(args.archive))
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'pairs':data['unique_pairs'],'source_wavs':data['unique_source_wavs'],
        'matched':sum(g['status']=='EXACT_SOURCE_SHA_AND_INTERVAL_MATCH' for g in data['source_groups'])}))
if __name__=='__main__':main()