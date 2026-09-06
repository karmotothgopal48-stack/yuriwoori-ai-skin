"""
Builds an ordered AM/PM routine from real, matched products (Step 12's
recommendation engine). Sunscreen only ever appears in AM. Each step's
`reason` combines the product's genuine concern-match with a general,
textbook skincare-ordering rationale (why this step goes here in a
routine) — never an invented ingredient-efficacy claim.
"""

from sqlalchemy.orm import Session
from app.db.models import Product
from app.services.recommendation import build_recommendations

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


def build_routine(db: Session, profile) -> dict:
    scored = build_recommendations(db, profile, limit_per_step=5)  # wider pool to pick best-per-step from

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