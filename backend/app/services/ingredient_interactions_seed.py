"""
Sourced ingredient interaction seed data. Each entry cites the real,
documented reasoning — not an assumption. Interactions only get created
for ingredients that actually exist in your imported catalogue; the rest
sit ready for when new actives (e.g. retinoids, AHA/BHA) get added.
"""

SEED_INTERACTIONS = [
    {
        "a": "Ascorbic Acid",
        "b": "Niacinamide",
        "relationship_type": "synergistic",
        "explanation": (
            "Long believed incompatible, but this is a debunked myth from 1960s studies that used "
            "unstabilized ingredients under extreme heat. In modern formulations at normal skin "
            "temperature, the two are safe and effective together. Very high-strength (10%+) pure "
            "L-ascorbic acid users who prefer extra caution can apply vitamin C first, wait a few "
            "minutes, then apply niacinamide — a precaution, not a requirement.",
        ),
    },
    {
        "a": "Retinol",
        "b": "Glycolic Acid",
        "relationship_type": "caution",
        "explanation": (
            "Both increase skin cell turnover and can compound irritation, dryness, and sun "
            "sensitivity when used together, especially for new users. Commonly alternated "
            "(different nights) rather than layered same-session."
        ),
    },
    {
        "a": "Retinol",
        "b": "Salicylic Acid",
        "relationship_type": "caution",
        "explanation": (
            "Similar to retinol + AHA: combined use can over-exfoliate and compromise the skin "
            "barrier. Often recommended on alternating nights instead of together."
        ),
    },
    {
        "a": "Retinol",
        "b": "Benzoyl Peroxide",
        "relationship_type": "avoid_same_routine",
        "explanation": (
            "Benzoyl peroxide can oxidize and destabilize retinol when applied in the same routine, "
            "reducing the retinol's effectiveness. Typically recommended at different times of day."
        ),
    },
    {
        "a": "Ascorbic Acid",
        "b": "Retinol",
        "relationship_type": "caution",
        "explanation": (
            "Vitamin C performs best at low pH and retinol at closer-to-neutral pH, so layering them "
            "back-to-back can reduce both ingredients' effectiveness. Most commonly resolved by using "
            "vitamin C in the AM routine and retinol at PM."
        ),
    },
]