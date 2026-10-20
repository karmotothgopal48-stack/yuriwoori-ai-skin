"""
Matches a real Skin Profile against the live YuriWoori catalogue (app/services/live_catalogue.py).
Every recommendation's match_reason is built from that product's own concern tags (derived from the
brand's product copy) — never a generated or guessed claim.
"""

# Skin-profile attribute -> (threshold, concern tag it should match, human phrase)
CONCERN_RULES = [
    ("redness", 40, "redness", "calm visible redness"),
    ("pigmentation", 40, "brightening", "even out uneven tone"),
    ("pigmentation", 40, "uneven-tone", "even out uneven tone"),
    ("blemish_index", 40, "blemish", "target blemish-prone areas"),
    ("pore_visibility", 40, "pore-visibility", "refine visible pores"),
    ("oiliness", 55, "oiliness", "balance excess oil"),
]
# Hydration is the one "higher is better" metric with a level: below it, "boost hydration" applies.
HYDRATION_MIN = 45

ROUTINE_ORDER = ["cleanse", "tone", "treat", "moisturize", "protect", "mask"]

# A hand scan is matched against hand care only (the brand's own "handcream" Shopify tag),
# never against facial products. Face scans are matched against the whole catalogue, as before.
HAND_CATEGORY = "handcream"

METRIC_FIELDS = ("hydration", "oiliness", "texture", "redness", "pigmentation", "blemish_index", "pore_visibility")


def concern_details(metrics: dict) -> dict[str, tuple[str, float]]:
    """Skin metrics -> {concern tag: (human phrase, severity 0-1)} for every concern above its
    threshold. Severity is how far past the threshold the metric is, so a worse scan ranks higher."""
    found: dict[str, tuple[str, float]] = {}
    for attr, threshold, tag, phrase in CONCERN_RULES:
        value = metrics.get(attr)
        if value is not None and value > threshold:
            found[tag] = (phrase, (value - threshold) / (100 - threshold))

    hydration = metrics.get("hydration")
    if hydration is not None and hydration < HYDRATION_MIN:  # 0.0 is a real (very low) value
        found["hydration"] = ("boost hydration", (HYDRATION_MIN - hydration) / HYDRATION_MIN)
    return found


def active_concerns(metrics: dict) -> dict[str, str]:
    """{concern tag: human phrase} for every concern the analysis flagged."""
    return {tag: phrase for tag, (phrase, _) in concern_details(metrics).items()}


def profile_metrics(profile) -> dict:
    return {f: getattr(profile, f, None) for f in METRIC_FIELDS}


def is_selectable(product) -> bool:
    """A single product the user can buy right now: not a kit/combo, priced, in stock, with a cart variant."""
    return (product.routine_step != "bundle" and bool(product.price) and product.available
            and product.variant_id is not None)


def recommend(metrics: dict, products, limit_per_step: int = 2, body_part: str = "face") -> tuple[dict[str, str], list[dict]]:
    """Returns (active concerns, ranked recommendations) from `products` (the live catalogue).
    A product is only recommended if its own concern tags overlap a real concern from the scan
    and it can be bought now. A hand scan is matched against hand care only (HAND_CATEGORY)."""
    details = concern_details(metrics)
    concerns = {tag: phrase for tag, (phrase, _) in details.items()}
    if not concerns:
        return concerns, []

    scored = []
    for p in products:
        if not is_selectable(p):
            continue
        if body_part == "hand" and p.category != HAND_CATEGORY:
            continue
        overlap = sorted(set(p.concern_tags) & concerns.keys())
        if not overlap:
            continue
        reasons = [concerns[t] for t in overlap]
        scored.append({
            "product": p,
            # each matched concern is worth 10, plus up to 10 more the worse that concern is in the scan
            "score": round(sum(10 + 10 * details[t][1] for t in overlap)),
            "matched_concerns": overlap,
            # brightening and uneven-tone share one phrase, so list each phrase once
            "match_reason": f"Matches your scan: helps {', '.join(dict.fromkeys(reasons))}.",
        })

    scored.sort(key=lambda x: (-x["score"], x["product"].name))

    # Cap per routine step so results span a routine, not five toners
    per_step: dict[str, int] = {}
    final = []
    for item in scored:
        step = item["product"].routine_step or "unassigned"
        per_step[step] = per_step.get(step, 0) + 1
        if per_step[step] <= limit_per_step:
            final.append(item)
    return concerns, final


def build_recommendations(profile, products, limit_per_step: int = 2, body_part: str = "face") -> list[dict]:
    """Ranked live products for a saved skin profile (same rules as recommend())."""
    return recommend(profile_metrics(profile), products, limit_per_step, body_part)[1]
