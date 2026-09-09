"""Explicit startup and cooperative cleanup for the migrated application."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import replace

from autonavy.config import Settings, validate_settings
from autonavy.models import FramePacket, RuntimeState
from autonavy.telemetry import OfflineTelemetry, TelemetryService, TelemetrySnapshot

LOG = logging.getLogger(__name__)


class Application:
    def __init__(self, settings: Settings, *, telemetry=None, clock_ns=time.monotonic_ns,
                 input_backend=None, window_guard=None, vision=None, navigation=None, rng=None, wait=None):
        self.settings = validate_settings(settings)
        self._clock_ns = clock_ns
        self.telemetry = telemetry if telemetry is not None else (
            OfflineTelemetry() if self.settings.capture.backend == 'replay' else
            TelemetryService(self.settings.telemetry, clock_ns=clock_ns,
                             join_timeout_s=self.settings.runtime.join_timeout_s,
                             fault_interval_s=self.settings.diagnostics.fault_interval_s))
        self._last_snapshot = TelemetrySnapshot()
        self.state = RuntimeState.STOPPED
        self.frames_processed = 0
        self.last_frame: FramePacket | None = None
        self.last_observations = None
        self.vision = vision
        self.last_error: str | None = None
        self.capture = None
        self.stop_event = threading.Event()
        self._wait = self.stop_event.wait if wait is None else wait
        self._closed = False
        self._closing = False
        self._close_complete = threading.Event()
        self._close_error: str | None = None
        self._capture_lifecycle = threading.Lock()
        from autonavy.input.controller import InputController, RecordingBackend
        from autonavy.input.windows import WindowsBackend, LiveWindowGuard
        from autonavy.behavior import BattlePolicy
        backend = input_backend if input_backend is not None else (
            WindowsBackend(self.settings.input) if self.settings.input.enable_input else RecordingBackend())
        self.window_guard = window_guard if window_guard is not None else LiveWindowGuard(self.settings)
        self.input = InputController(backend, guard=self._input_guard, clock_ns=clock_ns,
                                     max_pending=self.settings.input.max_pending)
        self.policy = BattlePolicy(self, navigation=navigation, rng=rng)
        self.pause_event = threading.Event()
        self.hotkeys = None
        self._stop_errors = []

    def _input_guard(self, intent):
        if self.stop_event.is_set() or self.input.emergency.is_set() or self.pause_event.is_set(): return False
        p = self.last_frame; obs = self.last_observations
        if p is None or obs is None or obs.packet is not p or not obs.recognition_supported or p.geometry is None: return False
        g = p.geometry; configured = self.settings.geometry
        age = self._clock_ns()-p.received_at_ns
        if not (0 <= age < self.settings.runtime.frame_ttl_s*1e9): return False
        if not (g.recognition_supported and g.profile_id == configured.profile_id
                and g.profile_size == (configured.width,configured.height) and g.ui_scale == configured.ui_scale): return False
        if intent.geometry_id != p.geometry_id or intent.source_generation != p.source_generation: return False
        source_generation = getattr(self.capture, 'source_generation', p.source_generation)
        if source_generation != p.source_generation: return False
        if self.input.backend.physical:
            if not self.settings.input.enable_input or self.settings.capture.backend == 'replay': return False
            if not self.window_guard(p): return False
        if intent.requires_telemetry or intent.owner != 'ui':
            current = self.telemetry.snapshot().at(self._clock_ns())
            if not current.valid or current.generation != intent.telemetry_generation: return False
        age=self._clock_ns()-p.received_at_ns
        return (not self.stop_event.is_set() and not self.input.emergency.is_set() and not self.pause_event.is_set()
                and self.last_frame is p and 0 <= age < self.settings.runtime.frame_ttl_s*1e9
                and getattr(self.capture,'source_generation',p.source_generation)==p.source_generation)

    def pause(self):
        """Signal-only callback; the runtime owns pause transitions and releases."""
        self.pause_event.set()

    def emergency_stop(self):
        """Signal-only hotkey callback, including during startup or a capture wait."""
        self.input.emergency.set()
        self.stop_event.set()

    def tick(self, packet=None):
        """One actual decision tick, also used when capture has no new publication."""
        self._last_snapshot = self.telemetry.snapshot()
        if packet is not None and not self.stop_event.is_set():
            if packet.geometry is not None and (self.last_frame is None or self.last_frame.geometry_id != packet.geometry_id):
                LOG.info('capture_geometry=%s', packet.geometry.diagnostic())
            self.last_frame = packet
            self.last_observations = self.vision.observe(packet, selection=self.policy.detectors)
            self.frames_processed += 1
        self._last_snapshot = self.telemetry.snapshot()
        self.input.tick()
        if self.stop_event.is_set():
            self.input.release_all()
            self.policy._reset()
            return
        self._consume_pause()
        self.policy.tick(packet is not None)
        self.input.tick()
        # A signal raised inside a late dispatch guard also releases existing holds
        # before this tick returns. Callbacks themselves remain signal-only.
        self._consume_pause()

    def _consume_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.policy.toggle_pause()

    @property
    def last_snapshot(self):
        snapshot = self._last_snapshot
        if self.stop_event.is_set():
            snapshot = replace(snapshot, valid=False, error='application stopped')
        return snapshot.at(self._clock_ns())

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
            self.vision = self.vision if self.vision is not None else VisionPipeline(self.settings)
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
                try:
                    self.telemetry.start()
                except Exception:
                    if not self.stop_event.is_set():
                        raise
            if not self.stop_event.is_set():
                if self.input.backend.physical and not self.settings.input.enable_input:
                    raise RuntimeError('Physical input requires explicit opt-in')
                self.input.start()
                if self.input.backend.physical and not self.stop_event.is_set():
                    from autonavy.input.windows import Hotkeys
                    hooks = Hotkeys(self.settings.input, self.emergency_stop, self.pause)
                    with self._capture_lifecycle:
                        self.hotkeys = hooks
                        cancelled = self._closed or self.stop_event.is_set()
                    if cancelled: hooks.close()
                    else: hooks.start()
                self.policy._state(RuntimeState.WAITING, 'hangar', self.settings.runtime.menu_timeout_s)
            period_ns=int(1e9/self.settings.runtime.tick_hz)
            next_tick=self._clock_ns()
            while not self.stop_event.is_set():
                remaining=(next_tick-self._clock_ns())/1e9
                if remaining>0: self._wait(remaining)
                if self.stop_event.is_set(): break
                self._last_snapshot = self.telemetry.snapshot()
                try:
                    packet = self.capture.read(timeout=1/self.settings.runtime.tick_hz)
                except CaptureTimeout:
                    self.tick()
                    # A bounded capture wait already supplied the decision interval.
                    next_tick=self._clock_ns()
                    continue
                if packet is None or self.stop_event.is_set():
                    break
                self.tick(packet)
                # Schedule from completion: a delayed decision never creates a burst.
                next_tick=self._clock_ns()+period_ns
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
        self.input.emergency.set()
        with self._capture_lifecycle:
            capture = self.capture
        for resource in (capture,self.telemetry,self.policy.navigation):
            if resource is not None and hasattr(resource,'request_stop'):
                try: resource.request_stop()
                except Exception as exc: self._stop_errors.append(exc)

    def close(self) -> None:
        self.stop()
        with self._capture_lifecycle:
            owner = not self._closing and not self._closed
            if owner:
                self._closing = True
                capture = self.capture
        failure = None
        failures = []
        if owner:
            try:
                # Input release is always first, before any service join or native wait.
                failures.extend(self._stop_errors)
                for resource in (self.input, self.hotkeys, capture, self.telemetry, self.policy):
                    if resource is not None and hasattr(resource,'close'):
                        try:
                            resource.close()
                        except BaseException as exc:
                            failures.append(exc)
                failure = next((exc for exc in failures if not isinstance(exc, Exception)),
                               failures[0] if failures else None)
            finally:
                with self._capture_lifecycle:
                    self._close_error = '; '.join(f'{type(exc).__name__}: {exc}' for exc in failures) or None
                    self._closed = True
                    self._closing = False
                    self._close_complete.set()
        else:
            # The resource owner has its own bounded cleanup. Concurrent callers
            # allow that budget plus the runtime join allowance, then fail explicitly.
            budget = self.settings.capture.stop_timeout_s + 3 * self.settings.runtime.join_timeout_s + .25
            if not self._close_complete.wait(budget):
                raise RuntimeError('Application cleanup did not complete within the concurrent wait budget')
        with self._capture_lifecycle:
            error = self._close_error
        if failure is not None and not isinstance(failure, Exception):
            raise failure
        if error is not None:
            raise RuntimeError(error) from failure
