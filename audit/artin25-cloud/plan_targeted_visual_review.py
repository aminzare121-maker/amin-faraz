"""Choose time-aligned visual review candidates from EXISTING ASR, never approve rules."""
import base64,hashlib,io,json,os,pathlib,re,subprocess,zipfile
REPO='aminzare121-maker/amin-faraz'
def api(path):
 p=subprocess.run(['gh','api',f'repos/{REPO}/'+path],capture_output=True,timeout=120)
 if p.returncode:raise RuntimeError('GITHUB_SOURCE_READ_FAILED')
 return json.loads(p.stdout)
def blob(sha):
 data=base64.b64decode(api('git/blobs/'+sha)['content'])
 if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=sha:raise ValueError('BLOB_CHANGED')
 return data
def archive(a):
 p=subprocess.run(['gh','api',f'repos/{REPO}/actions/artifacts/{a["id"]}/zip'],capture_output=True,timeout=300)
 if p.returncode:raise RuntimeError('EXISTING_TEXT_ARCHIVE_READ_FAILED')
 if len(p.stdout)>256*1024**2:raise ValueError('TEXT_ARCHIVE_LIMIT')
 return p.stdout
def documents(data,depth=0):
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  if sum(i.file_size for i in z.infolist())>512*1024**2:raise ValueError('TEXT_EXPANSION_LIMIT')
  for i in z.infolist():
   if i.is_dir():continue
   if i.filename.lower().endswith('.zip') and depth<1 and 'text' in i.filename.lower():
    yield from documents(z.read(i),depth+1)
   elif i.filename.lower().endswith('.json') and 'part_' in i.filename and 'unverified' in i.filename:
    raw=z.read(i)
    yield i.filename,hashlib.sha256(raw).hexdigest(),json.loads(raw)
seq=int(os.environ['SEQUENCE'])
registry=json.loads(blob('5dec2c82c4e2a895bd6f51744d8967b9911f342e'))
session=next(s for s in registry['registered_sessions'] if s['sequence']==seq)
seed=json.loads(pathlib.Path('audit/artin25-cloud/targeted_visual_seeds.json').read_text(encoding='utf-8'))
seeds=[s for s in seed['seeds'] if s['sequence']==seq]
if seq==2:
 seeds += [dict(start_seconds=990,end_seconds=1030,prior_node_id='MANUAL_CONTRACT_SIZE_EXAMPLE'),dict(start_seconds=1398,end_seconds=1512,prior_node_id='MANUAL_NUMERIC_ASR_CONFLICT')]
run=int(session['source_audio_run'].split('/')[-1])
artifacts=api(f'actions/runs/{run}/artifacts?per_page=100')['artifacts']
selected=[a for a in artifacts if not a['expired'] and ('text-only' in a['name'].lower() or 'text_only' in a['name'].lower())]
if not selected:
 if seq==3:
  run=42426863832
  artifacts=api(f'actions/runs/{run}/artifacts?per_page=100')['artifacts']
 selected=[a for a in artifacts if not a['expired'] and re.search(r'fast-asr-\d+$',a['name'])]
rows=[];read_archives=[];errors=[]
for a in selected:
 try:
  raw=archive(a);read_archives.append(dict(id=a['id'],archive_sha256=hashlib.sha256(raw).hexdigest()))
  for name,digest,doc in documents(raw):
   if doc.get('source_video_sha256')!=session['source_sha256']:raise ValueError('TRANSCRIPT_SOURCE_MISMATCH')
   if doc.get('timebase')!='absolute_original_video_seconds':raise ValueError('TRANSCRIPT_TIMEBASE_UNVERIFIED')
   for index,s in enumerate(doc.get('segments',[])):
    start=float(s['start']);end=float(s['end'])
    if not 0<=start<=end<=session['duration_seconds']+0.1:raise ValueError('TRANSCRIPT_TIME_OUTSIDE_SOURCE')
    rows.append(dict(start=start,end=end,text=s['text'],id=s.get('id',str(index)),audio_sha256=doc.get('source_audio_sha256'),transcript_sha256=digest,member=name,artifact_id=a['id'],avg_logprob=s.get('avg_logprob'),no_speech_prob=s.get('no_speech_prob')))
 except Exception as exc:errors.append(dict(artifact_id=a['id'],error_type=type(exc).__name__))
rows.sort(key=lambda r:(r['start'],r['end'],r['artifact_id']))
# Identical overlap records are duplicate evidence, never independent confirmations.
unique=[];seen=set()
for r in rows:
 k=(r['start'],r['end'],r['text'])
 if k not in seen:seen.add(k);unique.append(r)
rows=unique
visual_nouns=r'کندل|بدنه|سایه|گره|پیوت|نمودار|چارت|فیبو|ناحیه|نقطه|ماشین حساب'
pointer=r'این|همین|اون|آن|اینجا|اینو|اینجارو'
pointing=re.compile('('+pointer+').{0,35}('+visual_nouns+')|('+visual_nouns+').{0,25}(ببین|نگاه|نشون|نشان|رسم|کشید)')
candidates=[]
for i,r in enumerate(rows):
 text=r['text'];links=[s['prior_node_id'] for s in seeds if r['end']>=s['start_seconds'] and r['start']<=s['end_seconds']]
 reasons=[]
 if pointing.search(text):reasons.append('EXPLICIT_VISUAL_REFERENCE')
 if links and re.search(r'ببین|نگاه|نشون|نشان|مثال|مثلا|مثلاً|رسم|کشید|عدد|بالا|پایین|نیمه|سایه|بدنه|کندل|خط|ناحیه',text):reasons.append('PRIOR_TEXT_AMBIGUITY_VISUAL_EXAMPLE')
 if links and re.search(r'اشتباه|اصلاح|منظورم|برعکس|استثنا',text):reasons.append('MATERIAL_CORRECTION_IN_PRIOR_REVIEW')
 audio_uncertain=(r['avg_logprob'] is not None and r['avg_logprob']<-1) or (r['no_speech_prob'] is not None and r['no_speech_prob']>.6)
 if reasons:
  candidates.append(dict(segment=r,reason_codes=reasons,prior_node_ids=links,review_start=max(0,r['start']-12),review_end=min(session['duration_seconds'],r['end']+20),context=rows[max(0,i-2):i+4],audio_review_required=audio_uncertain,teacher_role_verified=False,image_example_relation_verified=False))
windows=[]
for c in candidates:
 start,end=c['review_start'],c['review_end']
 if windows and start<=windows[-1]['end_seconds']+5:
  windows[-1]['end_seconds']=max(windows[-1]['end_seconds'],end);windows[-1]['candidate_count']+=1
 else:windows.append(dict(start_seconds=start,end_seconds=end,candidate_count=1))
duration=sum(w['end_seconds']-w['start_seconds'] for w in windows)
result=dict(sequence=seq,source_sha256=session['source_sha256'],source_run=run,transcript_segments=len(rows),source_archives=read_archives,errors=errors,candidates=candidates,windows=windows,candidate_window_seconds=duration,source_duration_seconds=session['duration_seconds'],semantic_verified=False,verified_rules=[],models_executed=0,status='CANDIDATE_REVIEW_PLAN_NOT_MEANING_VERIFICATION' if rows else 'EXISTING_TRANSCRIPT_NOT_RETRIEVED_NO_REEXTRACTION_STARTED',selection_limitations=['Prior study and text cues nominate windows; they do not prove teacher roles or image meaning.','No candidate does not mean no visual dependence.','Expand a window until the example and preceding/following explanation are resolved.','Ambiguous audio/negation must remain unresolved without sufficient evidence.'])
pathlib.Path('review_plan').mkdir(exist_ok=True)
pathlib.Path('review_plan/targeted_review_PRIVATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
summary={k:result[k] for k in ['sequence','transcript_segments','candidate_window_seconds','source_duration_seconds','models_executed','status']}
summary.update(candidate_count=len(candidates),window_count=len(windows),semantic_verified=False,artifact_error_count=len(errors))
pathlib.Path('review_plan/summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary))
