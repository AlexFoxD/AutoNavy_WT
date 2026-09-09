"""Bounded derivatives owned by one selected publication, never by a camera."""
from collections import OrderedDict

import cv2
import numpy as np

from autonavy.models import FramePacket


class FrameContext:
    def __init__(self, packet: FramePacket, *, max_entries=64):
        if not isinstance(packet, FramePacket) or type(max_entries) is not int or max_entries < 1:
            raise ValueError('FrameContext requires a packet and a positive cache bound')
        self.packet = packet
        self._cache = OrderedDict()
        self._max_entries = max_entries

    @property
    def cache_size(self):
        return len(self._cache)

    def _cached(self, key, build):
        key = (self.packet.pixel_format, *key)
        if key not in self._cache:
            value = build()
            value.flags.writeable = False
            self._cache[key] = value
            if len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)
        self._cache.move_to_end(key)
        return self._cache[key]

    def _rect(self, roi):
        roi = tuple(roi)
        h, w = self.packet.image.shape[:2]
        if len(roi) != 4 or any(type(v) is not int for v in roi):
            raise ValueError('ROI requires four integer frame coordinates')
        l, t, r, b = roi
        if not (0 <= l < r <= w and 0 <= t < b <= h):
            raise ValueError('ROI is empty or outside frame')
        return roi

    def profile_roi(self, roi):
        """Translate an unscaled profile crop through game content, not desktop origin."""
        geometry = self.packet.geometry
        if geometry is None:
            raise ValueError('Profile ROI requires packet geometry')
        l, t, r, b = tuple(roi)
        w, h = geometry.profile_size
        if any(type(v) is not int for v in (l,t,r,b)) or not (0 <= l < r <= w and 0 <= t < b <= h):
            raise ValueError('ROI is outside reference profile')
        a, top, c, d = geometry.content_rect
        if (c-a, d-top) != (w,h):
            raise ValueError('Recognition of scaled content is unsupported')
        return self._rect((a+l, top+t, a+r, top+b))

    def roi(self, roi):
        l, t, r, b = self._rect(roi)
        return self.packet.image[t:b, l:r]

    def bgr(self, roi):
        rect = self._rect(roi)
        return self._cached(('bgr', rect), lambda: self.roi(rect)[:, :, :3])

    def hsv(self, roi):
        rect = self._rect(roi)
        return self._cached(('hsv', rect), lambda: cv2.cvtColor(self.bgr(rect), cv2.COLOR_BGR2HSV))

    def gray(self, roi):
        rect = self._rect(roi)
        return self._cached(('gray', rect), lambda: cv2.cvtColor(self.bgr(rect), cv2.COLOR_BGR2GRAY))

    def mask(self, roi, lower, upper, morphology_size=1):
        rect = self._rect(roi)
        lower, upper = tuple(lower), tuple(upper)
        if type(morphology_size) is not int or morphology_size < 1 or morphology_size % 2 != 1:
            raise ValueError('Morphology size must be a positive odd integer')
        def build():
            mask = cv2.inRange(self.hsv(rect), np.array(lower), np.array(upper))
            # Boundary policy is the selected ROI; 1x1 close/open is exactly identity.
            if morphology_size > 1:
                kernel = np.ones((morphology_size, morphology_size), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            return mask
        return self._cached(('mask', rect, lower, upper, morphology_size), build)

    def edges(self, roi, settings, *, mask=None):
        rect = self._rect(roi)
        mask = None if mask is None else (tuple(mask[0]), tuple(mask[1]), mask[2])
        def build():
            # Retain raw color Canny, including alpha if the packet has it.
            source = self.mask(rect, *mask) if mask is not None else (
                self.gray(rect) if settings.canny_input == 'gray' else self.roi(rect))
            return cv2.Canny(source, settings.canny_low, settings.canny_high)
        return self._cached(('edges', rect, settings.canny_input, settings.canny_low,
                             settings.canny_high, settings.preprocess_version, mask), build)

    def debug_image(self):
        """Allocate only at the explicit preview boundary; never draw on packet views."""
        return self.packet.image.copy()
