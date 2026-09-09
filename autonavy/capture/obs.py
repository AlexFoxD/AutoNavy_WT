"""Optional OpenCV source owned exclusively by the supervised capture child.

The configured index is trusted operator configuration, not verified device identity.
Native open/read/release may block; ProcessCapture owns their time limits.
"""
from dataclasses import replace
import math
import time

from autonavy.capture.base import CaptureError, CaptureSample
from autonavy.geometry import source_geometry
from autonavy.windows import WindowsGeometry


class OBSSource:
    def __init__(self, settings, *, camera_factory=None, geometry_adapter=None):
        self.settings = settings
        self._factory = camera_factory
        self.geometry = geometry_adapter or WindowsGeometry(settings.geometry)
        self.camera = None
        self._previous = None
        self._failures = 0
        self._reported = {}

    def _snapshot(self):
        c = self.settings.capture
        return source_geometry(self.settings, self.geometry.snapshot((c.width, c.height)))

    def _diagnostic(self, delivered=None):
        c = self.settings.capture
        return dict(requested=dict(device_index=c.device_index, api=c.obs_api, width=c.width,
                                   height=c.height, fps=c.fps, pixel_format=c.pixel_format),
                    reported=dict(self._reported), delivered=delivered,
                    device_identity_verified=False, source_timestamp=None)

    def start(self):
        if self.camera is not None:
            return
        self._snapshot()  # Establish window bounds before opening the configured index.
        import cv2
        c = self.settings.capture
        api = {'auto': cv2.CAP_ANY, 'dshow': cv2.CAP_DSHOW, 'msmf': cv2.CAP_MSMF}[c.obs_api]
        self._previous = None
        self._failures = 0
        self._reported = {}
        factory = self._factory if self._factory is not None else cv2.VideoCapture
        # Exactly one index/API. Never enumerate or retry another camera.
        try:
            self.camera = factory(c.device_index, api)
            if self.camera is None or not self.camera.isOpened():
                raise CaptureError(f'OBS configured device failed to open: {self._diagnostic()}')
            for key, value in ((cv2.CAP_PROP_FRAME_WIDTH, c.width), (cv2.CAP_PROP_FRAME_HEIGHT, c.height),
                               (cv2.CAP_PROP_FPS, c.fps), (cv2.CAP_PROP_CONVERT_RGB, 1)):
                self.camera.set(key, value)
            # get() values and the API name are reports, not negotiated-size/device proof.
            self._reported['backend'] = str(self.camera.getBackendName())[:128]
            for name, key in (('width', cv2.CAP_PROP_FRAME_WIDTH), ('height', cv2.CAP_PROP_FRAME_HEIGHT),
                              ('fps', cv2.CAP_PROP_FPS), ('convert_rgb', cv2.CAP_PROP_CONVERT_RGB)):
                value = float(self.camera.get(key))
                self._reported[name] = value if math.isfinite(value) else None
        except BaseException as exc:
            try:
                self.close()
            except Exception as cleanup:
                raise CaptureError(f'OBS startup failed: {exc}; cleanup failed: {cleanup}; {self._diagnostic()}') from exc
            if isinstance(exc, Exception):
                raise CaptureError(f'OBS startup failed: {exc}; {self._diagnostic()}') from exc
            raise

    def read(self):
        if self.camera is None:
            raise CaptureError('OBS source must be started')
        before = self._snapshot()
        if self._previous is not None and self._previous.geometry != before:
            self._previous = None
        try:
            success, pixels = self.camera.read()
        except Exception as exc:
            raise CaptureError(f'OBS read failed: {exc}; {self._diagnostic()}') from exc
        received_at_ns = time.monotonic_ns() if success else None
        after = self._snapshot()
        if before != after:
            self._previous = None
        if not success:
            self._failures += 1
            if self._failures >= self.settings.capture.read_failure_limit:
                raise CaptureError(f'OBS read failed {self._failures} consecutive times: {self._diagnostic()}')
            return self._previous if self.settings.capture.repeated_frames and before == after else None
        import numpy as np
        c = self.settings.capture
        delivered = dict(width=pixels.shape[1] if isinstance(pixels, np.ndarray) and pixels.ndim >= 2 else None,
                         height=pixels.shape[0] if isinstance(pixels, np.ndarray) and pixels.ndim >= 2 else None,
                         channels=pixels.shape[2] if isinstance(pixels, np.ndarray) and pixels.ndim == 3 else None,
                         dtype=str(pixels.dtype) if isinstance(pixels, np.ndarray) else None,
                         pixel_format=('BGR' if isinstance(pixels, np.ndarray) and pixels.dtype == np.uint8
                                       and pixels.ndim == 3 and pixels.shape[2] == 3 else None))
        if not isinstance(pixels, np.ndarray) or pixels.dtype != np.uint8 or pixels.shape != (c.height, c.width, 3):
            raise CaptureError(f'OBS delivered incompatible uint8 BGR frame: {self._diagnostic(delivered)}')
        self._failures = 0
        if before != after:
            return None
        sample = CaptureSample(pixels, before, received_at_ns, self._diagnostic(delivered))
        if c.repeated_frames:
            self._previous = replace(sample, image=pixels.copy())
            return self._previous
        return sample

    def close(self):
        camera, self.camera = self.camera, None
        self._previous = None
        self._failures = 0
        if camera is not None:
            camera.release()
