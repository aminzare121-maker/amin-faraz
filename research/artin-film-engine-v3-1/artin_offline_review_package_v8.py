#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build an offline, mobile-friendly human evidence review artifact.

Inputs: existing PRIVATE source-hashed teacher ASR, 35 fidelity packets, 59
provisional chat questions and original screenshot index. No private text
or video is put in Git commits. This creates a local index.html and bundled
original source crops, with a strict no-trading release policy.
"""
from __future__ import annotations
import argparse
import html
import json
import re
import shutil
from pathlib import Path

SOURCE="b23c618eb63af8c91c77d9a451411091bf7f5a57edbc0b6fdc20e01b86bcc8ff"

def require(predicate,message):
    if not predicate:raise ValueError(message)

def build(qa_file,claims_file,audio_file,visual_index_file,visual_root,out):
    qa=json.loads(Path(qa_file).read_text(encoding="utf8"))
    claims=json.loads(Path(claims_file).read_text(encoding="utf8"))
    audio=json.loads(Path(audio_file).read_text(encoding="utf8"))
    visuals=json.loads(Path(visual_index_file).read_text(encoding="utf8"))
    for name,x in (("qa",qa),("claims",claims),("audio",audio),("visuals",visuals)):
        require(x.get("source_video_sha256")==SOURCE,name+" source video mismatch")
    require(qa.get("schema")=="artin_private_typed_chat_audio_candidates_v8","Wrong QA schema")
    require(claims.get("schema")=="artin_private_teacher_review_packet_v7","Wrong claims schema")
    require(audio.get("schema")=="artin_teacher_av_review_v5","Wrong ASR schema")
    require(visuals.get("schema")=="artin_classroom_visual_v6","Wrong image index")
    frames={x["frame_id"]:x for x in visuals.get("rows",[])}
    speech={x["id"]:x for x in audio.get("speech_lines",[])}
    require(speech and frames,"Empty source evidence")
    require(audio.get("parts_with_asr")==audio.get("parts_total")==17,"Not all 17 audio parts available")
    rows=[];needed={}
    for i,p in enumerate(qa.get("question_groups",[]),1):
        require(isinstance(p.get("frame_sources"),list) and p["frame_sources"],"QA has no original frame")
        refs=[]
        for fr in p["frame_sources"]:
            x=frames.get(fr.get("frame_id"))
            require(x is not None and fr.get("chat_frame_sha256")==x["chat"]["sha256"],
                    "QA frame source SHA mismatch")
            needed[x["chat"]["path"]]=x["chat"]["sha256"]
            refs.append({"frame_id":fr["frame_id"],
                         "time":fr["observed_at_seconds"],
                         "image":"evidence/"+x["chat"]["path"]})
        speech_context=[]
        for a in p.get("provisional_nearby_speech",[])[:10]:
            u=speech.get(a["speech_line_id"])
            if u:
                speech_context.append({"time":u["start"],"text":u["text"],
                    "line_id":u["id"],"speaker_verified":False})
        rows.append({"id":"Q-%03d"%i,"kind":"question",
                     "time":p["first_seen"],"headline":p.get("candidate_text",""),
                     "description":"پرسش احتمالی نوشته‌شده در چت؛ پاسخ مدرس تأیید نشده",
                     "source_images":refs,"speech":speech_context,
                     "warnings":["نویسنده و زمان ارسال پرسش قطعی نیست",
                                 "گفتار نزدیک الزاماً پاسخ این پرسش نیست"],
                     "verified":False,"can_trade":False})
    for i,p in enumerate(claims.get("candidate_review_packets",[]),1):
        require(p.get("video_sha256")==SOURCE and p.get("audio_sha256"),
                "Rule packet missing original source hashes")
        refs=[]
        for fr in p.get("source_video_frames",[]):
            x=frames.get(fr.get("id"))
            if x is None:raise ValueError("Rule screenshot ID not in original timeline")
            for ch in ("board","chat"):
                expected=fr.get(ch+"_sha256")
                require(expected==x[ch]["sha256"],"Rule screenshot SHA mismatch")
                needed[x[ch]["path"]]=x[ch]["sha256"]
                refs.append({"frame_id":fr["id"],"time":fr["t"],
                             "image":"evidence/"+x[ch]["path"],"channel":ch})
        snippets=[{"time":x["t"],"text":x["text"],"line_id":x["id"]}
                   for x in p.get("nearby_unverified_asr",[])]
        rows.append({"id":"R-%03d"%i,"kind":"rule",
                     "time":p["start"],"headline":p["unverified_asr_quote"],
                     "description":"جملهٔ مشکوک به قانون؛ شرایط کامل معاملاتی هنوز اثبات نشده",
                     "source_images":refs,"speech":snippets,
                     "warnings":p.get("completeness_risks",[]),
                     "verified":False,"can_trade":False})
    require(len(rows)==len(qa.get("question_groups",[]))+
                      len(claims.get("candidate_review_packets",[])),
            "Unexpected missing review packet")
    dest=Path(out).resolve()
    dest.mkdir(parents=True,exist_ok=True)
    base=Path(visual_root).resolve()
    for filename,expected in needed.items():
        import hashlib
        input_path=(base/filename).resolve()
        require(input_path.is_relative_to(base) and input_path.is_file(),"Original image missing")
        data=input_path.read_bytes()
        require(hashlib.sha256(data).hexdigest()==expected,
                "Original image failed SHA verification: "+filename)
        target=(dest/"evidence"/filename).resolve()
        require(target.is_relative_to(dest),"Unsafe output screenshot path")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
    # Embed JSON only as escaped literal; all untrusted class text rendered as
    # textContent. Never evaluate OCR/ASR text as DOM or JS code.
    payload=json.dumps({"source_video_sha256":SOURCE,
       "class_duration_seconds":audio["duration_seconds"],
       "qa_count":len(qa.get("question_groups",[])),
       "rule_count":len(claims.get("candidate_review_packets",[])),
       "rows":rows},ensure_ascii=False,separators=(",",":")).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    view=WEB_UI.replace("DATA_GOES_HERE",payload)
    (dest/"index.html").write_text(view,encoding="utf8")
    (dest/"README_FA.txt").write_text(
      "آرتین — بستهٔ بازبینی فیلم اصلی\n"
      "فایل index.html را در مرورگر باز کنید. برای پخش زمان‌دار، نسخهٔ اصلی J2_6-11-1404.mp4 را با دکمهٔ انتخاب فایل از روی گوشی یا رایانه انتخاب کنید.\n"
      "تمام اطلاعات و عکس‌های داخل بسته محلی هستند؛ بدون سرویس خارجی کار می‌کند. متن‌های گفتار و تصویر نامطمئن‌اند؛ با ویدئو چک شوند.\n"
      "بررسی‌ها را با «خروجی بازبینی» به JSON تبدیل کنید؛ ذخیرهٔ مرورگر در حالت خصوصی ممکن است پایدار نباشد.\n"
      "هیچ نتیجه‌ای، حتی در حالت تأیید کاربر، دستور معامله نیست. موتور MT5 و ربات اصلی تغییر نمی‌کنند.\n",
      encoding="utf8")
    summary={"schema":"artin_offline_source_review_package_v1",
       "source_video_sha256":SOURCE,"question_groups":len(qa["question_groups"]),
       "unverified_rule_fragments":len(claims["candidate_review_packets"]),
       "source_images_copied":len(needed),"verified_teacher_answers":0,
       "executable_teacher_rules":0,"standalone_html":True,
       "real_media_bundled":False,
       "status":"USABLE_OFFLINE_REVIEW_NOT_CERTIFIED_AUTOMATED_TRADING"}
    (dest/"summary_safe.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
    print("ARTIN_OFFLINE_REVIEW_PACKAGE="+json.dumps(summary,ensure_ascii=False),flush=True)
    return summary

WEB_UI=r"""<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>بازبین شواهد فیلم — مخزن ابزارها</title>
<style>
:root{color-scheme:dark;font-family:system-ui,Tahoma,sans-serif;background:#101820;color:#ecf2f6}
*{box-sizing:border-box}body{margin:0}header{padding:16px;background:#172431;border-bottom:1px solid #4e6170;position:sticky;top:0;z-index:2}
h1{margin:0 0 8px;font-size:22px}p{line-height:1.7;margin:6px 0}
.notice{color:#ffcf89}.muted{color:#a9b9c7}main{max-width:1250px;margin:auto;padding:12px}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}
input,select,textarea,button{font:inherit;border:1px solid #5a6e80;border-radius:8px;background:#20303e;color:white;padding:10px}
input[type=search]{min-width:210px;flex:1}button{cursor:pointer}button:hover{background:#365065}
video{display:block;width:100%;max-height:320px;background:black;margin:10px 0;border-radius:8px}
.layout{display:grid;grid-template-columns:260px 1fr;gap:14px}
aside{max-height:70vh;overflow:auto;background:#192734;border-radius:10px;padding:8px}
aside button{width:100%;text-align:right;margin:3px 0;font-size:13px;overflow-wrap:anywhere}
aside button.active{border:2px solid #8cc9ea;background:#284457}
article{background:#192734;padding:14px;border-radius:10px;min-height:250px}
.group{border-bottom:1px solid #394b5b;padding:12px 0}
.imgs{display:flex;gap:12px;overflow-x:auto;padding:8px 0}
.figure{min-width:240px;max-width:400px;flex-shrink:0}
.figure img{width:100%;height:220px;object-fit:contain;background:#09111a;border-radius:7px}
.figlabel{font-size:12px;color:#adbeca}
.speech{max-height:360px;overflow:auto;background:#0e1923;padding:8px;border-radius:8px}
.speech p{padding:6px;border-bottom:1px solid #263948;font-size:14px}
pre{white-space:pre-wrap;overflow-wrap:anywhere}
label{display:block;margin:8px 0}.status{color:#ffcc82}
footer{padding:18px;color:#9daeb9}
@media(max-width:720px){.layout{grid-template-columns:1fr}aside{max-height:180px}.figure{min-width:190px}}
</style></head>
<body>
<header><h1>ابزار آرتین — بازبینی شواهد واقعی مدرس</h1>
<p class="notice">۳۵ جملهٔ نامزد قانون و پرسش‌های چت هنوز تأیید نشده‌اند. هیچ نتیجه‌ای اجازهٔ معامله نمی‌دهد.</p>
<p id="stats" class="muted"></p></header>
<main>
<section><label>برای بررسی دقیق زمان و صوت، فایل اصلی ویدئو را فقط روی همین دستگاه انتخاب کن:
<input type="file" id="videoFile" accept="video/mp4,video/*"></label>
<video id="film" controls preload="metadata"></video>
<p class="muted">اگر ویدئو را نداری: <a style="color:#9ed7fb" href="https://my.uupload.ir/p/aGgKYdpL" target="_blank" rel="noopener noreferrer">لینک اصلی فیلم مدرس</a> (ویدئو داخل این بسته کپی نشده است).</p></section>
<div class="controls"><input id="query" type="search" placeholder="جست‌وجو در گفتار و سؤال‌ها">
<select id="kind"><option value="all">همه</option><option value="question">پرسش‌های چت</option><option value="rule">جمله‌های مشکوک به قانون</option></select>
<select id="reviewFilter"><option value="all">همهٔ وضعیت‌ها</option><option value="unreviewed">بررسی‌نشده</option><option value="source_confirmed">منبع را بررسی کردم</option><option value="wrong">متن/نسبت اشتباه است</option><option value="unclear">نامشخص</option></select>
<button id="export">خروجی بازبینی JSON</button></div>
<div class="layout"><aside id="items" aria-label="پرونده‌های بررسی"></aside>
<article id="details"><p class="muted">یک پرونده را انتخاب کن.</p></article></div>
</main><footer>تمام متن و تصویر این بسته از اجرای خصوصی پردازش فیلم دریافت شده؛ OCR و ASR به‌تنهایی صحت آموزش را اثبات نمی‌کنند. بازبینی محلی است. هیچ خروجی خودکار وارد موتور معاملاتی نمی‌شود.</footer>
<script id="artin_data" type="application/json">DATA_GOES_HERE</script>
<script>
"use strict";
const DATA=JSON.parse(document.getElementById("artin_data").textContent);
const $=id=>document.getElementById(id);
const key="artin-review-"+DATA.source_video_sha256;
let notes={};try{notes=JSON.parse(localStorage.getItem(key)||"{}")}catch(_){}
const el=(name,text,cls)=>{const e=document.createElement(name);if(text!==undefined)e.textContent=String(text);if(cls)e.className=cls;return e};
let active=DATA.rows[0]?.id||"";
function fmt(t){t=Math.floor(Number(t)||0);return String(Math.floor(t/3600)).padStart(2,"0")+":"+String(Math.floor(t%3600/60)).padStart(2,"0")+":"+String(t%60).padStart(2,"0")}
function seek(t){const v=$("film");if(!v.src){alert("ابتدا فایل اصلی فیلم را انتخاب کن.");return}v.currentTime=Math.max(0,Number(t)-3);v.play().catch(()=>{})}
function save(){try{localStorage.setItem(key,JSON.stringify(notes))}catch(_){alert("ذخیرهٔ موقت مرورگر در دسترس نیست؛ از خروجی JSON استفاده کن.")}}
function pick(){const q=$("query").value.trim().toLowerCase(),kind=$("kind").value,status=$("reviewFilter").value;const list=DATA.rows.filter(r=>(kind==="all"||r.kind===kind)&&(status==="all"||(notes[r.id]?.status||"unreviewed")===status)&&(!q||(r.headline+" "+r.description+" "+r.speech.map(s=>s.text).join(" ")).toLowerCase().includes(q)));$("items").replaceChildren(...list.map(r=>{const b=el("button",r.id+" · "+fmt(r.time)+" · "+r.headline.slice(0,85));if(r.id===active)b.className="active";b.onclick=()=>{active=r.id;render();pick()};return b}));$("stats").textContent="پرسش‌های احتمالی: "+DATA.qa_count+" | عبارت‌های مشکوک به قانون: "+DATA.rule_count+" | قابل اجرای معاملاتی: صفر | فهرست فعلی: "+list.length}
function render(){const r=DATA.rows.find(x=>x.id===active);const root=$("details");root.replaceChildren();if(!r)return;
root.append(el("h2",r.id+" — "+fmt(r.time)));
root.append(el("p",r.description,"status"));
root.append(el("h3","متن استخراج‌شده (تأییدنشده)"));
root.append(el("pre",r.headline));
const jump=el("button","پخش فیلم از چند ثانیه قبل");jump.onclick=()=>seek(r.time);root.append(jump);
if(r.warnings?.length){root.append(el("h3","مواردی که هنوز اثبات نشده‌اند"));const ul=el("ul");for(const warning of r.warnings)ul.append(el("li",warning));root.append(ul)}
root.append(el("h3","تصویر اصلی زمان‌دار"));const gallery=el("div",undefined,"imgs");
for(const image of r.source_images.slice(0,18)){const fig=el("div",undefined,"figure");const img=el("img");img.src=image.image;img.alt="تصویر چت یا تختهٔ کلاس";img.loading="lazy";const b=el("button","دیدن زمان "+fmt(image.time));b.onclick=()=>seek(image.time);fig.append(img,el("div",(image.channel||"چت")+" · "+fmt(image.time),"figlabel"),b);gallery.append(fig)}
root.append(gallery);
root.append(el("h3","گفتار اطراف (رونوشت خام، بدون تأیید نقش گوینده)"));const sg=el("div",undefined,"speech");for(const line of r.speech.slice(0,60)){const p=el("p",fmt(line.time)+" | "+line.text);p.onclick=()=>seek(line.time);p.style.cursor="pointer";sg.append(p)}root.append(sg);
root.append(el("h3","نتیجهٔ بررسی من — ثبت محلی، بدون صدور دستور معامله"));
const saved=notes[r.id]||{};
const select=el("select");for(const [value,label] of [["unreviewed","بررسی‌نشده"],["unclear","نامشخص / نیاز به بررسی بیشتر"],["wrong","متن یا نسبت اشتباه است"],["source_confirmed","منبع را خودم تطبیق داده‌ام"]]){const o=el("option",label);o.value=value;select.append(o)}select.value=saved.status||"unreviewed";
const note=el("textarea");note.rows=4;note.placeholder="متن صحیح، اصلاح مدرس، شرط دقیق یا ایراد این مورد را بنویس";note.style.width="100%";note.value=saved.note||"";
const saveButton=el("button","ثبت این بررسی");saveButton.onclick=()=>{notes[r.id]={status:select.value,note:note.value,updated_at:new Date().toISOString(),human_source_checked:select.value==="source_confirmed",releases_trading:false};save();pick();alert("بازبینی فقط در همین مرورگر ثبت شد. برای نگهداری فایل خروجی JSON بگیر.")};
root.append(select,note,saveButton,el("p","حتی تأیید شخصی اینجا، موتور آرتین یا MT5 را تغییر نمی‌دهد.","muted"));
}
for(const id of ["query","kind","reviewFilter"])$(id).addEventListener("input",pick);
$("videoFile").onchange=e=>{const f=e.target.files?.[0];if(f){const v=$("film");if(v.src?.startsWith("blob:"))URL.revokeObjectURL(v.src);v.src=URL.createObjectURL(f)}};
$("export").onclick=()=>{const output={schema:"artin_manual_source_review_v1",source_video_sha256:DATA.source_video_sha256,original_qa_count:DATA.qa_count,original_rule_count:DATA.rule_count,reviewed:notes,all_reviews_untrusted_until_independent_validation:true,can_trade:false,exported_at:new Date().toISOString()};const blob=new Blob([JSON.stringify(output,null,2)],{type:"application/json"});const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="artin_private_manual_review.json";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),10000)};
pick();render();
</script></body></html>
""";

def main():
    parser=argparse.ArgumentParser()
    for name in ("qa","claims","audio","visual_index","visual_root","out"):
        parser.add_argument("--"+name.replace("_","-"),required=True,type=Path)
    a=parser.parse_args()
    build(a.qa,a.claims,a.audio,a.visual_index,a.visual_root,a.out)
if __name__=="__main__":
    main()
