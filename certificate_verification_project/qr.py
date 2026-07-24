"""Fast QR detection with a short screenshot-friendly fallback chain."""

from collections.abc import Iterator

import cv2
import numpy as np
from PIL import Image

# Cap size so upscaling a tiny screenshot stays fast.
MAX_EDGE_PX = 1400
SMALL_IMAGE_EDGE = 900
PADDING_PX = 40

_detector: cv2.QRCodeDetector | None = None


def decode_qr_from_image(image: Image.Image) -> str | None:
    """Return decoded QR text, or None. Stops at the first successful decode."""
    bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)

    for variant in _variant_pipeline(bgr):
        text = _decode_variant(variant)
        if text:
            return text

    return None


def _variant_pipeline(bgr: np.ndarray) -> Iterator[np.ndarray]:
    """Yield a small ordered list: quick tries first, heavier screenshot tries last."""
    yield bgr

    height, width = bgr.shape[:2]
    min_edge = min(height, width)

    if min_edge > SMALL_IMAGE_EDGE:
        return

    # Screenshot path: one upscale + footer crops (where NPTEL-style QRs sit).
    scaled = _upscale_to_max_edge(bgr)
    if scaled is not bgr:
        yield scaled
        bgr = scaled
        height, width = bgr.shape[:2]

    band = bgr[int(height * 0.78) :, :]
    if band.size == 0:
        return

    yield band
    yield _pad(band)

    band_w = band.shape[1]
    center = band[:, int(band_w * 0.30) : int(band_w * 0.70)]
    if center.size:
        yield _pad(center)

    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
    yield _pad(cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR))


def _upscale_to_max_edge(bgr: np.ndarray) -> np.ndarray:
    height, width = bgr.shape[:2]
    min_edge = min(height, width)
    if min_edge >= MAX_EDGE_PX:
        return bgr

    scale = MAX_EDGE_PX / min_edge
    return cv2.resize(
        bgr,
        (int(width * scale), int(height * scale)),
        interpolation=cv2.INTER_CUBIC,
    )


def _pad(bgr: np.ndarray) -> np.ndarray:
    return cv2.copyMakeBorder(
        bgr, PADDING_PX, PADDING_PX, PADDING_PX, PADDING_PX,
        cv2.BORDER_CONSTANT,
        value=(255, 255, 255),
    )


def _decode_variant(bgr: np.ndarray) -> str | None:
    """OpenCV first (fast), zxing only if needed."""
    for text in _decode_opencv(bgr):
        return text

    for text in _decode_zxing(bgr):
        return text

    return None


def _get_detector() -> cv2.QRCodeDetector:
    global _detector
    if _detector is None:
        _detector = cv2.QRCodeDetector()
    return _detector


def _decode_opencv(bgr: np.ndarray) -> list[str]:
    detector = _get_detector()
    found: list[str] = []

    ok, decoded_list, _, _ = detector.detectAndDecodeMulti(bgr)
    if ok and decoded_list is not None:
        found.extend(t.strip() for t in decoded_list if t and t.strip())

    if found:
        return found

    data, _, _ = detector.detectAndDecode(bgr)
    if data and data.strip():
        found.append(data.strip())

    return found


def _decode_zxing(bgr: np.ndarray) -> list[str]:
    try:
        import zxingcpp
    except ImportError:
        return []

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return [
        result.text.strip()
        for result in zxingcpp.read_barcodes(rgb)
        if result.text and result.text.strip()
    ]

