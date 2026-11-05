"""Amin calendar: explainable evidence propagation; no fabricated probabilities.
This is an offline *hypothesis engine*, not a learned causal model.
Edges must be explicitly reviewed, dated, versioned and sourced.
"""
from collections import defaultdict

def update_hypotheses(prior, incoming, edges):
    """Return directional pressure, not price forecasts.
    incoming: list of {id, delta, confidence, verified}; delta standardized [-1,1]
    edges: list of {source, target, sign, weight, rationale, evidence_id}
    prior: dict target -> pre-existing pressure within [-1,1].
    No inferred edge is created automatically.
    """
    scores = dict(prior)
    reasons = defaultdict(list)
    for item in incoming:
        if item.get("verified") is not True:
            continue
        delta = float(item["delta"])
        confidence = float(item["confidence"])
        if not (-1 <= delta <= 1 and 0 <= confidence <= 1):
            raise ValueError("delta/confidence out of bounds")
        for edge in edges:
            if edge["source"] != item["id"]:
                continue
            if not edge.get("evidence_id") or not edge.get("rationale"):
                raise ValueError("undocumented relationship")
            sign, weight = int(edge["sign"]), float(edge["weight"])
            if sign not in (-1,1) or not (0 <= weight <= 1):
                raise ValueError("invalid relationship")
            amount = delta * confidence * sign * weight
            target = edge["target"]
            old = scores.get(target,0.0)
            scores[target] = max(-1.0,min(1.0,old+amount))
            reasons[target].append({"event":item["id"],"delta":round(amount,4),
                "from":round(old,4),"to":round(scores[target],4),
                "evidence_id":edge["evidence_id"],"rationale":edge["rationale"]})
    return {"pressure_by_target":scores, "trace":dict(reasons),
            "caveat":"Hypothetical signed propagation only; not causal proof, calibrated probability or trading signal."}
