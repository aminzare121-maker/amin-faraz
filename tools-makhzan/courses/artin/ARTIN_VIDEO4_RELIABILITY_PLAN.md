# Video 4 reliability runbook (evidence-based)
1. Input: original GitHub run 42581509064 TEXT-ONLY artifact 13658290669; outer ZIP contains nested V13_BEHROOZ_TEXT_ONLY.zip.
2. Inspect 49 source JSON files (15 ASR shards and visual OCR partitions). Preserve original file SHA256 and full source reference.
3. Deterministic validation against original artifact: 1997 speech segments, 502 OCR frames, 1798 speech segments within 8 seconds of an OCR frame. Seven timing/segmentation flags need audio comparison. These are inspection priorities, NOT proven ASR errors.
4. Reject empty or malformed nested ZIP, insufficient speech or visual coverage, or missing timestamps. Do not mark teacher meaning verified without comparing actual original audio/video.
5. Next blocker: independent audio-based checking of flagged segments and extraction of teacher/student roles. This requires retrieving the original audio shards, re-transcribing selected intervals independently, and recording comparisons; do not assert a complete semantic repair until this is done.
6. No changes to trading engine or production trading permissions.
