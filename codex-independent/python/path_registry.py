"""Structural 13-path slots; no invented teaching or executable trade rules."""
PATHS=tuple({"id":f"PATH{i:02d}","name":None,"status":"UNVERIFIED_UNMAPPED",
             "speech_evidence":[],"image_evidence":[],"semantic_verified":False,
             "execution_enabled":False} for i in range(1,14))

def evaluate_path(path_id, observation=None):
    if path_id not in {p['id'] for p in PATHS}:raise ValueError('UNKNOWN_PATH')
    return {"path_id":path_id,"decision":"NEEDS_EVIDENCE", "orders_enabled":False,
            "reason":"No independently verified teacher rule mapping is installed"}
