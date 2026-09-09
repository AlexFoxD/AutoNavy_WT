"""Explicit packet/context or heading-ROI compatibility; never reads a camera."""
import cv2
import numpy as np

from autonavy.config import VisionSettings
from autonavy.models import FramePacket
from autonavy.vision.context import FrameContext
from autonavy.vision.detectors import angle_from_mask, detect_degree
from autonavy.vision.templates import validate_image


def get_deg(selected):
    """Return degrees or None from the caller's packet/context or explicit heading ROI."""
    if isinstance(selected, (FramePacket,FrameContext)):
        context = FrameContext(selected) if isinstance(selected,FramePacket) else selected
        return detect_degree(context).degrees
    validate_image('heading ROI',selected)
    if selected.ndim != 3:
        raise ValueError('Explicit heading ROI must use BGR/BGRA pixels')
    settings = VisionSettings()
    hsv = cv2.cvtColor(selected[:,:,:3],cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,np.array(settings.heading_hsv_lower),np.array(settings.heading_hsv_upper))
    return angle_from_mask(mask)[0]
