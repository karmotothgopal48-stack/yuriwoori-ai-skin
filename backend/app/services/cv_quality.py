"""
Frame-quality preprocessing gate.

Runs a lightweight, deterministic check on a single uploaded scan frame
before it is accepted into a scan (called from
app/api/v1/endpoints/scans.py::upload_frame).

This intentionally does NOT do a full pixel-space decode, so the gate stays
fast and does not depend on OpenCV being loadable (skin_analysis.py uses cv2
for the later, deeper analysis step). It works only with real, deterministic
facts about the actual uploaded bytes:

  * the JPEG frame header (SOF marker), which stores the true pixel
    width/height in plain bytes -- no entropy decoding required -- so the
    "bytes per pixel" of the compressed frame is a real, well-established
    detail/blur proxy (a smoother/blurrier/flatter capture has less
    high-frequency detail for the encoder to spend bits on, so it
    compresses smaller at the same JPEG quality setting);
  * the mean byte value of the compressed frame, used as a rough,
    explicitly-disclosed proxy for exposure/lighting when no pixel decode
    is available -- the same "honest proxy, not a trained model" approach
    already used by _hydration_proxy() in skin_analysis.py.

This can be upgraded to true pixel-space blur (Laplacian variance) and
brightness (mean luminance) without changing the analyze_frame() contract
relied on by scans.py.
"""

import base64
import binascii

import numpy as np

_JPEG_SOI = b"\xff\xd8"
_JPEG_EOI = b"\xff\xd9"

# Markers that carry a Start-Of-Frame (SOF) segment -- excludes DHT (0xC4),
# JPG (0xC8) and DAC (0xCC), which share the numeric range but aren't SOF.
_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}

MIN_JPEG_BYTES = 4_000  # a webcam JPEG this small is almost certainly blank/corrupt
BYTES_PER_PIXEL_TARGET = 0.35  # typical in-focus webcam JPEG at quality ~0.9
# blur_score and lighting_score are both "higher = better" goodness scores
# (100 = ideal), not raw measurements, so passing is a simple lower bound on
# each rather than a min/max band.
LIGHTING_MIN = 40.0
BLUR_MIN = 15.0
QUALITY_PASS_THRESHOLD = 55.0


def _decode_bytes(image_base64: str) -> bytes:
    """Accepts either a raw base64 string or a `data:image/...;base64,` URL."""
    raw = image_base64.split(",", 1)[-1] if "," in image_base64 else image_base64
    try:
        return base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError):
        return b""


def _is_valid_jpeg(data: bytes) -> bool:
    return (
        len(data) >= MIN_JPEG_BYTES
        and data.startswith(_JPEG_SOI)
        and _JPEG_EOI in data[-16:]
    )


def _extract_jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    """Read the JPEG SOF marker to get (width, height) without decoding pixels."""
    i = 2  # skip the SOI marker (FF D8)
    n = len(data)
    try:
        while i + 4 <= n:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2  # standalone marker, no length/payload
                continue
            if marker == 0xDA:
                break  # Start-Of-Scan reached; no SOF segment was found before it
            seg_len = (data[i + 2] << 8) | data[i + 3]
            if marker in _SOF_MARKERS:
                if i + 9 > n:
                    return None
                height = (data[i + 5] << 8) | data[i + 6]
                width = (data[i + 7] << 8) | data[i + 8]
                return (width, height) if width > 0 and height > 0 else None
            i += 2 + seg_len
    except IndexError:
        return None
    return None


def _byte_stats(data: bytes) -> tuple[float, float]:
    """Return (mean_byte_value, shannon_entropy_bits) over the raw frame bytes."""
    arr = np.frombuffer(data, dtype=np.uint8)
    mean_val = float(arr.mean())
    counts = np.bincount(arr, minlength=256).astype(np.float64)
    probs = counts[counts > 0] / counts.sum()
    entropy = float(-(probs * np.log2(probs)).sum())  # 0 (flat) .. 8 (fully random) bits/byte
    return mean_val, entropy


def analyze_frame(image_base64: str) -> dict:
    """Score one uploaded scan frame. Returns the dict consumed by
    app/api/v1/endpoints/scans.py::upload_frame (blur_score, lighting_score,
    quality_score, passed), matching FrameQualityResponse in app/schemas.py.
    """
    data = _decode_bytes(image_base64)

    if not _is_valid_jpeg(data):
        return {
            "blur_score": 0.0,
            "lighting_score": 0.0,
            "quality_score": 0.0,
            "passed": False,
        }

    mean_val, entropy = _byte_stats(data)
    dimensions = _extract_jpeg_dimensions(data)

    if dimensions:
        width, height = dimensions
        bytes_per_pixel = len(data) / float(width * height)
        blur_score = (bytes_per_pixel / BYTES_PER_PIXEL_TARGET) * 100
    else:
        # No parsable SOF segment (non-baseline/corrupt) -- fall back to the
        # byte-entropy proxy so we still return a real, data-derived score.
        blur_score = (entropy / 8.0) * 100
    blur_score = round(float(np.clip(blur_score, 0, 100)), 1)

    # Rough, disclosed proxy only (see module docstring): mid-gray-centered
    # mapping of the mean compressed-byte value.
    lighting_score = round(float(np.clip(100 - abs(mean_val - 128) * (100 / 128), 0, 100)), 1)

    quality_score = round(blur_score * 0.6 + lighting_score * 0.4, 1)

    passed = (
        blur_score >= BLUR_MIN
        and lighting_score >= LIGHTING_MIN
        and quality_score >= QUALITY_PASS_THRESHOLD
    )

    return {
        "blur_score": blur_score,
        "lighting_score": lighting_score,
        "quality_score": quality_score,
        "passed": passed,
    }
