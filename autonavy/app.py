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
        self.last_error: str | None = None
        self.capture = None
        self.stop_event = threading.Event()
        self._closed = False

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
            from autonavy.capture.base import CaptureTimeout
            self.capture = create_capture(self.settings)
            self.capture.start()
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
        if self.capture is not None and hasattr(self.capture, 'request_stop'):
            self.capture.request_stop()

    def close(self) -> None:
        self.stop()
        if self._closed:
            return
        try:
            if self.capture is not None:
                self.capture.close()
        finally:
            self._closed = True
