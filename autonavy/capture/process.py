"""Supervise one native owner with bounded shared memory, waits, and reclamation.

The Windows x64 child alone constructs/reads/releases the camera. It publishes
one fixed frame under a timed lock. Independent aligned control words avoid
depending on a mutex the terminated child may own. No frame FIFO or feeder thread.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from copy import deepcopy
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
        if shared.stop.value:
            return
        source = source_factory(settings)
        if shared.stop.value:
            return
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
                                           geometry=asdict(sample.geometry), diagnostic=sample.diagnostic)).encode('utf-8')
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
        _write_error(shared, exc, context=f'backend={settings.capture.backend} device={settings.capture.device_index} output={settings.capture.output_index}')
    finally:
        if source is not None:
            try:
                source.close()
            except BaseException as exc:
                _write_error(shared, exc, cleanup=True, context=f'backend={settings.capture.backend} device={settings.capture.device_index} cleanup')


def _write_error(shared, exc, *, cleanup=False, context=''):
    # A single child writes bounded error bytes, then publishes length last.
    from autonavy.diagnostics import exception_text
    encoded = exception_text(exc, context=context)
    size = shared.cleanup_size if cleanup else shared.error_size
    destination = shared.cleanup_text if cleanup else shared.error_text
    if not size.value:
        destination[:len(encoded)] = encoded
        size.value = len(encoded)


@dataclass
class _Progress:
    # Readiness is historical within a generation; cancellation is a separate one-way signal.
    started: bool = False
    publication_id: int = 0
    diagnostic: dict | None = None
    delivered: int = 0
    publication_gaps: int = 0
    idle_reads: int = 0
    failures: int = 0


@dataclass(frozen=True)
class _Session:
    """One atomic lifecycle reference; its transport identity never changes."""
    shared: _Shared | None
    process: object
    cancel: threading.Event
    latest: LatestFrameSlot
    generation: int
    settings: object
    progress: _Progress


class ProcessCapture:
    def __init__(self, settings, *, source_factory=None):
        if source_factory is None:
            from autonavy.capture.dxcam import DXcamSource
            source_factory = DXcamSource
        self.settings = settings
        self._factory = source_factory
        self._context = multiprocessing.get_context('spawn')
        self._stop_requested = threading.Event()
        self._idle_latest = LatestFrameSlot()
        self._session = None
        self.closed = False
        self._closing = False
        self._generation = 0
        self._lifecycle = threading.RLock()

    @property
    def process(self):
        session = self._session
        return session.process if session is not None else None

    @property
    def latest(self):
        session = self._session
        return session.latest if session is not None else self._idle_latest

    @property
    def started(self):
        session = self._session
        return session is not None and session.progress.started and not session.cancel.is_set()

    @property
    def source_generation(self):
        session = self._session
        return session.generation if session is not None else 0

    @property
    def publication_id(self):
        session = self._session
        return session.progress.publication_id if session is not None else 0

    @property
    def diagnostic(self):
        session = self._session
        return deepcopy(session.progress.diagnostic) if session is not None else None

    @property
    def statistics(self):
        with self._lifecycle:
            progress = self._session.progress if self._session is not None else _Progress()
            return {name: getattr(progress, name) for name in
                    ('delivered', 'publication_gaps', 'idle_reads', 'failures')}

    @staticmethod
    def _error(shared):
        size = shared.error_size.value
        return bytes(shared.error_text[:size]).decode('utf-8', errors='replace') if size else None

    def start(self) -> None:
        with self._lifecycle:
            if self.closed or self._closing:
                raise CaptureError('Capture is closed; construct a new source')
            # A signal received before launch stays latched until explicit stop/close.
            if self._stop_requested.is_set():
                return
            previous = self._session
            if previous is not None and previous.process.is_alive():
                if previous.progress.started and not previous.cancel.is_set():
                    return
                raise CaptureError('Previous capture process has not stopped or is still starting')
            c = self.settings.capture
            shared = _Shared(self._context, c.width*c.height*(3 if c.pixel_format == 'BGR' else 4))
            process = self._context.Process(target=_native_owner, args=(self.settings, self._factory, shared), name='AutoNavy-capture')
            self._generation += 1
            session = _Session(shared, process, threading.Event(), LatestFrameSlot(), self._generation, self.settings, _Progress())
            self._session = session
            if self._stop_requested.is_set():
                self._signal(session)
                return
            process.start()
        deadline = time.monotonic() + c.startup_timeout_s
        try:
            while not session.cancel.is_set():
                error = self._error(shared)
                if error:
                    raise CaptureError(error)
                if shared.ready.value:
                    with self._lifecycle:
                        if self._session is session and not session.cancel.is_set():
                            session.progress.started = True
                        return
                if not process.is_alive():
                    raise CaptureError('Capture process exited during startup')
                if time.monotonic() >= deadline:
                    raise CaptureTimeout('Capture startup deadline exceeded')
                session.cancel.wait(min(0.01, max(0, deadline-time.monotonic())))
        except BaseException:
            session.progress.failures += 1
            self._signal(session)
            # Only reclaim this attempt; a late failure cannot stop a newer generation.
            with self._lifecycle:
                self._reclaim(session)
            raise

    def read(self, timeout: float | None = None) -> FramePacket | None:
        session = self._session
        try:
            return self._read(session, timeout)
        except CaptureTimeout:
            if session is not None: session.progress.idle_reads += 1
            raise
        except CaptureError:
            if session is not None: session.progress.failures += 1
            raise

    def _read(self, session, timeout: float | None = None) -> FramePacket | None:
        """Wait for a newer publication; healthy no-frame raises CaptureTimeout.

        Runtime tick consumers can pass a short timeout, or zero for a poll.
        Only one runtime reader drains transport; consumers share latest packets.
        """
        if session is None:
            if self._stop_requested.is_set():
                return None
            raise CaptureError('Capture must be started before reading')
        if session.cancel.is_set():
            return None
        if not session.progress.started:
            raise CaptureError('Capture must be started before reading')
        shared, process, cancel, latest = session.shared, session.process, session.cancel, session.latest
        generation, after = session.generation, session.progress.publication_id
        c = session.settings.capture
        timeout = c.frame_timeout_s if timeout is None else timeout
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
                        pixels = np.frombuffer(shared.pixels, dtype=np.uint8).reshape(c.height, c.width, 3 if c.pixel_format == 'BGR' else 4)
                        geometry = GeometrySnapshot(**metadata['geometry'])
                        packet = FramePacket(pixels, c.pixel_format, metadata['publication_id'], generation,
                                             metadata['received_at_ns'], geometry.geometry_id, geometry=geometry)
                        if cancel.is_set():
                            return None
                        if self._lifecycle.acquire(blocking=False):
                            try:
                                if cancel.is_set() or self._session is not session:
                                    return None
                                try:
                                    latest.publish(packet)
                                except RuntimeError:
                                    if cancel.is_set():
                                        return None
                                    raise
                                session.progress.delivered += 1
                                session.progress.publication_gaps += max(0, packet.publication_id-after-1)
                                session.progress.publication_id = packet.publication_id
                                session.progress.diagnostic = metadata.get('diagnostic')
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
        self._stop_requested.set()
        session = self._session
        if session is not None:
            self._signal(session)
        else:
            self._idle_latest.close()

    @staticmethod
    def _signal(session):
        session.cancel.set()
        if session.shared is not None:
            session.shared.stop.value = 1
        session.latest.close()

    @staticmethod
    def _reclaim(session):
        process = session.process
        if process.pid is not None:
            budget = session.settings.capture.stop_timeout_s
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

    def stop(self) -> None:
        self.request_stop()
        with self._lifecycle:
            session = self._session
            if session is not None:
                self._signal(session)
                self._reclaim(session)
            if not self.closed and not self._closing:
                self._stop_requested.clear()  # Explicit completed stop permits a fresh start.

    def close(self) -> None:
        self.request_stop()
        error = None
        with self._lifecycle:
            if self.closed:
                return
            # Keep start excluded through stop and the terminal-state publication.
            self._closing = True
            self.stop()
            session = self._session
            if session is not None and session.shared is not None:
                shared = session.shared
                if shared.cleanup_size.value:
                    error = bytes(shared.cleanup_text[:shared.cleanup_size.value]).decode('utf-8', errors='replace')
                self._session = replace(session, shared=None)
            self.closed = True
        if error:
            raise CaptureError(error)
