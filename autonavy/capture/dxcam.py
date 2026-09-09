"""Pinned DXcam 0.0.5 native owner.

Construct and call only in the capture child.

DXGI output coordinates are DPI-sensitive. Keep the native capture-owner
thread in PER_MONITOR_AWARE_V2 for the whole lifetime of DXcam so that
Windows client coordinates and DXGI DesktopCoordinates use the same desktop
coordinate space.
"""
from __future__ import annotations

import ctypes
import time

from autonavy.capture.base import CaptureError, CaptureSample
from autonavy.windows import WindowsGeometry


_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


def _enter_per_monitor_v2():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    setter = user32.SetThreadDpiAwarenessContext
    setter.argtypes = [ctypes.c_void_p]
    setter.restype = ctypes.c_void_p

    ctypes.set_last_error(0)
    previous = setter(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    if not previous:
        error = ctypes.get_last_error()
        raise CaptureError(
            f"Cannot establish PER_MONITOR_AWARE_V2 for DXcam owner thread "
            f"(WinError={error})"
        )
    return user32, previous


def _restore_dpi_context(user32, previous):
    if user32 is None or previous is None:
        return

    setter = user32.SetThreadDpiAwarenessContext
    setter.argtypes = [ctypes.c_void_p]
    setter.restype = ctypes.c_void_p

    ctypes.set_last_error(0)
    result = setter(previous)
    if not result:
        error = ctypes.get_last_error()
        raise CaptureError(
            f"Cannot restore DXcam owner thread DPI awareness "
            f"(WinError={error})"
        )


class DXcamSource:
    def __init__(self, settings, *, camera_factory=None, geometry_adapter=None):
        self.settings = settings
        self._factory = camera_factory
        self.geometry = geometry_adapter or WindowsGeometry(settings.geometry)
        self.camera = None
        self._previous = None
        self._dpi_api = None
        self._dpi_previous = None

    def _snapshot(self):
        c = self.settings.capture
        snapshot = self.geometry.snapshot((c.width, c.height))
        l, t, r, b = snapshot.client_rect
        if (r - l, b - t) != (c.width, c.height):
            raise CaptureError(
                "Game client size does not match configured capture size: "
                f"client={snapshot.client_rect} "
                f"size={(r - l, b - t)} "
                f"configured={(c.width, c.height)} "
                f"dpi={snapshot.dpi}"
            )
        return snapshot

    def _output_rect(self):
        try:
            rect = self.camera._output.desc.DesktopCoordinates
            return tuple(
                int(getattr(rect, key))
                for key in ("left", "top", "right", "bottom")
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise CaptureError(
                "Cannot establish selected DXcam output desktop coordinates"
            ) from exc

    @staticmethod
    def _region(snapshot, output):
        try:
            return snapshot.output_region(output)
        except ValueError as exc:
            raise CaptureError(
                "Game client is outside selected capture output: "
                f"client={snapshot.client_rect} "
                f"output={output} "
                f"frame_size={snapshot.frame_size} "
                f"dpi={snapshot.dpi} "
                f"geometry_id={snapshot.geometry_id}"
            ) from exc

    def start(self):
        if self.camera is not None:
            return

        self._dpi_api, self._dpi_previous = _enter_per_monitor_v2()

        try:
            self._snapshot()

            factory = self._factory
            if factory is None:
                import dxcam
                factory = dxcam.create

            c = self.settings.capture
            self.camera = factory(
                device_idx=c.device_index,
                output_idx=c.output_index,
                output_color=c.pixel_format,
                max_buffer_len=1,
            )

            snapshot = self._snapshot()
            output = self._output_rect()
            self._region(snapshot, output)
        except BaseException:
            self.close()
            raise

    def read(self):
        if self.camera is None:
            raise CaptureError("DXcam source must be started")

        before = self._snapshot()
        if self._previous is not None and self._previous.geometry != before:
            self._previous = None

        output = self._output_rect()
        region = self._region(before, output)
        pixels = self.camera.grab(region=region)

        after = self._snapshot()
        after_output = self._output_rect()
        if before != after or output != after_output:
            self._previous = None
            return None

        if pixels is None:
            if (
                self.settings.capture.repeated_frames
                and self._previous is not None
                and self._previous.geometry == before
            ):
                return self._previous
            return None

        expected = (
            self.settings.capture.height,
            self.settings.capture.width,
            3 if self.settings.capture.pixel_format == "BGR" else 4,
        )
        if pixels.shape != expected:
            raise CaptureError(
                "DXcam returned unexpected frame dimensions or format: "
                f"actual={getattr(pixels, 'shape', None)} expected={expected} "
                f"region={region} output={output}"
            )

        if self.settings.capture.repeated_frames:
            self._previous = CaptureSample(
                pixels.copy(), before, time.monotonic_ns()
            )
            return self._previous

        return CaptureSample(pixels, before, time.monotonic_ns())

    def close(self):
        camera, self.camera = self.camera, None
        self._previous = None

        release_error = None
        if camera is not None:
            try:
                camera.release()
            except BaseException as exc:
                release_error = exc

        dpi_api, dpi_previous = self._dpi_api, self._dpi_previous
        self._dpi_api = None
        self._dpi_previous = None

        restore_error = None
        if dpi_api is not None and dpi_previous is not None:
            try:
                _restore_dpi_context(dpi_api, dpi_previous)
            except BaseException as exc:
                restore_error = exc

        if release_error is not None:
            raise release_error
        if restore_error is not None:
            raise restore_error
