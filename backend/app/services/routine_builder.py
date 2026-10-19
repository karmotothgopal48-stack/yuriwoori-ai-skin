"""
Builds an ordered AM/PM routine from matched products of the live YuriWoori catalogue
(app/services/live_catalogue.py, via the recommendation engine). Sunscreen only ever appears in AM. Each step's
`reason` combines the product's genuine concern-match with a general,
textbook skincare-ordering rationale (why this step goes here in a
routine) — never an invented ingredient-efficacy claim.
"""

from app.services.recommendation import HAND_CATEGORY, build_recommendations, is_selectable

AM_STEP_ORDER = ["cleanse", "tone", "treat", "moisturize", "protect"]
PM_STEP_ORDER = ["cleanse", "tone", "treat", "moisturize"]  # no "protect" at night

STEP_PURPOSE = {
    "cleanse": "Clears the skin so later steps can absorb properly.",
    "tone": "Preps and balances skin before treatment products.",
    "treat": "The active step — where your main concerns get addressed.",
    "moisturize": "Locks in hydration and supports the skin barrier.",
    "protect": "Shields skin from UV exposure, preventing new damage.",
    "mask": "An occasional treatment layer for extra care.",
}


def _pick_best_per_step(scored_products: list[dict], steps: list[str]) -> list[dict]:
    chosen = []
    for step in steps:
        candidates = [item for item in scored_products if item["product"].routine_step == step]
        if candidates:
            best = max(candidates, key=lambda x: x["score"])
            chosen.append({"step": step, **best})
    return chosen


def build_routine(profile, products, body_part: str = "face") -> dict:
    """`products`: the live catalogue's products."""
    # wider pool to pick best-per-step from; a hand scan's pool is hand care only (a moisturize step)
    scored = build_recommendations(profile, products, limit_per_step=5, body_part=body_part)

    am_picks = _pick_best_per_step(scored, AM_STEP_ORDER)
    pm_picks = _pick_best_per_step(scored, PM_STEP_ORDER)

    def format_steps(picks):
        result = []
        for order, pick in enumerate(picks, start=1):
            purpose = STEP_PURPOSE.get(pick["step"], "")
            reason = f"{purpose} {pick['match_reason']}"
            result.append(
                {
                    "step_order": order,
                    "step": pick["step"],
                    "product": pick["product"],
                    "reason": reason,
                }
            )
        return result

    return {"AM": format_steps(am_picks), "PM": format_steps(pm_picks)}


# ---- Maintenance routine: only for a scan whose analysis found no concern ("balanced") ----
# Nothing is targeted, so each step uses the catalogue product most tagged for general care - the
# hydration / barrier-repair / soothing tags derived from the brand's own benefit copy
# (services/catalogue_rules.py). Ties go to the more general product (fewer concern-targeting tags), then by
# name. No treat step: it is the "active step" for concerns, and a balanced scan has none. Protect (morning
# only) needs a product tagged for sun protection. Concern detection and its thresholds are not involved.
MAINTENANCE_TAGS = ("hydration", "barrier-repair", "soothing")
MAINTENANCE_AM = ["cleanse", "tone", "moisturize", "protect"]
MAINTENANCE_PM = ["cleanse", "tone", "moisturize"]
_CARE_WORDS = {"hydration": "hydration", "barrier-repair": "barrier support", "soothing": "soothing"}


def _maintenance_pick(products: list, step: str):
    candidates = []
    for p in products:
        tags = set(p.concern_tags or [])
        care = [t for t in MAINTENANCE_TAGS if t in tags]
        if p.routine_step != step or not is_selectable(p):
            continue
        if step == "protect" and "sun-protection" not in tags:
            continue
        if step != "protect" and not care:
            continue
        candidates.append(((-len(care), len(tags) - len(care), p.name), p, care))
    if not candidates:
        return None
    _, product, care = min(candidates, key=lambda c: c[0])
    return product, care


def build_maintenance_routine(products, body_part: str = "face") -> dict:
    """`products`: the live catalogue's products."""
    products = [p for p in products if (p.category == HAND_CATEGORY) == (body_part == "hand")]

    def steps(order: list[str]) -> list[dict]:
        result = []
        for step in order:
            picked = _maintenance_pick(products, step)
            if not picked:
                continue
            product, care = picked
            words = [_CARE_WORDS[t] for t in care] or ["sun protection"]
            words = words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"
            result.append({
                "step_order": len(result) + 1,
                "step": step,
                "product": product,
                "reason": f"{STEP_PURPOSE.get(step, '')} For maintenance: tagged in the YuriWoori catalogue for {words}.",
            })
        return result

    return {"AM": steps(MAINTENANCE_AM), "PM": steps(MAINTENANCE_PM)}
