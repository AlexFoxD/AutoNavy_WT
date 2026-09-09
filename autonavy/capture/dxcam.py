"""Pinned DXcam 0.0.5 native owner. Construct and call only in capture child."""
import time
from autonavy.capture.base import CaptureError, CaptureSample
from autonavy.windows import WindowsGeometry


class DXcamSource:
    def __init__(self, settings, *, camera_factory=None, geometry_adapter=None):
        self.settings = settings
        self._factory = camera_factory
        self.geometry = geometry_adapter or WindowsGeometry(settings.geometry)
        self.camera = None
        self._previous = None

    def _snapshot(self):
        c = self.settings.capture
        snapshot = self.geometry.snapshot((c.width, c.height))
        l, t, r, b = snapshot.client_rect
        if (r-l, b-t) != (c.width, c.height):
            raise CaptureError('Game client size does not match configured capture size')
        return snapshot

    def _output_rect(self):
        # Pinned 0.0.5 exposes DXGI desktop coordinates here; never substitute monitor indexes.
        try:
            rect = self.camera._output.desc.DesktopCoordinates
            return tuple(int(getattr(rect, key)) for key in ('left', 'top', 'right', 'bottom'))
        except (AttributeError, TypeError, ValueError) as exc:
            raise CaptureError('Cannot establish selected DXcam output desktop coordinates') from exc

    def start(self):
        if self.camera is not None:
            return
        self._snapshot()  # Fail missing/invalid window before importing DXcam and enumerating devices.
        factory = self._factory
        if factory is None:
            import dxcam
            factory = dxcam.create
        c = self.settings.capture
        self.camera = factory(device_idx=c.device_index, output_idx=c.output_index,
                              output_color=c.pixel_format, max_buffer_len=1)
        try:
            self._snapshot().output_region(self._output_rect())
        except BaseException:
            self.close()
            raise

    def read(self):
        if self.camera is None:
            raise CaptureError('DXcam source must be started')
        before = self._snapshot()
        if self._previous is not None and self._previous.geometry != before:
            self._previous = None
        output = self._output_rect()
        pixels = self.camera.grab(region=before.output_region(output))
        after = self._snapshot()
        if before != after or output != self._output_rect():
            self._previous = None
            return None
        if pixels is None:
            if self.settings.capture.repeated_frames and self._previous is not None and self._previous.geometry == before:
                return self._previous
            return None
        expected = (self.settings.capture.height, self.settings.capture.width, 3 if self.settings.capture.pixel_format == 'BGR' else 4)
        if pixels.shape != expected:
            raise CaptureError('DXcam returned unexpected frame dimensions or format')
        if self.settings.capture.repeated_frames:
            # Only explicit artificial-repeat mode needs a retained native-boundary copy.
            self._previous = CaptureSample(pixels.copy(), before, time.monotonic_ns())
            return self._previous
        return CaptureSample(pixels, before, time.monotonic_ns())

    def close(self):
        camera, self.camera = self.camera, None
        self._previous = None
        if camera is not None:
            camera.release()
