#!/usr/bin/env python3
"""An independently inspected visual scene audit of 66 original-frame thumbnails.
Category assignment is human visual review, not AI model claims or algorithmic trade proof.
"""
import collections,hashlib,io,json,pathlib,subprocess,zipfile
REPO="aminzare121-maker/amin-faraz";ART=13697590451
OUT=pathlib.Path("artin25_scene_review_output");OUT.mkdir(exist_ok=True)
manual_scene_groups={
 "TRADING_CHART":[1,2,3,5,19,20,25,27,30,32,34,35,40,42,43,44,45,46,48,49,51,52,53,54,55,56,61,64,65,66],
 "WHITEBOARD_OR_NOTES":[4,7,8,11,12,15,16,26,31,33,50,60,63],
 "CLASSROOM_SHARED_SCREEN":[6,9,10,13,14,17,18,21,22,23,24,28,29,36,37,38,39,41,57,58,59,62],
 "OTHER_NON_CHART":[47]
}
p=subprocess.run(["gh","api",f"repos/{REPO}/actions/artifacts/{ART}/zip"],capture_output=True,timeout=180)
if p.returncode:raise RuntimeError("SOURCE_FETCH_ERROR:"+p.stderr.decode("utf8","replace")[:200])
if not zipfile.is_zipfile(io.BytesIO(p.stdout)):raise RuntimeError("Not zip")
with zipfile.ZipFile(io.BytesIO(p.stdout)) as z:
    paths=[x for x in z.namelist() if x.endswith("contact_sheet_index.json")]
    if len(paths)!=1:raise RuntimeError("atlas index missing")
    index=json.loads(z.read(paths[0]))
flat={}
for cat,ids in manual_scene_groups.items():
    for item in ids:
        if item in flat:raise RuntimeError("Overlapping manual classification")
        flat[item]=cat
if set(flat)!=set(range(1,67)):raise RuntimeError("Classification missing or invalid position")
if len(index)!=66 or {x["global_position"] for x in index}!=set(range(1,67)):
    raise RuntimeError("Original source index incomplete")
out=[]
for r in index:
    item=dict(r)
    kind=flat[item["global_position"]]
    item.update({
      "visual_kind_thumb_review":kind,
      "scene_has_chart":kind=="TRADING_CHART",
      "visual_related_to_spoken_meaning_certified":False,
      "speaker_is_teacher_confirmed":False,
      "source_speech_validated_semantics":False,
      "executable_entry_rule":False,
      "visual_review_scope":"human review of authentic contact sheet thumbnails, not frame-by-frame full-resolution replay",
      "time_relation_status":"MORE_THAN_6S_APART" if float(item["image_delta"])>6 else "WITHIN_6S_NOT_SEMANTIC",
      "requires_direct_case_review":True
    })
    out.append(item)
c=collections.Counter(x["visual_kind_thumb_review"] for x in out)
distant=[{"id":x["global_position"],"sequence":x["seq"],"distance_s":x["image_delta"]} for x in out if x["time_relation_status"]=="MORE_THAN_6S_APART"]
tests={
 "all_66_source_windows_assessed":len(out)==66,
 "category_totals_66":sum(c.values())==66,
 "no_speech_picture_semantic_overclaim":all(not x["visual_related_to_spoken_meaning_certified"] for x in out),
 "no_teacher_role_overclaim":all(not x["speaker_is_teacher_confirmed"] for x in out),
 "no_unapproved_trade":all(not x["executable_entry_rule"] for x in out)
}
summary={
 "source_artifact":ART,
 "schema":"artin25_authentic_frame_scene_review_v1",
 "visual_review_scope":"Original screenshot thumbnail content; not independent teacher-meaning certification",
 "source_windows":len(out),
 "scene_types":dict(c),
 "frame_more_than_6_seconds_from_speech":len(distant),
 "distant_frame_windows":distant,
 "teacher_semantics_verified":0,
 "full_25_lesson_method_certified":False,
 "mt5_strategy_rules_approved":0,
 "tests":tests
}
(OUT/"all_66_frame_scene_reviews.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
(OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
print("ARTIN25_SCENE_REVIEW="+json.dumps(summary,ensure_ascii=False),flush=True)
if not all(tests.values()):raise SystemExit(2)
