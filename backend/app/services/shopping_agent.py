"""
Budget-constrained routine builder. Given a real budget and (optionally) a
real skin profile, greedily selects the highest-matching real product per
routine step that still fits the remaining budget. Every price and product
is real — nothing here is estimated or invented.
"""

import re
from sqlalchemy.orm import Session

from app.db.models import Product
from app.services.recommendation import build_recommendations

STEP_PRIORITY = ["cleanse", "tone", "treat", "moisturize", "protect"]


def extract_budget(message: str) -> float | None:
    """Pulls a rupee amount out of free text: '₹2000', '2000 rupees',
    '2k budget', 'under 1500'. Returns None if nothing parseable is found —
    the caller should ask the user to clarify rather than guessing."""
    text = message.lower().replace(",", "")

    k_match = re.search(r"(\d+(?:\.\d+)?)\s*k\b", text)
    if k_match:
        return float(k_match.group(1)) * 1000

    num_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d{2,6})", text)
    if num_match:
        return float(num_match.group(1))

    return None


def build_budget_routine(db: Session, budget: float, profile=None) -> dict:
    if profile is not None:
        scored = build_recommendations(db, profile, limit_per_step=10)
        candidates_by_step: dict[str, list[dict]] = {}
        for item in scored:
            step = item["product"].routine_step
            candidates_by_step.setdefault(step, []).append(item)
    else:
        # No scan context: fall back to all active products, grouped by step,
        # with no concern-based ranking (just cheapest-first per step).
        candidates_by_step = {}
        for p in db.query(Product).filter(Product.active == True).all():  # noqa: E712
            candidates_by_step.setdefault(p.routine_step, []).append({"product": p, "score": 0})

    remaining = budget
    picks = []

    for step in STEP_PRIORITY:
        options = candidates_by_step.get(step, [])
        affordable = [o for o in options if o["product"].price is not None and o["product"].price <= remaining]
        if not affordable:
            continue
        affordable.sort(key=lambda o: (-o["score"], o["product"].price))
        best = affordable[0]
        picks.append({"step": step, "product": best["product"]})
        remaining -= best["product"].price

    total = sum(p["product"].price for p in picks)

    return {
        "picks": picks,
        "total": round(total, 2),
        "budget": budget,
        "fits_budget": total <= budget,
        "matches_profile": profile is not None,
    }