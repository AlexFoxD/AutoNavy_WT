"""Supervise one native owner with bounded shared memory, waits, and reclamation.

The Windows x64 child alone constructs/reads/releases the camera. It publishes
one fixed frame under a timed lock. Independent aligned control words avoid
depending on a mutex the terminated child may own. No frame FIFO or feeder thread.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import math
import multiprocessing
import threading
import time

from autonavy.capture.base import CaptureError, CaptureTimeout
from autonavy.capture.latest import LatestFrameSlot
from autonavy.geometry import GeometrySnapshot
from autonavy.models import FramePacket


class _Shared:
    def __init__(self, context, size):
        self.pixels = context.RawArray('B', size)
        self.metadata = context.RawArray('B', 8192)
        self.metadata_size = context.RawValue('i', 0)
        self.error_text = context.RawArray('B', 4096)
        self.error_size = context.RawValue('i', 0)
        self.cleanup_text = context.RawArray('B', 4096)
        self.cleanup_size = context.RawValue('i', 0)
        self.stop = context.RawValue('i', 0)
        self.ready = context.RawValue('i', 0)
        self.lock = context.Lock()


def _native_owner(settings, source_factory, shared):
    import numpy as np
    source = None
    try:
        source = source_factory(settings)
        source.start()
        shared.ready.value = 1
        count = 0
        c = settings.capture
        expected = (c.height, c.width, 3 if c.pixel_format == 'BGR' else 4)
        destination = np.frombuffer(shared.pixels, dtype=np.uint8).reshape(expected)
        while not shared.stop.value:
            tick = time.monotonic()
            sample = source.read()
            if shared.stop.value:
                break
            if sample is not None:
                if sample.image.dtype != np.uint8 or sample.image.shape != expected or sample.geometry.frame_size != (c.width, c.height):
                    raise CaptureError('Native source returned incompatible frame geometry or format')
                count += 1
                metadata = json.dumps(dict(publication_id=count, received_at_ns=sample.received_at_ns,
                                           geometry=asdict(sample.geometry))).encode('utf-8')
                if len(metadata) > len(shared.metadata):
                    raise CaptureError('Capture geometry metadata exceeds transport limit')
                if shared.lock.acquire(timeout=min(0.05, c.stop_timeout_s)):
                    try:
                        destination[:] = sample.image
                        shared.metadata[:len(metadata)] = metadata
                        shared.metadata_size.value = len(metadata)
                    finally:
                        shared.lock.release()
            # Managed grab cadence; no DXcam recording worker or fabricated receive time.
            deadline = tick + 1/c.fps
            while not shared.stop.value:
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 0.01))
    except BaseException as exc:
        _write_error(shared, exc)
    finally:
        if source is not None:
            try:
                source.close()
            except BaseException as exc:
                _write_error(shared, exc, cleanup=True)


def _write_error(shared, exc, *, cleanup=False):
    # A single child writes bounded error bytes, then publishes length last.
    encoded = f'{type(exc).__name__}: {exc}'.encode('utf-8', errors='replace')[:4096]
    size = shared.cleanup_size if cleanup else shared.error_size
    destination = shared.cleanup_text if cleanup else shared.error_text
    if not size.value:
        destination[:len(encoded)] = encoded
        size.value = len(encoded)


class ProcessCapture:
    def __init__(self, settings, *, source_factory=None):
        if source_factory is None:
            from autonavy.capture.dxcam import DXcamSource
            source_factory = DXcamSource
        self.settings = settings
        self._factory = source_factory
        self._context = multiprocessing.get_context('spawn')
        self._cancel = threading.Event()
        self.latest = LatestFrameSlot()
        self._shared = None
        self.process = None
        self.started = False
        self.closed = False
        self.source_generation = 0
        self.publication_id = 0
        self._lifecycle = threading.Lock()

    @staticmethod
    def _error(shared):
        size = shared.error_size.value
        return bytes(shared.error_text[:size]).decode('utf-8', errors='replace') if size else None

    def start(self) -> None:
        with self._lifecycle:
            if self.closed:
                raise CaptureError('Capture is closed; construct a new source')
            if self.started:
                return
            if self.process is not None and self.process.is_alive():
                raise CaptureError('Previous capture process has not stopped')
            c = self.settings.capture
            self._cancel = threading.Event()
            self.latest = LatestFrameSlot()
            self._shared = _Shared(self._context, c.width*c.height*(3 if c.pixel_format == 'BGR' else 4))
            self.source_generation += 1
            self.publication_id = 0
            self.process = self._context.Process(target=_native_owner, args=(self.settings, self._factory, self._shared), name='AutoNavy-capture')
            self.process.start()
            shared, process, cancel = self._shared, self.process, self._cancel
        deadline = time.monotonic() + c.startup_timeout_s
        try:
            while not cancel.is_set():
                error = self._error(shared)
                if error:
                    raise CaptureError(error)
                if shared.ready.value:
                    with self._lifecycle:
                        if not cancel.is_set():
                            self.started = True
                        return
                if not process.is_alive():
                    raise CaptureError('Capture process exited during startup')
                if time.monotonic() >= deadline:
                    raise CaptureTimeout('Capture startup deadline exceeded')
                cancel.wait(min(0.01, max(0, deadline-time.monotonic())))
        except BaseException:
            self.stop()
            raise

    def read(self, timeout: float | None = None) -> FramePacket | None:
        """Wait for a newer publication; healthy no-frame raises CaptureTimeout.

        Runtime tick consumers can pass a short timeout, or zero for a poll.
        Only one runtime reader drains transport; consumers share latest packets.
        """
        shared, process, cancel, latest = self._shared, self.process, self._cancel, self.latest
        generation, after = self.source_generation, self.publication_id
        if cancel.is_set():
            return None
        if not self.started or self.closed:
            raise CaptureError('Capture must be started before reading')
        timeout = self.settings.capture.frame_timeout_s if timeout is None else timeout
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError('Capture read timeout must be finite and nonnegative')
        import numpy as np
        deadline = time.monotonic() + timeout
        while not cancel.is_set():
            error = self._error(shared)
            if error:
                raise CaptureError(error)
            if not process.is_alive():
                raise CaptureError('Capture process exited unexpectedly')
            if shared.lock.acquire(timeout=min(0.01, max(0, deadline-time.monotonic()))):
                try:
                    size = shared.metadata_size.value
                    metadata = json.loads(bytes(shared.metadata[:size])) if size else None
                    if metadata and metadata['publication_id'] > after:
                        c = self.settings.capture
                        pixels = np.frombuffer(shared.pixels, dtype=np.uint8).reshape(c.height, c.width, 3 if c.pixel_format == 'BGR' else 4)
                        geometry = GeometrySnapshot(**metadata['geometry'])
                        packet = FramePacket(pixels, c.pixel_format, metadata['publication_id'], generation,
                                             metadata['received_at_ns'], geometry.geometry_id, geometry=geometry)
                        if cancel.is_set():
                            return None
                        if self._lifecycle.acquire(blocking=False):
                            try:
                                if cancel.is_set():
                                    return None
                                try:
                                    latest.publish(packet)
                                except RuntimeError:
                                    if cancel.is_set():
                                        return None
                                    raise
                                self.publication_id = packet.publication_id
                                return packet
                            finally:
                                self._lifecycle.release()
                finally:
                    shared.lock.release()
            if time.monotonic() >= deadline:
                raise CaptureTimeout('No new capture frame within caller wait budget')
            cancel.wait(min(0.01, max(0, deadline-time.monotonic())))
        return None

    def request_stop(self) -> None:
        """Wake parent waits and signal native owner without waiting for cleanup."""
        self._cancel.set()
        if self._shared is not None:
            self._shared.stop.value = 1
        self.latest.close()

    def stop(self) -> None:
        self.request_stop()
        with self._lifecycle:
            process = self.process
            if process is not None and process.pid is not None:
                budget = self.settings.capture.stop_timeout_s
                deadline = time.monotonic() + budget
                process.join(budget/2)
                if process.is_alive():
                    process.terminate()
                    process.join(max(0, (deadline-time.monotonic())/2))
                if process.is_alive():
                    process.kill()
                    process.join(max(0, deadline-time.monotonic()))
                if process.is_alive():
                    raise CaptureError('Capture process did not exit within shutdown budget')
            self.started = False

    def close(self) -> None:
        if self.closed:
            return
        self.stop()
        self.closed = True
        error = None
        if self._shared is not None and self._shared.cleanup_size.value:
            size = self._shared.cleanup_size.value
            error = bytes(self._shared.cleanup_text[:size]).decode('utf-8', errors='replace')
        self._shared = None
        if error:
            raise CaptureError(error)
