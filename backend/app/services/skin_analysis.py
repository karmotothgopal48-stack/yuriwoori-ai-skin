"""
Heuristic v0 skin analyzer.

Uses classical computer vision (HSV/LAB color-space statistics, edge-density
texture analysis, blob detection) to produce real, image-derived scores.
This is NOT a trained CNN/ViT model — it's an honest, working baseline that
gets replaced by a trained model later (see roadmap Phase 2) without changing
the API contract, database schema, or frontend.

All scores are 0-100. For redness/oiliness/pigmentation/blemish_index/
pore_visibility, higher = MORE of that trait (a "concern level"). For
hydration/texture, higher = better/healthier skin.
"""

import cv2
import numpy as np


def _load_bgr(path: str) -> np.ndarray:
    image = cv2.imread(path)
    if image is None:
        raise ValueError(f"Could not read image at {path}")
    return image


def _center_crop(image: np.ndarray, fraction: float = 0.6) -> np.ndarray:
    h, w = image.shape[:2]
    ch, cw = int(h * fraction), int(w * fraction)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    return image[y0 : y0 + ch, x0 : x0 + cw]


def _redness(bgr: np.ndarray) -> float:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    a_channel = lab[:, :, 1].astype(np.float32)  # 128 = neutral, >128 = red/magenta
    redness = np.clip((a_channel.mean() - 128) * 2.2, 0, 100)
    return round(float(redness), 1)


def _oiliness(bgr: np.ndarray) -> float:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v, s = hsv[:, :, 2].astype(np.float32), hsv[:, :, 1].astype(np.float32)
    shine_mask = (v > 200) & (s < 60)  # bright + low saturation = specular highlight
    shine_ratio = shine_mask.mean()
    return round(float(np.clip(shine_ratio * 400, 0, 100)), 1)


def _texture(gray: np.ndarray) -> float:
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    roughness = np.clip(variance / 8.0, 0, 100)
    return round(float(100 - roughness), 1)  # higher = smoother/healthier


def _pigmentation(bgr: np.ndarray) -> float:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0].astype(np.float32)
    unevenness = np.clip(l_channel.std() * 1.8, 0, 100)
    return round(float(unevenness), 1)


def _blemish_index(bgr: np.ndarray) -> float:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 60, 40])
    upper = np.array([12, 255, 200])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    spots = [c for c in contours if 8 < cv2.contourArea(c) < 400]
    density = len(spots) / (mask.size / 10000)
    return round(float(np.clip(density * 3, 0, 100)), 1)


def _pore_visibility(gray: np.ndarray) -> float:
    cropped = _center_crop(gray, 0.4)
    variance = cv2.Laplacian(cropped, cv2.CV_64F).var()
    return round(float(np.clip(variance / 6.0, 0, 100)), 1)


def _hydration_proxy(oiliness: float, texture: float) -> float:
    # Rough proxy only: true hydration needs specialized (e.g. corneometer-style)
    # sensing. Smooth texture + moderate (not zero, not excessive) shine reads
    # as better-hydrated skin under visible light.
    shine_penalty = abs(oiliness - 35) * 0.4
    return round(float(np.clip(texture - shine_penalty, 0, 100)), 1)


def _classify_skin_type(oiliness: float, hydration: float) -> str:
    if oiliness > 55 and hydration < 55:
        return "oily"
    if oiliness < 30 and hydration < 45:
        return "dry"
    if oiliness > 45 and hydration > 55:
        return "combination"
    return "normal"


def analyze_skin_profile(frame_paths: list[str]) -> dict:
    if not frame_paths:
        raise ValueError("No frames available to analyze")

    per_frame = []
    for path in frame_paths:
        bgr = _load_bgr(path)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        per_frame.append(
            {
                "redness": _redness(bgr),
                "oiliness": _oiliness(bgr),
                "texture": _texture(gray),
                "pigmentation": _pigmentation(bgr),
                "blemish_index": _blemish_index(bgr),
                "pore_visibility": _pore_visibility(gray),
            }
        )

    avg = {k: round(sum(f[k] for f in per_frame) / len(per_frame), 1) for k in per_frame[0]}
    hydration = _hydration_proxy(avg["oiliness"], avg["texture"])
    skin_type = _classify_skin_type(avg["oiliness"], hydration)

    concern_avg = (avg["redness"] + avg["pigmentation"] + avg["blemish_index"] + avg["pore_visibility"]) / 4
    overall_score = round(np.clip((hydration + avg["texture"] + (100 - concern_avg)) / 3, 0, 100), 1)

    return {
        "skin_type": skin_type,
        "hydration": hydration,
        "oiliness": avg["oiliness"],
        "texture": avg["texture"],
        "redness": avg["redness"],
        "pigmentation": avg["pigmentation"],
        "blemish_index": avg["blemish_index"],
        "pore_visibility": avg["pore_visibility"],
        "overall_score": overall_score,
    }