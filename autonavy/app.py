"""Explicit startup and cooperative cleanup for the migrated application."""
from __future__ import annotations

import logging
import threading

from autonavy.config import Settings, validate_settings
from autonavy.models import FramePacket, RuntimeState

LOG = logging.getLogger(__name__)


class Application:
    def __init__(self, settings: Settings):
        self.settings = validate_settings(settings)
        self.state = RuntimeState.STOPPED
        self.frames_processed = 0
        self.last_frame: FramePacket | None = None
        self.last_observations = None
        self.vision = None
        self.last_error: str | None = None
        self.capture = None
        self.stop_event = threading.Event()
        self._closed = False
        self._closing = False
        self._close_complete = threading.Event()
        self._close_error: str | None = None
        self._capture_lifecycle = threading.Lock()

    def _transition(self, state: RuntimeState) -> None:
        LOG.info('state=%s previous=%s', state.value, self.state.value)
        self.state = state

    def run(self) -> int:
        if self._closed or self.state is not RuntimeState.STOPPED:
            LOG.error('Application is already running or closed; construct a new Application')
            return 3
        failed = False
        result = 0
        if self.stop_event.is_set():
            self.close()
            return 0
        self._transition(RuntimeState.STARTING)
        try:
            from autonavy.capture.factory import create_capture
            from autonavy.capture.base import CaptureError, CaptureTimeout
            from autonavy.vision.detectors import VisionPipeline
            # Decode and validate every selected template before any live capture resource.
            self.vision = VisionPipeline(self.settings)
            capture = create_capture(self.settings)
            with self._capture_lifecycle:
                self.capture = capture
                cancelled = self._closed or self.stop_event.is_set()
            if cancelled:
                capture.close()
            else:
                try:
                    capture.start()
                except CaptureError:
                    if not self.stop_event.is_set():
                        raise
            if not self.stop_event.is_set():
                self._transition(RuntimeState.WAITING)
            while not self.stop_event.is_set():
                try:
                    packet = self.capture.read()
                except CaptureTimeout:
                    continue  # Healthy static/no-new-frame source; still check stop on every wait.
                if packet is None or self.stop_event.is_set():
                    break
                if packet.geometry is not None and (self.last_frame is None or self.last_frame.geometry_id != packet.geometry_id):
                    LOG.info('capture_geometry=%s', packet.geometry.diagnostic())
                self.last_frame = packet
                self.last_observations = self.vision.observe(packet)
                self.frames_processed += 1
                if self.settings.capture.max_frames is not None and self.frames_processed >= self.settings.capture.max_frames:
                    break
        except KeyboardInterrupt:
            LOG.info('Application stopped by user')
        except Exception as exc:
            LOG.exception('Application failed')
            self.last_error = str(exc)
            failed = True
            result = 3
        finally:
            self._transition(RuntimeState.STOPPING)
            try:
                self.close()
            except Exception as exc:
                LOG.exception('Application cleanup failed')
                self.last_error = str(exc)
                failed = True
                result = 3
            self._transition(RuntimeState.ERROR if failed else RuntimeState.STOPPED)
        return result

    def stop(self) -> None:
        self.stop_event.set()
        with self._capture_lifecycle:
            capture = self.capture
        if capture is not None and hasattr(capture, 'request_stop'):
            capture.request_stop()

    def close(self) -> None:
        self.stop()
        with self._capture_lifecycle:
            owner = not self._closing and not self._closed
            if owner:
                self._closing = True
                capture = self.capture
        failure = None
        if owner:
            try:
                if capture is not None:
                    capture.close()
            except BaseException as exc:
                failure = exc
            finally:
                with self._capture_lifecycle:
                    self._close_error = f'{type(failure).__name__}: {failure}' if failure is not None else None
                    self._closed = True
                    self._closing = False
                    self._close_complete.set()
        else:
            # The resource owner has its own bounded cleanup. Concurrent callers
            # allow that budget plus the runtime join allowance, then fail explicitly.
            budget = self.settings.capture.stop_timeout_s + self.settings.runtime.join_timeout_s
            if not self._close_complete.wait(budget):
                raise RuntimeError('Application cleanup did not complete within the concurrent wait budget')
        with self._capture_lifecycle:
            error = self._close_error
        if failure is not None and not isinstance(failure, Exception):
            raise failure
        if error is not None:
            raise RuntimeError(error) from failure
