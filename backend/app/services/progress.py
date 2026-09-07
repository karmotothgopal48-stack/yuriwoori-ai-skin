"""
Compares progress_snapshots over time. A change is only reported as real
progress if it exceeds NOISE_THRESHOLD — otherwise it's treated as normal
scan-to-scan variance (lighting, angle, heuristic-model noise) and hidden,
matching the product's own "beyond normal variance" disclaimer.
"""

NOISE_THRESHOLD = 6.0  # points on the 0-100 scale

METRICS = ["hydration", "oiliness", "texture", "redness", "pigmentation", "blemish_index"]


def build_progress_series(snapshots: list) -> dict:
    if not snapshots:
        return {"snapshots": [], "meaningful_changes": []}

    ordered = sorted(snapshots, key=lambda s: s.day_offset)
    first, latest = ordered[0], ordered[-1]

    meaningful_changes = []
    for metric in METRICS:
        start_val = getattr(first, metric)
        end_val = getattr(latest, metric)
        if start_val is None or end_val is None:
            continue
        delta = end_val - start_val
        if abs(delta) >= NOISE_THRESHOLD:
            meaningful_changes.append(
                {
                    "metric": metric,
                    "start": start_val,
                    "latest": end_val,
                    "delta": round(delta, 1),
                    "direction": "improved" if _is_improvement(metric, delta) else "worsened",
                }
            )

    return {
        "snapshots": [
            {
                "day_offset": s.day_offset,
                "hydration": s.hydration,
                "oiliness": s.oiliness,
                "texture": s.texture,
                "redness": s.redness,
                "pigmentation": s.pigmentation,
                "blemish_index": s.blemish_index,
            }
            for s in ordered
        ],
        "meaningful_changes": meaningful_changes,
    }


def _is_improvement(metric: str, delta: float) -> bool:
    # For hydration/texture, higher is better. For the rest, lower is better.
    higher_is_better = metric in ("hydration", "texture")
    return delta > 0 if higher_is_better else delta < 0