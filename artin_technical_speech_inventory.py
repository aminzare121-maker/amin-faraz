#!/usr/bin/env python3
"""Lossless technical-topic triage of *machine* ASR for Artin's 25 sessions.

This is a review index, not speaker identification, semantic fidelity,
trading-rule approval or an MT5 bot. No rows are discarded.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import re
import zipfile
from pathlib import Path

TOPICS = {
    "entry_exit_conditions": (
        "ورود", "خروج", "سیگنال", "بای", "سل", "شورت", "لانگ", "نقطه ورود", "نقطه خروج", "پوزیشن",
        "معامله", "استاپ", "تارگت", "تریگر", "تریگر ورود", "خرید", "فروش", "سفارش"),
    "price_action_chart": (
        "کندل", "کَندِل", "چارت", "نمودار", "حمایت", "مقاومت", "روند", "ترند", "خط روند",
        "پولبک", "پول بک", "بریک", "شکست", "پیوت", "سویینگ", "لو", "های", "کف", "سقف",
        "لیکوئیدیتی", "نقدینگی", "لیکوئید", "زون", "باکس", "پرایس اکشن", "پیرسینگ", "فیک", "اصلاح",
        "سطح", "ریجکت", "تایم فریم", "تایمفریم", "تایم‌فریم", "قیمت", "بسته شدن", "کلوز"),
    "risk_management": (
        "ریسک", "حد ضرر", "حد سود", "ریوارد", "استاپ لاس", "استاپلاس", "استاپ لاسو", "حدسود",
        "سر به سر", "سربه سر", "ریسک فری", "ریسکفری", "برداشت سود", "مدیریت سرمایه", "حجم",
        "دراوداون", "ضرر", "سود", "پرافیت", "تیک پرافیت", "نسبت ریسک", "بریک ایون", "ریوار", "لات"),
    "indicator_methods": (
        "اندیکاتور", "مووینگ", "میانگین متحرک", "RSI", "MACD", "ایچیموکو", "استوکاستیک", "فیبوناچی", "واگرایی", "دایورجنس",
        "بولینگر", "ADX", "او بی", "اوردر بلاک", "فیر ولیو", "FVG", "ATR"),
    "market_infrastructure": (
        "بروکر", "متاتریدر", "صرافی", "اسپرد", "کمیسیون", "اهرم", "لوریج", "فارکس", "جفت ارز", "مارجین", "حساب دمو", "حساب واقعی", "لیکویید پرووایدر", "اردر", "کپی ترید", "پلتفرم", "اسلیپیج", "کارگزاری"),
    "learning_psychology": (
        "روانشناسی", "روان‌شناسی", "تمرین", "پلن", "ژورنال", "اشتباه", "ترس", "طمع", "صبوری", "انضباط", "پشت سرهم")
}
HYPOTHETICAL = ("فرض کنید", "فرض کن", "مثلا", "مثلاً", "اگه", "اگر", "حالا فرض", "تصور کنید", "ممکنه", "می تونه", "میتونه")
CONDITION = ("اگر", "اگه", "وقتی", "زمانی که", "تا وقتی", "به شرط", "در صورتی", "در صورت", "چنانچه")
NEGATION = ("نکن", "نخریم", "نفروش", "نمی", "نباید", "اجازه ندار", "ممنوع", "نه اینکه", "غلط", "اشتباه")
SHA = re.compile(r"^[0-9a-f]{64}$")


def norm(v):
    v = str(v or "")
    return re.sub(r"\s+", " ", v.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")).strip()


def topic_terms(text):
    t = norm(text).casefold()
    return {topic: [term for term in terms if norm(term).casefold() in t]
            for topic, terms in TOPICS.items() if any(norm(term).casefold() in t for term in terms)}


def scan_records(path):
    rows=[]
    for i,line in enumerate(path.read_text(encoding="utf8").splitlines()):
        if not line.strip():
            continue
        data=json.loads(line)
        if data.get('row') != len(rows):
            raise ValueError(f'Out-of-order row {path.name}: {data.get("row")}')
        if not SHA.fullmatch(data.get('source_audio_sha256') or ''):
            raise ValueError(f'Invalid audio SHA at {path.name} row {i}')
        if not (isinstance(data.get('start_seconds'),(int,float)) and
                isinstance(data.get('end_seconds'),(int,float)) and
                0<=data['start_seconds']<=data['end_seconds']):
            raise ValueError(f'Invalid timing at {path.name} row {i}')
        rows.append(data)
    return rows


def process(root, output_zip, summary_path):
    files={}; stats=[]; total=0; directly_marked=0; contextual_marked=0; unmarked=0; hypoth_count=0
    counts=Counter(); seen=set()
    for session in range(1,26):
        p=Path(root)/f'session_{session:02d}_all_machine_speech_review.jsonl'
        rows=scan_records(p)
        if not rows:
            raise ValueError(f'Empty session {session}')
        marked=[topic_terms(row.get('machine_text_unverified')) for row in rows]
        records=[];stats_topics=Counter()
        for i,row in enumerate(rows):
            if row.get('session')!=session or row.get('record_id') in seen:
                raise ValueError(f'Duplicate/mismatched session or record {session}:{i}')
            seen.add(row['record_id'])
            t=norm(row.get('machine_text_unverified'))
            direct=marked[i]
            relevant=[]
            # Nearby speech is context, NOT independent confirmation that current words teach this topic.
            for j in range(max(0,i-4),min(len(rows),i+5)):
                if j==i:continue
                other=rows[j]
                if min(abs(other['start_seconds']-row['end_seconds']),abs(other['end_seconds']-row['start_seconds']))<=18 and marked[j]:
                    relevant.append(j)
            class_name='DIRECT_TOPIC_CANDIDATE' if direct else ('CONTEXT_REVIEW_CANDIDATE' if relevant else 'UNCLASSIFIED_RETAINED')
            if direct: directly_marked+=1
            elif relevant:contextual_marked+=1
            else:unmarked+=1
            hyp=any(norm(w).casefold() in t.casefold() for w in HYPOTHETICAL)
            if hyp:hypoth_count+=1
            for k in direct:counts[k]+=1;stats_topics[k]+=1
            rec={
                'record_id':row['record_id'],'session':session,'row':i,
                'start_seconds':row['start_seconds'],'end_seconds':row['end_seconds'],
                'raw_machine_text_unverified':row.get('machine_text_unverified'),
                'source_audio_sha256':row['source_audio_sha256'],
                'source_video_sha256_if_available':row.get('source_video_sha256_if_available'),
                'source_segment_id':row.get('source_segment_id'),
                'nearby_visual_refs_machine_only':row.get('visual_source_nearby',[]),
                'classification':class_name,
                'direct_topic_matches_unverified':direct,
                'context_neighbor_record_ids':[rows[j]['record_id'] for j in relevant[:8]],
                'teaching_hypothesis_marker':hyp,
                'negation_marker':any(norm(w).casefold() in t.casefold() for w in NEGATION),
                'conditional_marker':any(norm(w).casefold() in t.casefold() for w in CONDITION),
                'teacher_speech_independently_verified':False,
                'teacher_method_semantically_verified':False,
                'motor_decision_approved':False,
                'trade_permitted':False,
            }
            records.append(json.dumps(rec,ensure_ascii=False,separators=(',',':')))
        contents=('\n'.join(records)+'\n').encode('utf8')
        name=f'technical_review_session_{session:02d}.jsonl'
        files[name]=contents
        stats.append({'session':session,'speech_rows':len(rows),
                      'direct_topic_candidate_rows':sum(bool(x) for x in marked),
                      'other_rows_preserved':sum(not bool(x) for x in marked),
                      'detected_direct_topics':dict(stats_topics),'bytes_sha256':hashlib.sha256(contents).hexdigest()})
        total+=len(rows)
    if total!=10235 or len(seen)!=total:
        raise ValueError(f'Unexpected row count {total}; recheck source baseline and do not silently change threshold')
    summary={
        'schema':'artin_25_session_full_speech_technical_triage_v1',
        'total_machine_speech_rows_preserved':total,'sessions':25,
        'direct_topic_candidate_rows':directly_marked,
        'context_only_candidate_rows':contextual_marked,
        'unclassified_rows_preserved':unmarked,
        'rows_with_hypothetical_language':hypoth_count,
        'topic_counts_nonexclusive':dict(counts),
        'session_summaries':stats,
        'semantic_review_status':'NOT_VERIFIED',
        'teacher_rules_verified':0,'mt5_enabled':False,
        'notes':'Every original machine-ASR row preserved, including greetings, student speech and uncertainties. Classification is lexicon based; no verified speaker, technique completeness or teaching meaning is inferred. A hypothetical teacher scenario is meaningful instructional content, not proof of an executed historical trade.',
        'original_files_unchanged':True
    }
    files['MANIFEST.json']=(json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    with zipfile.ZipFile(output_zip,'w',zipfile.ZIP_DEFLATED) as z:
        for name,b in files.items():z.writestr(name,b)
    summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output-zip',type=Path,required=True)
    p.add_argument('--summary',type=Path,required=True)
    a=p.parse_args()
    report=process(a.root,a.output_zip,a.summary)
    print(json.dumps({k:report[k] for k in ['sessions','total_machine_speech_rows_preserved','direct_topic_candidate_rows','context_only_candidate_rows','unclassified_rows_preserved','teacher_rules_verified','mt5_enabled']},ensure_ascii=False))
if __name__=='__main__':main()