"""Unicode-safe loading helpers for Windows runtime resources."""

from pathlib import Path

import cv2
import numpy as np


def read_image(path, flags=cv2.IMREAD_COLOR):
    """Read an image without passing a Unicode Windows path to OpenCV."""
    try:
        encoded = np.fromfile(Path(path), dtype=np.uint8)
    except OSError:
        return None
    if encoded.size == 0:
        return None
    return cv2.imdecode(encoded, flags)
