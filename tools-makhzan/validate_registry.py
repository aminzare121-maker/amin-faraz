#!/usr/bin/env python3
"""Validate persisted tool index and guard against false semantic 'success' claims."""
from pathlib import Path
import json
import re


def validate_registry(registry,root):
    if registry.get("schema")!="makhzan_tools_registry_v1":
        raise ValueError("Unknown registry schema")
    if registry.get("hub_name_fa")!="مخزن ابزارها":
        raise ValueError("Incorrect Persian hub name")
    if registry.get("hub_ref")!="tools-makhzan-hub":
        raise ValueError("Registry must point to canonical tool hub branch")
    tools=registry.get("tools")
    if not isinstance(tools,list) or not tools:
        raise ValueError("No registered tools")
    seen=set()
    for item in tools:
        tid=item.get("id")
        if not isinstance(tid,str) or not re.fullmatch(r"[A-Z]+-[0-9]{3}",tid) or tid in seen:
            raise ValueError("Tool IDs must be unique and stable")
        seen.add(tid)
        for key in ("name_fa","status","state_path","continuation_path","next_action"):
            if not isinstance(item.get(key),str) or not item[key].strip():
                raise ValueError(f"Missing tool field {key}")
        for key in ("state_path","continuation_path"):
            file=(root/item[key]).resolve()
            if not file.is_relative_to(root.resolve()) or not file.is_file():
                raise ValueError("Missing or unsafe tool handoff file")
        code=item.get("code") or {}
        if code.get("ref") is None or code.get("path") is None:
            raise ValueError("Code ref must be explicit; default branch is unsafe")
        verified=item.get("last_verified") or {}
        if item.get("status")=="COMPLETE_RELIABLE" and verified.get("verified_teacher_rules",0)==0:
            raise ValueError("Cannot claim complete teacher fidelity with zero verified rules")
        known=item.get("known_sources") or []
        for source in known:
            if not re.fullmatch(r"[0-9a-f]{64}",str(source.get("sha256",""))):
                raise ValueError("Original media SHA256 is missing")
            if type(source.get("global_parts")) is not int or source["global_parts"]<1:
                raise ValueError("Original chunk count invalid")
        if not isinstance(item.get("outstanding"),list):
            raise ValueError("Remaining blockers must be listed")
    return len(tools)


def main():
    root=Path(__file__).resolve().parent.parent
    path=root/"tools-makhzan"/"REGISTRY.json"
    registry=json.loads(path.read_text(encoding="utf-8"))
    count=validate_registry(registry,root)
    for doc in ("tools-makhzan/INDEX_FA.md","tools-makhzan/CONTINUATION_FA.md",
                "tools-makhzan/VIDEO_ENGINE_STATE_FA.md"):
        text=(root/doc).read_text(encoding="utf-8")
        if "مخزن ابزارها" not in text and doc.endswith("INDEX_FA.md"):
            raise ValueError("Makhzan name missing in index")
    print(f"MAKHZAN_REGISTRY_VALIDATED: {count} registered tool(s), all handoff files present")


if __name__=="__main__":
    main()
