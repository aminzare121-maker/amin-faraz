#!/usr/bin/env python3
"""Source-linked chart viewport registration for the nine unresolved Artin comparisons.

Quantifies alignment of on-screen chart features under pan/shift; never infers
teacher speech, speaker identity, candle formation, trade state or permission.
No broker, trading platform, network or model calls.
"""
from __future__ import annotations
import argparse, hashlib, io, json, math, zipfile
from pathlib import Path

SOURCE_CLIPS = {19: 's19_b96434bd99_4276-4331.mp4', 21: 's21_d3ea03e2be_1896-1944.mp4'}
SOURCE_PAIRS = {2,3,5,7,9,10,12,13,14}
# Original clip is 960x640. Bounds deliberately exclude browser chrome, toolbar, and watchlist.
ROIS = {19: (100,190,730,510), 21: (100,190,770,525)}

def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def register_chart_pair(frame_a, frame_b, roi, *, min_inliers=30):
    import cv2, numpy as np
    if frame_a is None or frame_b is None or frame_a.shape != frame_b.shape or len(frame_a.shape)!=3:
        raise ValueError('invalid or mismatched frames')
    h,w=frame_a.shape[:2]
    x1,y1,x2,y2=roi
    if not (0<=x1<x2<=w and 0<=y1<y2<=h and (x2-x1)>=120 and (y2-y1)>=120):
        raise ValueError('invalid chart ROI')
    a=frame_a[y1:y2,x1:x2];b=frame_b[y1:y2,x1:x2]
    gray_a=cv2.cvtColor(a,cv2.COLOR_BGR2GRAY)
    gray_b=cv2.cvtColor(b,cv2.COLOR_BGR2GRAY)
    orb=cv2.ORB_create(nfeatures=2600,scaleFactor=1.15,edgeThreshold=12,fastThreshold=10)
    kp1,d1=orb.detectAndCompute(gray_a,None)
    kp2,d2=orb.detectAndCompute(gray_b,None)
    def pending(reason,good=0,inliers=0):
        return {'status':'INCONCLUSIVE_UNDERLYING_CHART_MATCH','reason':reason,
                'ratio_test_matches':int(good),'ransac_inliers':int(inliers),
                'teacher_semantics_verified':False,'same_trade_state_verified':False,
                'orders_authorized':0},None
    if d1 is None or d2 is None or len(kp1)<20 or len(kp2)<20:
        return pending('insufficient chart detail')
    pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1,d2,k=2)
    good=[m for m,n in pairs if m.distance < .72*n.distance]
    if len(good)<min_inliers:return pending('insufficient distinctive matching features',len(good))
    src=np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1,1,2)
    dst=np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1,1,2)
    cv2.setRNGSeed(0)
    M,inliers=cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=3.3,
                                            maxIters=10000,confidence=.995)
    if M is None or inliers is None:return pending('ransac affine not determined',len(good))
    valid=inliers.ravel().astype(bool)
    count=int(valid.sum());ratio=count/len(good)
    transformed=cv2.transform(src,M).reshape(-1,2)
    err=np.linalg.norm(transformed-dst.reshape(-1,2),axis=1)
    med=float(np.median(err[valid])) if count else float('inf')
    scale=float(np.hypot(M[0,0],M[0,1]))
    dx,dy=float(M[0,2]),float(M[1,2])
    angle=float(math.degrees(math.atan2(M[1,0],M[0,0])))
    if (count<min_inliers or ratio<.50 or not .95<=scale<=1.05 or med>2.0 or
        abs(angle)>2 or abs(dx)>200 or abs(dy)>200):
        return pending('feature matching model below quality threshold',len(good),count)
    # Compare the same coordinates before and after correcting measured viewport motion.
    # This is screen image similarity only, and may include changes to drawing handles.
    warped=cv2.warpAffine(b,M,(x2-x1,y2-y1),flags=cv2.INTER_LINEAR|cv2.WARP_INVERSE_MAP,
                          borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))
    overlap=cv2.warpAffine(np.ones(gray_b.shape,dtype=np.uint8),M,(x2-x1,y2-y1),
                           flags=cv2.INTER_NEAREST|cv2.WARP_INVERSE_MAP,borderValue=0).astype(bool)
    delta_raw=np.max(cv2.absdiff(a,b),axis=2)>30
    delta_reg=np.max(cv2.absdiff(a,warped),axis=2)>30
    if np.count_nonzero(overlap)<.40*overlap.size:return pending('too little overlap after viewport shift',len(good),count)
    result={'status':'CHART_FEATURES_ALIGNED_VIEWPORT_ONLY','ratio_test_matches':len(good),
            'ransac_inliers':count,'inlier_ratio':round(ratio,4),
            'translate_x_pixels':round(dx,2),'translate_y_pixels':round(dy,2),
            'scale':round(scale,5),'angle_degrees':round(angle,3),
            'median_inlier_reprojection_pixels':round(med,3),
            'changed_pixels_raw_fraction':round(float(delta_raw[overlap].mean()),4),
            'changed_pixels_after_alignment_fraction':round(float(delta_reg[overlap].mean()),4),
            'interpretation':'Shared chart features have the reported geometric relation; drawing overlays and teacher conditions are NOT certified.',
            'teacher_semantics_verified':False,'same_trade_state_verified':False,'orders_authorized':0}
    return result, (warped,overlap)


def extract_midpoint_frame(path:Path, interval:list, source_start:float):
    import cv2
    cap=cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():raise ValueError('cannot open source video')
        tm=(interval[0]+interval[1])/2
        rel=tm-source_start
        if rel<0:raise ValueError('negative video offset')
        if not cap.set(cv2.CAP_PROP_POS_MSEC,rel*1000):raise ValueError('seek failed')
        ok,frame=cap.read()
        if not ok:raise ValueError('cannot decode source midpoint')
        frame_ms=float(cap.get(cv2.CAP_PROP_POS_MSEC))
        if not math.isfinite(frame_ms) or abs(frame_ms/1000-rel)>1.5:
            raise ValueError('decoded timestamp drift')
        return frame, tm, float(source_start+frame_ms/1000)
    finally:cap.release()


def run(private_manifest:Path, source_dir:Path, output_json:Path, private_zip:Path, public_json:Path):
    import cv2, numpy as np
    d=json.loads(private_manifest.read_text(encoding='utf-8'))
    if (len(d.get('source_groups',[]))!=2 or len(d.get('pairs',[]))!=9 or
        {x.get('pair') for x in d['pairs']}!=SOURCE_PAIRS or
        d.get('teacher_semantics_verified') is not False or d.get('mt5_orders_authorized')!=0):
        raise ValueError('source manifest identity/semantic gate failed')
    groups={x['session']:x for x in d['source_groups']}
    if set(groups)!={19,21}:raise ValueError('source groups differ')
    ids={};media={};frames={};assets={};coords={}
    for session,g in groups.items():
        f=source_dir/SOURCE_CLIPS[session]
        content=f.read_bytes()
        if sha256(content)!=g['video_excerpt_sha256']:
            raise ValueError('source MP4 SHA-256 not equal manifest')
        media[session]=content
        for u in g['machine_speech']:
            i=u['segment_id']
            if i in ids:raise ValueError('reused ASR id')
            interval=[u['start_seconds'],u['end_seconds']]
            if not g['clip_seconds'][0]<=interval[0]<interval[1]<=g['clip_seconds'][1]:
                raise ValueError('ASR source time outside original video')
            frame,mid,actual=extract_midpoint_frame(f,interval,g['clip_seconds'][0])
            frames[i]=frame;ids[i]=session;coords[i]=(mid,actual)
    reports=[]
    for p in sorted(d['pairs'],key=lambda x:x['pair']):
        session=p['session'];u,v=p['utterance_ids']
        if ids.get(u)!=session or ids.get(v)!=session or u==v:raise ValueError('pair source swapped')
        res,comparison=register_chart_pair(frames[u],frames[v],ROIS[session])
        case={'pair':p['pair'],'session':session,'chart':groups[session]['chart'],
              'first_original_second_midpoint':round(coords[u][0],3),'second_original_second_midpoint':round(coords[v][0],3),
              'first_decoded_second':round(coords[u][1],3),'second_decoded_second':round(coords[v][1],3),
              'machine_asr_ids':[u,v],**res}
        reports.append(case)
        # Contact images are derived from genuine frame samples. Remain private.
        a,b=frames[u],frames[v]
        a2=a.copy();b2=b.copy()
        x1,y1,x2,y2=ROIS[session]
        cv2.rectangle(a2,(x1,y1),(x2,y2),(10,100,255),2)
        cv2.rectangle(b2,(x1,y1),(x2,y2),(10,100,255),2)
        title=f'S{session} pair {p["pair"]} / first & second ASR sample / NO TRADE'
        composition=np.concatenate((a2,b2),axis=1)
        cv2.putText(composition,title,(25,42),cv2.FONT_HERSHEY_SIMPLEX,.7,(5,5,5),3,cv2.LINE_AA)
        cv2.putText(composition,title,(25,42),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),1,cv2.LINE_AA)
        ok,enc=cv2.imencode('.jpg',composition,[cv2.IMWRITE_JPEG_QUALITY,85])
        if not ok:raise ValueError('derived image encoding failed')
        assets[f'panels/pair_{p["pair"]:02d}_S{session}.jpg']=enc.tobytes()
    priv={'schema':'artin_source_video_chart_anchor_registration_v1','review_scope':'9 unresolved lexical candidate pairs only',
          'source_video_mp4_SHA256_verified':True,'source_video_sha256':{str(k):sha256(v) for k,v in media.items()},
          'pairs':reports,'independent_Persian_audio_listening':False,'speaker_verified':False,
          'teacher_meaning_certified':False,'same_trade_situation_certified':False,
          'XAUUSD_transfer_from_EURUSD_authorized':False,'orders_authorized':0}
    public={k:v for k,v in priv.items() if k!='pairs'}
    public['pairs']=[{k:v for k,v in case.items() if k!='machine_asr_ids'} for case in reports]
    public['private_media_report_path']='/بهروز/ARTIN_9_CHART_VIEWPORT_REGISTRATION_PRIVATE_20261110.json'
    public['private_review_zip_path']='/بهروز/ARTIN_9_CHART_VIEWPORT_REGISTRATION_PRIVATE_20261110.zip'
    output_json.write_text(json.dumps(priv,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    public_json.write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with zipfile.ZipFile(private_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('analysis_private.json',json.dumps(priv,ensure_ascii=False,indent=2)+'\n')
        for name,data in assets.items():z.writestr(name,data)
        html=['<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>تطبیق موقعیت نمای نمودار — آرتین</title>',
              '<style>body{font:16px Tahoma,Arial;margin:25px auto;max-width:1300px}article{padding:16px;border-bottom:1px solid #aaa}img{width:100%}small{color:#953030}</style>',
              '<h1>تطبیق ویژگی‌های بصری ۹ جفت — فقط بررسی جابه‌جایی نمای نمودار</h1>',
              '<p><strong>هیچ‌یک از این آزمون‌ها صحت گفتار مدرس، شرایط بازار یا اجازه معامله را تأیید نمی‌کند.</strong></p>']
        for case in reports:
            t=case['status'];dx=case.get('translate_x_pixels');dy=case.get('translate_y_pixels')
            html.append(f'<article><h2>جفت {case["pair"]}، جلسه {case["session"]} — {case["chart"]}</h2><p>وضعیت: {t}، جابه‌جایی تخمینی روی تصویر: ({dx}, {dy}) پیکسل، تعداد نقاط منطبق: {case.get("ransac_inliers",0)}</p><img src="panels/pair_{case["pair"]:02d}_S{case["session"]}.jpg"><p><small>فقط هندسه نمودار؛ معانی تصمیم معاملاتی تأیید نشده‌اند.</small></p></article>')
        html.append('</html>');z.writestr('index.html',''.join(html).encode('utf-8'))
    with zipfile.ZipFile(private_zip) as z:
        if z.testzip() is not None:raise ValueError('output ZIP invalid')
        for name,b in assets.items():
            if sha256(z.read(name))!=sha256(b):raise ValueError('image changed')
    return public


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',default='/mnt/data/ARTIN_9_TWO_EPISODE_EVIDENCE_PRIVATE_20261110.json')
    ap.add_argument('--sources',default='/mnt/data')
    ap.add_argument('--output-dir',default='/mnt/data')
    a=ap.parse_args()
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    r=run(Path(a.manifest),Path(a.sources),out/'ARTIN_9_CHART_VIEWPORT_REGISTRATION_PRIVATE_20261110.json',
          out/'ARTIN_9_CHART_VIEWPORT_REGISTRATION_PRIVATE_20261110.zip',
          out/'ARTIN_9_CHART_VIEWPORT_REGISTRATION_PUBLIC_20261110.json')
    print(json.dumps({'pairs':len(r['pairs']),'aligned':sum(x['status']=='CHART_FEATURES_ALIGNED_VIEWPORT_ONLY' for x in r['pairs']),
                      'teacher_verified':False,'orders':0}))
if __name__=='__main__':main()