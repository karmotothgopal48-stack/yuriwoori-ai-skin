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

Two body parts are supported, and the body part is decided before any measuring:
- face: MediaPipe's Face Landmarker (478 landmarks) finds the face and checks it is complete
  (one face, fully in frame, centred, large enough, not turned or tilted, not covered by a hand).
  The landmarks outline a consistent skin region (forehead, cheeks, nose, chin; eyes, brows and
  lips excluded), resampled to a fixed size, and all seven metrics are measured inside it.
- hand: MediaPipe's trained hand-landmark model finds the hand; only the metrics that mean
  something on hand skin are measured (pores, blemishes and oil are facial measures: None).

Every metric is measured only on the pixels of its skin mask (never on background, eyes or lips).
"""

import os
import threading

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


def _load_bgr(frame) -> np.ndarray:
    """One frame as a BGR image: raw image bytes, decoded in memory (scan photos are never written to disk),
    or a file path."""
    if isinstance(frame, (bytes, bytearray)):
        image = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not read the uploaded image")
        return image
    image = cv2.imread(frame)
    if image is None:
        raise ValueError(f"Could not read image at {frame}")
    return image


def _redness(bgr: np.ndarray, skin: np.ndarray) -> float:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    a_channel = lab[:, :, 1][skin].astype(np.float32)  # 128 = neutral, >128 = red/magenta
    redness = np.clip((a_channel.mean() - 128) * 2.2, 0, 100)
    return round(float(redness), 1)


def _oiliness(bgr: np.ndarray, skin: np.ndarray) -> float:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v, s = hsv[:, :, 2][skin].astype(np.float32), hsv[:, :, 1][skin].astype(np.float32)
    shine_mask = (v > 200) & (s < 60)  # bright + low saturation = specular highlight
    shine_ratio = shine_mask.mean()
    return round(float(np.clip(shine_ratio * 400, 0, 100)), 1)


def _texture(gray: np.ndarray, skin: np.ndarray) -> float:
    variance = cv2.Laplacian(gray, cv2.CV_64F)[skin].var()
    roughness = np.clip(variance / 8.0, 0, 100)
    return round(float(100 - roughness), 1)  # higher = smoother/healthier


def _pigmentation(bgr: np.ndarray, skin: np.ndarray) -> float:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0][skin].astype(np.float32)
    unevenness = np.clip(l_channel.std() * 1.8, 0, 100)
    return round(float(unevenness), 1)


def _blemish_index(bgr: np.ndarray, skin: np.ndarray) -> float:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 60, 40])
    upper = np.array([12, 255, 200])
    mask = cv2.inRange(hsv, lower, upper) & (skin.astype(np.uint8) * 255)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    spots = [c for c in contours if 8 < cv2.contourArea(c) < 400]
    density = len(spots) / (skin.sum() / 10000)
    return round(float(np.clip(density * 3, 0, 100)), 1)


def _pore_visibility(gray: np.ndarray, skin: np.ndarray) -> float:
    """Fine detail in the centre of the region (nose and inner cheeks on a face)."""
    h, w = gray.shape
    centre = np.zeros_like(skin)
    centre[int(h * 0.3): int(h * 0.7), int(w * 0.3): int(w * 0.7)] = True
    variance = cv2.Laplacian(gray, cv2.CV_64F)[skin & centre].var()
    return round(float(np.clip(variance / 6.0, 0, 100)), 1)


def _skin_mask(crop: np.ndarray, region: np.ndarray) -> np.ndarray:
    """Skin-coloured pixels (YCrCb range) inside the outlined region, so hair, shadows and
    background never enter the measurements. Odd lighting can defeat the colour range: if fewer
    than 15 % of the region's pixels pass it, the whole outlined region is used instead."""
    ycrcb = cv2.cvtColor(crop, cv2.COLOR_BGR2YCrCb)
    skin = region & (cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127)) > 0)
    return skin if skin.sum() >= 0.15 * region.sum() else region


# ---------- face ----------
# The face is located with MediaPipe's Face Landmarker (478 landmarks + head pose). A Haar cascade
# only gives a rectangle, so it cannot tell a complete face from a cut-off one, and its rectangle
# (and the crop taken from it) shifts from photo to photo.

FACE_MODEL_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "models", "face_landmarker.task")
)
# Server-side checks: the safety net for uploads and direct API calls. The camera screen applies
# stricter versions of the same checks live (frontend services/bodyPart.js, LIVE rules).
MAX_YAW, MAX_PITCH, MAX_ROLL = 25.0, 25.0, 15.0  # degrees of head turn / nod / tilt
MIN_FACE_SHARE, MAX_FACE_SHARE = 0.15, 0.90  # forehead-to-chin height as a share of the photo height
SECOND_FACE_SHARE = 0.25  # another face at least this big (relative to the main one) = "multiple faces"
EDGE_MARGIN = 0.01  # key landmarks must sit at least this far inside the photo edges
# Every face is resampled so forehead-to-chin is this many pixels before measuring: texture, pores
# and blemishes are pixel-scale measures, so without this the same face scored 0-89 for texture
# depending only on camera resolution and distance. Faces smaller than this are rejected, not
# upscaled (upscaling would invent smoothness).
ANALYSIS_FACE_HEIGHT = 224

_FOREHEAD, _CHIN, _LEFT_CHEEK, _RIGHT_CHEEK = 10, 152, 234, 454
_LEFT_EYE_OUTER, _RIGHT_EYE_OUTER, _NOSE_TIP = 33, 263, 1
_KEY_LANDMARKS = [_FOREHEAD, _CHIN, _LEFT_CHEEK, _RIGHT_CHEEK, _LEFT_EYE_OUTER, _RIGHT_EYE_OUTER, _NOSE_TIP]
# Face outline (MediaPipe face-mesh FACE_OVAL, in order around the face).
_FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377,
              152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]

FACE_MESSAGES = {
    "none": "No usable face found. Centre your full face in the frame, in soft even light, and try again.",
    "multiple": "Only one face should be visible. Make sure nobody else is in the photo and try again.",
    "cut_off": "Centre your full face in the frame: part of it is outside the photo.",
    "off_centre": "Centre your full face in the frame and try again.",
    "too_far": "Move slightly closer: your face is too small in the photo.",
    "too_close": "Move slightly farther away: your face is too large in the photo.",
    "tilted": "Keep your head straight and look directly at the camera, then try again.",
    "blocked": "Make sure your full face is visible, with nothing (such as a hand) covering it.",
}

_FACE_LANDMARKER = None
_FACE_LOCK = threading.Lock()


def _face_landmarker():
    global _FACE_LANDMARKER
    if _FACE_LANDMARKER is None:
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
        except ImportError as exc:
            raise AnalysisUnavailableError(f"MediaPipe could not be loaded: {exc}")
        if not os.path.exists(FACE_MODEL_PATH):
            raise AnalysisUnavailableError(f"Face model not found at {FACE_MODEL_PATH}")
        with open(FACE_MODEL_PATH, "rb") as f:
            options = vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_buffer=f.read()),
                running_mode=vision.RunningMode.IMAGE,
                num_faces=3,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                output_facial_transformation_matrixes=True,
            )
        conn = vision.FaceLandmarksConnections
        # Eyes + brows (one area per side) and lips are cut out of the skin region.
        exclusions = [
            sorted({i for c in group for i in (c.start, c.end)})
            for group in (
                conn.FACE_LANDMARKS_LEFT_EYE + conn.FACE_LANDMARKS_LEFT_EYEBROW,
                conn.FACE_LANDMARKS_RIGHT_EYE + conn.FACE_LANDMARKS_RIGHT_EYEBROW,
                conn.FACE_LANDMARKS_LIPS,
            )
        ]
        _FACE_LANDMARKER = (mp, vision.FaceLandmarker.create_from_options(options), exclusions)
    return _FACE_LANDMARKER


def _head_pose(matrix) -> tuple[float, float, float]:
    """(yaw, pitch, roll) in degrees from the face's 4x4 transformation matrix."""
    r = np.asarray(matrix)[:3, :3]
    yaw = np.degrees(np.arcsin(-np.clip(r[2, 0], -1, 1)))
    pitch = np.degrees(np.arctan2(r[2, 1], r[2, 2]))
    roll = np.degrees(np.arctan2(r[1, 0], r[0, 0]))
    return float(yaw), float(pitch), float(roll)


def _box(points: np.ndarray) -> tuple[float, float, float, float]:
    return points[:, 0].min(), points[:, 1].min(), points[:, 0].max(), points[:, 1].max()


def _overlap_share(a, b) -> float:
    """Share of box a covered by box b."""
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return (w * h) / max((a[2] - a[0]) * (a[3] - a[1]), 1e-6)


def _find_full_face(bgr: np.ndarray) -> np.ndarray:
    """The 478 landmark points (pixels) of one complete, usable face, or ValueError saying what to fix."""
    h, w = bgr.shape[:2]
    mp, landmarker, _ = _face_landmarker()
    rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    with _FACE_LOCK:
        result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not result.face_landmarks:
        raise ValueError(FACE_MESSAGES["none"])

    faces = [np.array([[p.x, p.y] for p in lms], dtype=np.float32) for lms in result.face_landmarks]  # 0-1
    # Forehead-to-chin length (straight line, so a slight tilt doesn't shrink it) as a share of the photo height
    heights = [float(np.hypot((f[_CHIN, 0] - f[_FOREHEAD, 0]) * w, (f[_CHIN, 1] - f[_FOREHEAD, 1]) * h)) / h for f in faces]
    main = int(np.argmax(heights))
    if any(i != main and heights[i] >= SECOND_FACE_SHARE * heights[main] for i in range(len(faces))):
        raise ValueError(FACE_MESSAGES["multiple"])
    face, share = faces[main], heights[main]

    key = face[_KEY_LANDMARKS]
    if share > MAX_FACE_SHARE:
        raise ValueError(FACE_MESSAGES["too_close"])
    if (key < EDGE_MARGIN).any() or (key > 1 - EDGE_MARGIN).any():
        raise ValueError(FACE_MESSAGES["cut_off"])
    yaw, pitch, roll = _head_pose(result.facial_transformation_matrixes[main])
    if abs(yaw) > MAX_YAW or abs(pitch) > MAX_PITCH or abs(roll) > MAX_ROLL:
        raise ValueError(FACE_MESSAGES["tilted"])
    if share < MIN_FACE_SHARE or share * h < ANALYSIS_FACE_HEIGHT:
        raise ValueError(FACE_MESSAGES["too_far"])
    cx = (face[_LEFT_CHEEK, 0] + face[_RIGHT_CHEEK, 0]) / 2
    cy = (face[_FOREHEAD, 1] + face[_CHIN, 1]) / 2
    if not (0.25 <= cx <= 0.75 and 0.15 <= cy <= 0.85):
        raise ValueError(FACE_MESSAGES["off_centre"])

    # The landmarker estimates hidden parts of a face, so a hand over it is checked separately.
    hand_mp, hands = _hand_landmarker()
    with _HAND_LOCK:
        hand_result = hands.detect(hand_mp.Image(image_format=hand_mp.ImageFormat.SRGB, data=rgb))
    face_box = _box(face)
    for lms in hand_result.hand_landmarks:
        hand = np.array([[p.x, p.y] for p in lms], dtype=np.float32)
        if _overlap_share(face_box, _box(hand)) > 0.10:
            raise ValueError(FACE_MESSAGES["blocked"])

    return face * np.array([w, h], dtype=np.float32)


def _face_region(bgr: np.ndarray, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The face resampled to ANALYSIS_FACE_HEIGHT and cropped to its outline, plus the skin mask:
    inside the face outline, minus eyes + brows and lips, minus non-skin-coloured pixels."""
    _, _, exclusions = _face_landmarker()
    scale = ANALYSIS_FACE_HEIGHT / float(np.hypot(*(points[_CHIN] - points[_FOREHEAD])))
    image = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    pts = points * scale
    h, w = image.shape[:2]

    outline = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(outline, [pts[_FACE_OVAL].astype(np.int32)], 255)
    for idx in exclusions:
        cv2.fillConvexPoly(outline, cv2.convexHull(pts[idx].astype(np.int32)), 0)
    # Shrink away from every edge (jawline, hairline, eyes, lips) so their contrast never reads as texture.
    k = max(3, int(ANALYSIS_FACE_HEIGHT * 0.03))
    outline = cv2.erode(outline, np.ones((k, k), np.uint8))

    x, y, rw, rh = cv2.boundingRect(pts[_FACE_OVAL].astype(np.int32))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + rw, w), min(y + rh, h)
    crop, region = image[y0:y1, x0:x1], outline[y0:y1, x0:x1] > 0
    return crop, _skin_mask(crop, region)


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


# The measurements each analysis produces (the hand pipeline has no oil, pore or blemish measures).
MEASURED_METRICS = {
    "face": ("hydration", "texture", "oiliness", "redness", "pigmentation", "pore_visibility", "blemish_index"),
    "hand": ("hydration", "texture", "redness", "pigmentation"),
}


def missing_measurements(profile, body_part: str) -> list[str]:
    """Measurements this scan type should have but the saved analysis lacks (an incomplete analysis
    must not be read as "no concerns")."""
    return [f for f in MEASURED_METRICS[body_part] if getattr(profile, f, None) is None]


def body_part_of(angles: list[str] | None) -> str:
    """A hand scan's frames are uploaded with angle "hand"; anything else ("front") is a face scan."""
    return "hand" if HAND_ANGLE in (angles or []) else "face"


def analyze_skin_profile(frame_paths: list[str], body_part: str = "face") -> dict:
    if cv2 is None:
        raise AnalysisUnavailableError(f"OpenCV could not be loaded: {_CV2_ERROR}")
    if not frame_paths:
        raise ValueError("No frames available to analyze")
    if body_part == "hand":
        return _analyze_hand_profile(frame_paths)

    per_frame = []
    last_error = None
    for path in frame_paths:
        try:
            full = _load_bgr(path)
            bgr, skin = _face_region(full, _find_full_face(full))
        except ValueError as exc:  # unreadable frame or no usable face: skip it, fail only if none work
            last_error = exc
            continue
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        per_frame.append(
            {
                "redness": _redness(bgr, skin),
                "oiliness": _oiliness(bgr, skin),
                "texture": _texture(gray, skin),
                "pigmentation": _pigmentation(bgr, skin),
                "blemish_index": _blemish_index(bgr, skin),
                "pore_visibility": _pore_visibility(gray, skin),
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

# ---------- hand ----------
# Hands are located with MediaPipe's trained hand-landmark model (21 keypoints per hand), not with
# colour rules: OpenCV has no reliable hand cascade, and a skin-colour mask also accepts wood or walls.

HAND_ANGLE = "hand"
HAND_MODEL_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "models", "hand_landmarker.task")
)
MIN_HAND_SCORE = 0.6
# Wrist, thumb base and the four knuckles outline the back of the hand / palm. Fingers are left out:
# they are thin, folded and carry nails, so they would skew colour and texture.
_HAND_REGION_LANDMARKS = [0, 1, 2, 5, 9, 13, 17]

_HAND_LANDMARKER = None
_HAND_LOCK = threading.Lock()  # one MediaPipe graph, shared by the request threads


def _hand_landmarker():
    global _HAND_LANDMARKER
    if _HAND_LANDMARKER is None:
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
        except ImportError as exc:
            raise AnalysisUnavailableError(f"MediaPipe could not be loaded: {exc}")
        if not os.path.exists(HAND_MODEL_PATH):
            raise AnalysisUnavailableError(f"Hand model not found at {HAND_MODEL_PATH}")
        with open(HAND_MODEL_PATH, "rb") as f:
            options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_buffer=f.read()),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
            )
        _HAND_LANDMARKER = (mp, vision.HandLandmarker.create_from_options(options))
    return _HAND_LANDMARKER


def _find_hand(bgr: np.ndarray) -> np.ndarray:
    """21 landmark points (pixels) of the largest confidently detected hand whose palm area is big
    enough to measure. Anything else (no hand, a tiny hand in the background) is rejected."""
    h, w = bgr.shape[:2]
    mp, landmarker = _hand_landmarker()
    rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    with _HAND_LOCK:
        result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    found = []
    for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
        if handedness[0].score < MIN_HAND_SCORE:
            continue
        points = np.array([[p.x * w, p.y * h] for p in landmarks], dtype=np.float32)
        palm = points[_HAND_REGION_LANDMARKS]
        if max(np.ptp(palm[:, 0]), np.ptp(palm[:, 1])) >= 0.12 * min(h, w):
            found.append(points)
    if not found:
        raise ValueError(
            "No hand found in the photo. Hold one hand open inside the frame, close enough to fill most "
            "of it, in soft even light, and try again."
        )
    return max(found, key=lambda pts: cv2.contourArea(cv2.convexHull(pts[_HAND_REGION_LANDMARKS])))


def _hand_region(bgr: np.ndarray, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Crop around the palm/back-of-hand outline plus a boolean mask of the skin inside it.
    The outline is shrunk slightly so background at its edge never enters the measurements."""
    h, w = bgr.shape[:2]
    hull = cv2.convexHull(points[_HAND_REGION_LANDMARKS].astype(np.int32))
    x, y, rw, rh = cv2.boundingRect(hull)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + rw, w), min(y + rh, h)
    outline = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(outline, hull, 255)
    k = max(3, int(min(rw, rh) * 0.08)) | 1
    outline = cv2.erode(outline, np.ones((k, k), np.uint8))
    crop, region = bgr[y0:y1, x0:x1], outline[y0:y1, x0:x1] > 0
    if region.sum() < 400:
        raise ValueError("The hand is too small in the photo. Move it closer to the camera and try again.")
    return crop, _skin_mask(crop, region)


def _analyze_hand_profile(frame_paths: list[str]) -> dict:
    per_frame = []
    last_error = None
    for path in frame_paths:
        try:
            full = _load_bgr(path)
            bgr, skin = _hand_region(full, _find_hand(full))
        except ValueError as exc:  # unreadable frame or no hand: skip it, fail only if none work
            last_error = exc
            continue
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        per_frame.append(
            {
                "redness": _redness(bgr, skin),
                "texture": _texture(gray, skin),
                "pigmentation": _pigmentation(bgr, skin),
                "shine": _oiliness(bgr, skin),  # only feeds the hydration proxy
            }
        )

    if not per_frame:
        raise last_error

    avg = {k: round(sum(f[k] for f in per_frame) / len(per_frame), 1) for k in per_frame[0]}
    hydration = _hydration_proxy(avg["shine"], avg["texture"])
    concern_avg = (avg["redness"] + avg["pigmentation"]) / 2
    overall_score = round(float(np.clip((hydration + avg["texture"] + (100 - concern_avg)) / 3, 0, 100)), 1)

    return {
        "skin_type": "dry" if hydration < 45 else "normal",  # oily/combination are facial (T-zone) types
        "hydration": hydration,
        "oiliness": None,
        "texture": avg["texture"],
        "redness": avg["redness"],
        "pigmentation": avg["pigmentation"],
        "blemish_index": None,
        "pore_visibility": None,
        "overall_score": overall_score,
    }
