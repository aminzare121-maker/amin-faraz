"""Exploratory paired temporal uncertainty; never independent future confirmation."""
import math
import random
from statistics import mean


def probability_metrics(probabilities, labels):
    if not labels:
        return {"n": 0, "brier": None, "log_loss": None, "reliability": []}
    p = [max(1e-8, min(1-1e-8, v)) for v in probabilities]
    groups = []
    for j in range(5):
        ids = [i for i, v in enumerate(p) if min(4, int(v*5)) == j]
        groups.append({"bin": j, "n": len(ids),
                       "mean_probability": mean(p[i] for i in ids) if ids else None,
                       "positive_fraction": mean(labels[i] for i in ids) if ids else None})
    return {"n": len(labels), "brier": mean((v-y)**2 for v, y in zip(p, labels)),
            "log_loss": -mean(y*math.log(v)+(1-y)*math.log(1-v) for v, y in zip(p, labels)),
            "reliability": groups}


def paired_bootstrap(model_daily, baseline_daily, days, block=5, reps=1000, seed=1729):
    differences = [model_daily.get(d, 0.0)-baseline_daily.get(d, 0.0) for d in days]
    if not differences:
        return {"status": "insufficient_days"}
    rng = random.Random(seed)
    n = len(differences)
    samples = []
    for _ in range(reps):
        draw = []
        while len(draw) < n:
            start = rng.randrange(n)
            draw.extend(differences[(start+j) % n] for j in range(block))
        samples.append(sum(draw[:n])/n)
    samples.sort()
    lo, hi = samples[int(.025*reps)], samples[min(reps-1, int(.975*reps))]
    return {"status": "exploratory_previously_seen_development",
            "daily_delta_mean": mean(differences), "total_net_delta": sum(differences),
            "mean_daily_delta_ci95": [lo, hi], "total_delta_ci95": [lo*n, hi*n],
            "calendar_days": n, "block_days": block, "approx_nonoverlap_blocks": n/block,
            "resamples": reps, "seed": seed, "independent_future_test": False,
            "minimum_effect_power_plan_locked": False,
            "warning": "Unverified feed/cost/session and prior exposure prevent confirmatory inference"}
