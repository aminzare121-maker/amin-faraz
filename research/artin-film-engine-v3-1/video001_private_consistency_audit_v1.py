#!/usr/bin/env python3
"""Private ASR/OCR consistency audit; never prints or certifies lesson text.
Consistency with a previous UNVERIFIED run is not human-gold accuracy.
"""
from __future__ import annotations
import argparse
from collections import Counter
import difflib
import json
from pathlib import Path
import re

POLARITY = frozenset({
    "نه", "نخر", "نخرید", "نفروش", "نفروشید", "نکن", "نکنید",
    "نباید", "نیست", "نمی", "نمیخوام", "نمیخواهیم", "نمیفروشیم", "نمیخریم"
})

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def normalize(text):
    text = str(text).translate(str.maketrans({"ي":"ی", "ك":"ک", "ى":"ی"})).replace("\u200c", "")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text)).strip().split()

def collect_asr(root):
    files = sorted(Path(root).rglob("part_*_unverified.json"))
    if not files:
        raise ValueError("Missing original ASR source-linked records")
    out = {}
    for f in files:
        doc = read(f)
        index = doc.get("global_chunk")
        segments = doc.get("segments")
        if not isinstance(index, int) or index < 1 or index in out:
            raise ValueError("Duplicated or invalid audio chunk")
        if not isinstance(segments,list) or any(
            not isinstance(s,dict) or not isinstance(s.get("text"),str) for s in segments
        ):
            raise ValueError("Corrupt ASR evidence structure")
        out[index] = doc
    return out

def collect_ocr(root):
    files = sorted(Path(root).rglob("full_chat_ocr_candidates_PRIVATE.json"))
    if not files:
        raise ValueError("Missing original OCR evidence")
    rows = {}
    sha = None
    for f in files:
        doc = read(f)
        if sha is None:
            sha = doc.get("source_video_sha256")
        if sha != doc.get("source_video_sha256"):
            raise ValueError("OCR video SHA changed across partitions")
        for row in doc.get("results", []):
            frame = row.get("frame_id")
            if not frame or frame in rows:
                raise ValueError("Duplicated or invalid original OCR frame")
            rows[frame] = row
    return sha, rows

def compare(base_asr,candidate_asr,base_ocr,candidate_ocr,*,expected_asr_parts=17,expected_ocr_frames=276,min_similarity=.95):
    a,b = collect_asr(base_asr), collect_asr(candidate_asr)
    source_ok = sorted(a) == sorted(b) == list(range(1,expected_asr_parts+1))
    per_chunk = []
    words_a = words_b = 0
    polarity_diff = False
    for idx in sorted(set(a) & set(b)):
        x,y = a[idx],b[idx]
        for key in ("source_video_sha256","source_audio_sha256","model","timebase"):
            if x.get(key)!=y.get(key):
                source_ok=False
        wx=normalize(" ".join(s["text"] for s in x["segments"]))
        wy=normalize(" ".join(s["text"] for s in y["segments"]))
        words_a+=len(wx)
        words_b+=len(wy)
        change=Counter(w for w in wx if w in POLARITY)!=Counter(w for w in wy if w in POLARITY)
        polarity_diff |= change
        per_chunk.append({"chunk":idx,"baseline_segments":len(x["segments"]),"candidate_segments":len(y["segments"]),
          "baseline_words":len(wx),"candidate_words":len(wy),
          "word_sequence_similarity":round(difflib.SequenceMatcher(None,wx,wy,autojunk=False).ratio(),4),
          "polarity_count_changed":change})
    oa,ra=collect_ocr(base_ocr)
    ob,rb=collect_ocr(candidate_ocr)
    sa={p.get("source_video_sha256") for p in a.values()}
    sb={p.get("source_video_sha256") for p in b.values()}
    source_ok=(source_ok and len(sa)==len(sb)==1 and sa==sb=={oa}=={ob} and
               all(re.fullmatch(r"[0-9a-f]{64}",p.get("source_audio_sha256") or "")
                   for p in list(a.values())+list(b.values())))
    ocr_ok=(oa==ob and len(ra)==len(rb)==expected_ocr_frames and
            set(ra)==set(rb) and
            all(ra[k].get("source_frame_sha256")==rb[k].get("source_frame_sha256") for k in ra))
    changed_ocr_keys=[k for k in ra if k in rb and ra[k].get("text_lines")!=rb[k].get("text_lines")]
    text_same=ocr_ok and not changed_ocr_keys
    def ocr_words(row):
        lines=row.get("text_lines") or []
        return normalize(" ".join(
            (line.get("ocr_candidate","") if isinstance(line,dict) else str(line))
            for line in lines))
    ocr_polarity_drift=sum(
        Counter(w for w in ocr_words(ra[k]) if w in POLARITY)!=
        Counter(w for w in ocr_words(rb[k]) if w in POLARITY)
        for k in changed_ocr_keys)
    return {"schema":"video001_private_consistency_audit_v1",
      "expected_audio_parts":expected_asr_parts,"observed_audio_parts":len(per_chunk),
      "expected_ocr_frames":expected_ocr_frames,"observed_ocr_frames":len(ra),
      "source_integrity_agrees":bool(source_ok and ocr_ok),
      "ocr_text_identical":bool(text_same),
      "total_asr_words_baseline":words_a,"total_asr_words_candidate":words_b,
      "ocr_frames_with_text_changes":len(changed_ocr_keys),
      "ocr_frames_with_polarity_count_changes":ocr_polarity_drift,
      "all_asr_chunks_above_similarity_threshold":bool(per_chunk and all(
          x["word_sequence_similarity"]>=min_similarity for x in per_chunk)),
      "polarity_count_changed":polarity_diff,
      "needs_independent_human_gold_validation":True,"automatic_merge_allowed":False,
      "status":"REVIEW_REQUIRED" if source_ok and ocr_ok else "REJECT_SOURCE_MISMATCH",
      "per_chunk_metrics_private":per_chunk}

def main():
    p=argparse.ArgumentParser()
    for name in ("baseline_asr","candidate_asr","baseline_ocr","candidate_ocr"):
        p.add_argument("--"+name.replace("_","-"),required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=compare(args.baseline_asr,args.candidate_asr,args.baseline_ocr,args.candidate_ocr)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    safe={k:v for k,v in result.items() if k!="per_chunk_metrics_private"}
    print("VIDEO001_PRIVATE_CONSISTENCY_SUMMARY="+json.dumps(safe,ensure_ascii=False),flush=True)
    if not result["source_integrity_agrees"]:
        raise SystemExit("REJECT_SOURCE_MISMATCH")

if __name__=="__main__":
    main()
