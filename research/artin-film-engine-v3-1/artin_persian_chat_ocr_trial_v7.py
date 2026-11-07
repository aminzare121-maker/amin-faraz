#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional printed Persian chat OCR via independent PaddleOCR, not VLM.

Only text candidates, never teacher attribution, chart semantics or trading rules.
This small pilot crop is pinned to an original video frame SHA256. Automated
correctness is NOT claimed merely because OCR text exists.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time


def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def trial(source_image:Path,output:Path,expected_hash:str,roi=(.04,.80,.94,.92),
          ocr_factory=None):
    from PIL import Image
    source_image=Path(source_image)
    if not source_image.is_file() or sha(source_image)!=expected_hash:
        raise ValueError("Cannot use unverified or changed source screenshot")
    if not isinstance(roi,(list,tuple)) or len(roi)!=4 or not (
        0<=roi[0]<roi[2]<=1 and 0<=roi[1]<roi[3]<=1):
        raise ValueError("Invalid source screenshot bounds")
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    with Image.open(source_image) as im:
        width,height=im.size
        img=im.convert("RGB")
        clip=img.crop((int(roi[0]*width),int(roi[1]*height),
                       int(roi[2]*width),int(roi[3]*height)))
        if clip.width<100 or clip.height<40:
            raise ValueError("Source has insufficient printed text resolution")
        crop=output/"private_source_question_crop.png"
        clip.save(crop)
    start=time.monotonic()
    if ocr_factory is None:
        from paddleocr import PaddleOCR
        ocr_factory=PaddleOCR
    model=ocr_factory(lang="fa",use_doc_orientation_classify=False,
                       use_doc_unwarping=False,use_textline_orientation=False)
    result=model.predict(str(crop))
    elapsed=time.monotonic()-start
    if not isinstance(result,list) or not result:
        raise ValueError("No OCR result was produced")
    first=result[0]
    text=list(first.get("rec_texts",[]))
    scores=list(first.get("rec_scores",[]))
    if len(text)!=len(scores):
        raise ValueError("OCR text and confidence counts diverge")
    items=[]
    for raw,score in zip(text,scores):
        if not isinstance(raw,str):
            raise ValueError("OCR result line is not text")
        try: score=float(score)
        except (TypeError,ValueError):
            raise ValueError("OCR confidence is not numeric")
        items.append({"ocr_candidate":raw,"ocr_model_confidence":round(float(score),4),
                      "original_text_verified":False})
    private={"schema":"artin_source_persian_chat_ocr_v7",
        "source_video_sha256":"b23c618eb63af8c91c77d9a451411091bf7f5a57edbc0b6fdc20e01b86bcc8ff",
        "source_frame_sha256":expected_hash,
        "crop_sha256":sha(crop),
        "crop_normalized_bounds":roi,
        "model":"PaddleOCR fa (unverified text)",
        "image_text_human_verified":False,
        "student_question_human_verified":False,
        "teacher_answer_human_verified":False,
        "rules_executable":0,
        "lines":items}
    (output/"ocr_PRIVATE_unverified.json").write_text(
        json.dumps(private,ensure_ascii=False,indent=2),encoding="utf8")
    safe={"schema":"artin_ocr_safe_summary_v7",
        "source_frame_sha256":expected_hash,
        "roi":roi,"text_lines_candidate":len(items),
        "runtime_seconds":round(elapsed,2),
        "mean_recognition_confidence":round(sum(float(x["ocr_model_confidence"])
              for x in items)/len(items),4) if items else None,
        "independent_persian_ground_truth_checked":False,
        "character_error_rate":None,
        "teacher_question_answer_verified":False,
        "rules_executable":0,"status":"OCR_UNVERIFIED"}
    (output/"ocr_summary_safe.json").write_text(
        json.dumps(safe,ensure_ascii=False,indent=2),encoding="utf8")
    print("ARTIN_PERSIAN_CHAT_OCR_TRIAL="+json.dumps(safe,ensure_ascii=False),flush=True)
    return safe


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--image",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--expected-sha256",required=True)
    a=p.parse_args()
    trial(a.image,a.out,a.expected_sha256)


if __name__=="__main__":main()
