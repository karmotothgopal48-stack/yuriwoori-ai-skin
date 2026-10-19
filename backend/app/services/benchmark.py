"""
Typical / Benchmark values shown next to the user's result on the results screens.

These are INTERNAL YURIWOORI BENCHMARKS: fixed values chosen by YuriWoori for comparison only.
They are NOT derived from a validated population dataset and are NOT medical or population norms
(no such reference dataset exists in this project yet). They are also separate from the product
recommendation thresholds in recommendation.py, which only decide which products to recommend.

The same values are returned for every scan. Change them here only, and bump BENCHMARK_VERSION.
Keys are the analysis field names (pigmentation = "Uneven tone", blemish_index = "Blemishes").
"""

BENCHMARK_VERSION = "yuriwoori-internal-2026-10-05"

FACE_BENCHMARK: dict[str, float] = {
    "hydration": 75.0,
    "texture": 75.0,
    "oiliness": 30.0,
    "redness": 15.0,
    "pigmentation": 20.0,     # Uneven tone
    "pore_visibility": 20.0,
    "blemish_index": 10.0,    # Blemishes
}

# No hand benchmark is configured yet: a face benchmark is not meaningful for hand skin.
HAND_BENCHMARK: dict[str, float] = {}


def benchmark_for(body_part: str) -> dict[str, float]:
    """The fixed benchmark for a body part ("face" or "hand"); empty when none is configured."""
    return dict(HAND_BENCHMARK if body_part == "hand" else FACE_BENCHMARK)
