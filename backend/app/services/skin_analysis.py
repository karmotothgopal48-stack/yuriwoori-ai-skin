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

import numpy as np

try:
    import cv2
except ImportError as _cv2_error:  # e.g. DLL blocked by an OS application-control policy
    cv2 = None
    _CV2_ERROR = _cv2_error
else:
    _CV2_ERROR = None


class AnalysisUnavailableError(RuntimeError):
    """Raised when the OpenCV runtime needed for skin analysis cannot be loaded."""


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


def _redness(bgr: np.ndarray, skin: np.ndarray) -> float:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    a_channel = lab[:, :, 1][skin].astype(np.float32)  # 128 = neutral, >128 = red/magenta
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


def _pigmentation(bgr: np.ndarray, skin: np.ndarray) -> float:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0][skin].astype(np.float32)
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


_CASCADES = None


def _cascades():
    global _CASCADES
    if _CASCADES is None:
        base = cv2.data.haarcascades
        _CASCADES = [
            cv2.CascadeClassifier(base + name)
            for name in ("haarcascade_frontalface_alt2.xml", "haarcascade_frontalface_default.xml")
        ]
    return _CASCADES


def _find_face(bgr: np.ndarray) -> tuple[int, int, int, int]:
    """Largest face whose centre is in the middle half of the frame. The capture screen asks the
    user to centre their face, so a face far off-centre is a bystander/poster, not the user."""
    h, w = bgr.shape[:2]
    gray = cv2.equalizeHist(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    min_side = max(60, int(min(h, w) * 0.12))
    found = []
    for cascade in _cascades():
        for x, y, fw, fh in cascade.detectMultiScale(gray, 1.08, 3, minSize=(min_side, min_side)):
            if 0.25 <= (x + fw / 2) / w <= 0.75:
                found.append((int(x), int(y), int(fw), int(fh)))
    if not found:
        raise ValueError(
            "No face found in the middle of the photo. Face the camera inside the outline, "
            "in soft even light (glasses glare or a busy background can also hide it), and try again."
        )
    return max(found, key=lambda r: r[2] * r[3])


def _skin_region(bgr: np.ndarray, box: tuple[int, int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Cheeks/nose/forehead crop of the detected face (hair and jaw edges trimmed) plus a boolean
    skin-pixel mask (YCrCb range), so walls, hair and clothing never enter the measurements."""
    x, y, w, h = box
    face = bgr[y + int(0.30 * h): y + int(0.90 * h), x + int(0.15 * w): x + int(0.85 * w)]
    ycrcb = cv2.cvtColor(face, cv2.COLOR_BGR2YCrCb)
    skin = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127)) > 0
    if skin.mean() < 0.15:  # mask unusable (odd lighting): fall back to the whole face crop
        skin = np.ones(skin.shape, dtype=bool)
    return face, skin


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
    if cv2 is None:
        raise AnalysisUnavailableError(f"OpenCV could not be loaded: {_CV2_ERROR}")
    if not frame_paths:
        raise ValueError("No frames available to analyze")

    per_frame = []
    last_error = None
    for path in frame_paths:
        try:
            full = _load_bgr(path)
            bgr, skin = _skin_region(full, _find_face(full))
        except ValueError as exc:  # unreadable frame or no face: skip it, fail only if none work
            last_error = exc
            continue
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        per_frame.append(
            {
                "redness": _redness(bgr, skin),
                "oiliness": _oiliness(bgr),
                "texture": _texture(gray),
                "pigmentation": _pigmentation(bgr, skin),
                "blemish_index": _blemish_index(bgr),
                "pore_visibility": _pore_visibility(gray),
            }
        )

    if not per_frame:
        raise last_error

    avg = {k: round(sum(f[k] for f in per_frame) / len(per_frame), 1) for k in per_frame[0]}
    hydration = _hydration_proxy(avg["oiliness"], avg["texture"])
    skin_type = _classify_skin_type(avg["oiliness"], hydration)

    concern_avg = (avg["redness"] + avg["pigmentation"] + avg["blemish_index"] + avg["pore_visibility"]) / 4
    # float(): a numpy.float64 can't be bound by psycopg2 (numpy 2 renders it as `np.float64(..)` in SQL)
    overall_score = round(float(np.clip((hydration + avg["texture"] + (100 - concern_avg)) / 3, 0, 100)), 1)

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