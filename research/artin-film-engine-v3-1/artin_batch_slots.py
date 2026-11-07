"""Stable 18-slot batches on a single continuous original-video timeline.

Global chunk numbers NEVER reset. Local slot numbers reset to 1..18 for each
new batch; a pair (batch, slot) is the unique visible slot identity.
"""
from __future__ import annotations

SLOTS_PER_BATCH = 18


def batch_slot(global_index: int) -> tuple[int, int]:
    if type(global_index) is not int or global_index < 1:
        raise ValueError("Global chunk number must be positive integer")
    return (global_index - 1) // SLOTS_PER_BATCH + 1, (global_index - 1) % SLOTS_PER_BATCH + 1


def artifact_path(folder: str, chunk: dict, extension: str = "json") -> str:
    """Keep first-batch paths backward compatible; prevent second-batch collisions."""
    batch, slot = batch_slot(chunk["chunk"])
    if batch == 1:
        return f"{folder}/part_{slot:02d}.{extension}"
    return f"{folder}/batch_{batch:03d}/part_{slot:02d}.{extension}"


def batch_frames_dir(chunk: dict) -> str:
    batch, slot = batch_slot(chunk["chunk"])
    return f"vision_frames/{'batch_%03d/' % batch if batch > 1 else ''}part_{slot:02d}"


def annotate_plan(plan: list[dict]) -> list[dict]:
    for expected, c in enumerate(plan, start=1):
        if c.get("chunk") != expected:
            raise ValueError("Source global chunk identity is missing/duplicated")
        batch, slot = batch_slot(expected)
        c["batch"] = batch
        c["slot"] = slot
        c["global_index"] = expected
        c["unique_id"] = f"b{batch:03d}_s{slot:02d}_g{expected:06d}"
        c["clip"] = artifact_path("clips", c, "mp4")
        c["transcript"] = artifact_path("transcripts", c)
        c["analysis"] = artifact_path("analyses", c)
    return plan


def batch_summary(chunks: list[dict]) -> list[dict]:
    if not chunks:
        raise ValueError("Cannot group empty video")
    batches=[]
    for i, c in enumerate(chunks, start=1):
        if c["chunk"] != i:
            raise ValueError("Chunks must be chronologically ordered before batch export")
        batch, slot = batch_slot(i)
        if c.get("batch") != batch or c.get("slot") != slot or c.get("global_index") != i:
            raise ValueError("Batch or slot does not match global timeline")
        if slot == 1:
            batches.append({"batch":batch,"slots_in_order":[],"global_indices":[],"unique_ids":[],
                            "core_start":c["core_start"],"core_end":c["core_end"]})
        g=batches[-1]
        g["slots_in_order"].append(slot)
        g["global_indices"].append(i)
        g["unique_ids"].append(c["unique_id"])
        g["core_end"]=c["core_end"]
    return batches
