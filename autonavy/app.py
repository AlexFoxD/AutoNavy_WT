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
            if self.settings.capture.backend != 'replay':
                raise RuntimeError(f'{self.settings.capture.backend} capture is unavailable at this milestone; use --dry-run --capture replay --fixture tests/fixtures/smoke')
            from autonavy.capture.replay import ReplayCapture
            self.capture = ReplayCapture(self.settings.capture.fixture, max_frames=self.settings.capture.max_frames)
            self.capture.start()
            self._transition(RuntimeState.WAITING)
            while not self.stop_event.is_set():
                packet = self.capture.read()
                if packet is None or self.stop_event.is_set():
                    break
                self.last_frame = packet
                self.frames_processed += 1
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

    def close(self) -> None:
        self.stop()
        if self._closed:
            return
        try:
            if self.capture is not None:
                self.capture.close()
        finally:
            self._closed = True
