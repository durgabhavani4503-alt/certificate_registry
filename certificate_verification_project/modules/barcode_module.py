"""
Read linear barcodes from certificate images (not QR codes).

QR scanning stays in qr.py — this module runs only when QR was not found.
"""

from collections.abc import Iterator

import cv2
import numpy as np
from PIL import Image

MAX_EDGE_PX = 1400
SMALL_IMAGE_EDGE = 900

# ZXing format names to skip (those are QR / matrix codes).
QR_FORMAT_NAMES = {"QRCode", "MicroQRCode", "RMQRCode", "Aztec", "DataMatrix", "PDF417"}


def decode_barcode_from_image(image: Image.Image) -> str | None:
    """Return decoded barcode text, or None if no linear barcode is found."""
    bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)

    for variant in _variant_pipeline(bgr):
        text = _decode_linear_barcodes(variant)
        if text:
            return text

    return None


def _variant_pipeline(bgr: np.ndarray) -> Iterator[np.ndarray]:
    yield bgr

    height, width = bgr.shape[:2]
    if min(height, width) > SMALL_IMAGE_EDGE:
        return

    scale = MAX_EDGE_PX / min(height, width)
    if scale > 1.0:
        bgr = cv2.resize(
            bgr,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_CUBIC,
        )

    yield bgr
    yield bgr[int(bgr.shape[0] * 0.7) :, :]


def _decode_linear_barcodes(bgr: np.ndarray) -> str | None:
    try:
        import zxingcpp
    except ImportError:
        return None

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    for result in zxingcpp.read_barcodes(rgb):
        format_name = str(result.format)
        if format_name in QR_FORMAT_NAMES:
            continue
        if result.text and result.text.strip():
            return result.text.strip()

    return None
