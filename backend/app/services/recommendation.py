"""
Matches a real Skin Profile against the real, imported catalogue.
Every recommendation's match_reason is built from that product's own
real concern_tags/category — never a generated or guessed claim.
"""

from sqlalchemy.orm import Session
from app.db.models import Product

# Skin-profile attribute -> (threshold, concern tag it should match, human phrase)
CONCERN_RULES = [
    ("redness", 40, "redness", "calm visible redness"),
    ("pigmentation", 40, "brightening", "even out uneven tone"),
    ("pigmentation", 40, "uneven-tone", "even out uneven tone"),
    ("blemish_index", 40, "blemish", "target blemish-prone areas"),
    ("pore_visibility", 40, "pore-visibility", "refine visible pores"),
    ("oiliness", 55, "oiliness", "balance excess oil"),
]

ROUTINE_ORDER = ["cleanse", "tone", "treat", "moisturize", "protect", "mask"]


def build_recommendations(db: Session, profile, limit_per_step: int = 2) -> list[dict]:
    active_concerns = []
    for attr, threshold, tag, phrase in CONCERN_RULES:
        value = getattr(profile, attr, None)
        if value is not None and value > threshold:
            active_concerns.append((tag, phrase))

    if (profile.hydration or 100) < 45:
        active_concerns.append(("hydration", "boost hydration"))

    concern_tags = {tag for tag, _ in active_concerns}
    phrase_by_tag = dict(active_concerns)

    products = db.query(Product).filter(Product.active == True).all()  # noqa: E712

    scored = []
    for p in products:
        product_tags = set(p.concern_tags or [])
        overlap = product_tags & concern_tags
        score = len(overlap) * 10

        if score == 0:
            continue  # only recommend products that genuinely match a real concern

        reasons = [phrase_by_tag[tag] for tag in overlap if tag in phrase_by_tag]
        match_reason = f"Matches your scan: helps {', '.join(reasons)}."

        scored.append({"product": p, "score": score, "match_reason": match_reason})

    scored.sort(key=lambda x: x["score"], reverse=True)

    # Cap per routine step so results span a routine, not five toners
    step_counts: dict[str, int] = {}
    final = []
    for item in scored:
        step = item["product"].routine_step or "unassigned"
        step_counts[step] = step_counts.get(step, 0) + 1
        if step_counts[step] <= limit_per_step:
            final.append(item)

    return final