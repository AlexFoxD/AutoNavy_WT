"""Real spawn/transport/lifecycle tests; native acquisition is always fake."""
import importlib.util
import multiprocessing
import threading
import time
from dataclasses import replace

import numpy as np
import pytest


class SyntheticSource:
    def __init__(self, settings):
        assert multiprocessing.parent_process() is not None, 'Native source must be constructed only in child'
        self.mode = settings.capture.device_index
        self.settings = settings
        self.index = 0
        self.image = np.zeros((720, 1280, 3), np.uint8)
    def start(self):
        if self.mode == 2: raise RuntimeError('synthetic startup failed')
        if self.mode == 5:
            while True: time.sleep(0.1)
    def read(self):
        if self.mode == 1:
            while True: time.sleep(0.1)
        if self.mode == 3: raise RuntimeError('synthetic read failed')
        if self.mode == 4: return None
        from autonavy.geometry import GeometrySnapshot
        self.index += 1
        self.image[:] = self.index % 255
        geometry = GeometrySnapshot((-1500 + self.index, 100, -220 + self.index, 820), (1280, 720), (0, 0, 1280, 720))
        from autonavy.capture.base import CaptureSample
        return CaptureSample(self.image, geometry, time.monotonic_ns())
    def close(self):
        if self.mode == 6: raise RuntimeError('synthetic cleanup failed')


def make_capture(mode=0, **changes):
    assert importlib.util.find_spec('autonavy.capture.process'), 'supervised capture is missing'
    from autonavy.capture.process import ProcessCapture
    from autonavy.config import Settings
    settings = Settings()
    capture = replace(settings.capture, device_index=mode, fps=120, startup_timeout_s=4.0, frame_timeout_s=0.5, stop_timeout_s=0.6, **changes)
    return ProcessCapture(replace(settings, capture=capture), source_factory=SyntheticSource)


def test_latest_transport_owns_retained_pixels_and_restart_invalidates_generation():
    capture = make_capture()
    capture.start()
    process = capture.process
    capture.start()
    assert capture.process is process and capture.source_generation == 1
    try:
        first = capture.read()
        retained = first.image.copy()
        time.sleep(0.12)
        latest = capture.read()
        assert latest.publication_id > first.publication_id + 1
        assert latest.geometry.client_rect[0] == -1500 + latest.publication_id
        assert latest.geometry_id == latest.geometry.geometry_id
        np.testing.assert_array_equal(first.image, retained)
        assert capture.latest.read() is latest
        capture.stop()
        assert not process.is_alive()
        capture.start()
        restarted = capture.read()
        assert restarted.source_generation > latest.source_generation
    finally:
        capture.close()
    assert not capture.process.is_alive()


@pytest.mark.parametrize('mode, fragment', [(2, 'startup failed'), (3, 'read failed'), (4, 'frame')])
def test_native_failures_and_no_frame_are_bounded_and_reclaimed(mode, fragment):
    capture = make_capture(mode)
    started = time.monotonic()
    try:
        with pytest.raises(RuntimeError, match=fragment):
            capture.start()
            capture.read()
    finally:
        capture.close()
    assert time.monotonic() - started < 7
    assert not capture.process.is_alive()


def test_hung_native_read_stop_wakes_consumer_and_reclaims_child():
    capture = make_capture(1)
    capture.start()
    result = []
    reader = threading.Thread(target=lambda: result.append(capture.read()))
    reader.start()
    started = time.monotonic()
    capture.stop()
    reader.join(1)
    assert result == [None] and not reader.is_alive()
    assert not capture.process.is_alive()
    assert time.monotonic() - started < 1.6
    capture.close()


def hold_lock(lock, ready):
    lock.acquire()
    ready.set()
    while True: time.sleep(0.1)


def test_dead_writer_lock_cannot_block_read_or_cleanup():
    capture = make_capture()
    capture.start()
    ctx = multiprocessing.get_context('spawn')
    ready = ctx.Event()
    holder = ctx.Process(target=hold_lock, args=(capture._session.shared.lock, ready))
    holder.start()
    try:
        assert ready.wait(4)
        holder.terminate()
        holder.join(2)
        with pytest.raises(RuntimeError, match='frame'):
            capture.read()
    finally:
        if holder.is_alive(): holder.terminate()
        holder.join(2)
        capture.close()
    assert not capture.process.is_alive()


def test_application_uses_selected_factory_and_stop_signals_before_close(monkeypatch):
    capture = make_capture(1)
    from autonavy.app import Application
    from autonavy.capture import factory
    monkeypatch.setattr(factory, 'create_capture', lambda settings: capture)
    app = Application(capture.settings)
    results = []
    runner = threading.Thread(target=lambda: results.append(app.run()))
    runner.start()
    deadline = time.monotonic() + 5
    while not capture.started and runner.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    app.stop()
    runner.join(2)
    assert results == [0] and not runner.is_alive()
    assert app.capture is capture and capture.closed
    assert not capture.process.is_alive()


def test_short_poll_times_out_without_stopping_healthy_no_frame_source():
    from autonavy.capture.base import CaptureTimeout
    capture = make_capture(4)
    capture.start()
    try:
        now = time.monotonic()
        with pytest.raises(CaptureTimeout): capture.read(timeout=0.02)
        assert time.monotonic()-now < 0.2
        assert capture.started and capture.process.is_alive()
    finally:
        capture.close()


def test_startup_hang_is_reclaimed_at_configured_deadline():
    capture = make_capture(5)
    capture.settings = replace(capture.settings, capture=replace(capture.settings.capture, startup_timeout_s=0.4))
    with pytest.raises(RuntimeError, match='startup deadline'):
        capture.start()
    assert not capture.process.is_alive()
    capture.close()


def test_cleanup_failure_is_reported_after_process_reclamation_and_close_is_idempotent():
    capture = make_capture(6)
    capture.start()
    capture.read()
    with pytest.raises(RuntimeError, match='cleanup failed'):
        capture.close()
    assert not capture.process.is_alive()
    capture.close()


def test_application_does_not_treat_healthy_no_frame_as_disconnect(monkeypatch):
    capture = make_capture(4)
    from autonavy.app import Application
    from autonavy.capture import factory
    monkeypatch.setattr(factory, 'create_capture', lambda settings: capture)
    app = Application(capture.settings)
    results = []
    runner = threading.Thread(target=lambda: results.append(app.run()))
    runner.start()
    deadline = time.monotonic()+5
    while not capture.started and runner.is_alive() and time.monotonic() < deadline: time.sleep(0.01)
    time.sleep(0.65)
    assert runner.is_alive() and app.last_error is None
    app.stop()
    runner.join(2)
    assert results == [0]


def test_application_emits_geometry_calibration_for_actual_packet(monkeypatch, caplog):
    capture = make_capture(max_frames=1)
    from autonavy.app import Application
    from autonavy.capture import factory
    monkeypatch.setattr(factory, 'create_capture', lambda settings: capture)
    app = Application(capture.settings)
    with caplog.at_level('INFO', logger='autonavy.app'):
        assert app.run() == 0
    assert app.frames_processed == 1
    records = [record for record in caplog.records if record.msg == 'capture_geometry=%s']
    assert len(records) == 1
    assert records[0].args['client_rect'] == app.last_frame.geometry.client_rect
    assert records[0].args['proposed_center'] == (app.last_frame.geometry.client_rect[0]+640, 460)


@pytest.mark.parametrize('restart', [False, True])
def test_inflight_old_read_cannot_publish_after_close_or_restart(monkeypatch, restart):
    capture = make_capture()
    from autonavy.capture import process as module
    original = module.FramePacket
    entered, resume = threading.Event(), threading.Event()
    def delayed_packet(*args, **kwargs):
        entered.set()
        assert resume.wait(4)
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'FramePacket', delayed_packet)
    capture.start()
    results, errors = [], []
    def read():
        try: results.append(capture.read())
        except Exception as exc: errors.append(exc)
    reader = threading.Thread(target=read)
    reader.start()
    try:
        assert entered.wait(3)
        if restart:
            capture.stop()
            capture.start()
        else:
            capture.close()
        resume.set()
        reader.join(2)
        assert errors == [] and results == [None]
        if restart:
            assert capture.read().source_generation == 2
    finally:
        resume.set()
        reader.join(2)
        capture.close()


def test_read_snapshot_is_one_generation_even_when_paused_at_first_attribute(monkeypatch):
    capture = make_capture()
    capture.start()
    entered, resume = threading.Event(), threading.Event()
    original = type(capture).__getattribute__
    paused = False
    def delayed_snapshot(self, name):
        nonlocal paused
        value = original(self, name)
        if self is capture and threading.current_thread().name == 'early-reader' and name in {'_shared', '_session'} and not paused:
            paused = True
            entered.set()
            assert resume.wait(5)
        return value
    monkeypatch.setattr(type(capture), '__getattribute__', delayed_snapshot)
    results, errors = [], []
    def read():
        try: results.append(capture.read())
        except Exception as exc: errors.append(exc)
    reader = threading.Thread(target=read, name='early-reader')
    reader.start()
    try:
        assert entered.wait(3)
        capture.stop()
        capture.start()
        resume.set()
        reader.join(2)
        assert errors == [] and results == [None]
        assert capture.read().source_generation == 2
    finally:
        resume.set()
        reader.join(2)
        capture.close()


@pytest.mark.parametrize('boundary', ['factory', 'start'])
@pytest.mark.parametrize('action', ['stop', 'close'])
def test_application_stop_during_capture_installation_never_launches_native_owner(monkeypatch, boundary, action):
    capture = make_capture(5)
    capture.settings = replace(capture.settings, capture=replace(capture.settings.capture, startup_timeout_s=0.3))
    from autonavy.app import Application
    from autonavy.capture import factory
    entered, resume = threading.Event(), threading.Event()
    def create(settings):
        if boundary == 'factory':
            entered.set()
            assert resume.wait(4)
        return capture
    monkeypatch.setattr(factory, 'create_capture', create)
    if boundary == 'start':
        original_start = capture.start
        def delayed_start():
            entered.set()
            assert resume.wait(4)
            return original_start()
        monkeypatch.setattr(capture, 'start', delayed_start)
    app = Application(capture.settings)
    results = []
    runner = threading.Thread(target=lambda: results.append(app.run()))
    runner.start()
    try:
        assert entered.wait(3)
        stopped = time.monotonic()
        getattr(app, action)()
        assert time.monotonic()-stopped < 0.2
        resume.set()
        runner.join(2)
        assert results == [0] and app.last_error is None
        assert capture.process is None and capture.closed
    finally:
        resume.set()
        runner.join(3)
        capture.close()


def test_close_keeps_restart_excluded_until_terminal_state_is_installed(monkeypatch):
    capture = make_capture()
    capture.start()
    first_process = capture.process
    entered, resume = threading.Event(), threading.Event()
    original_stop = capture.stop
    def delayed_stop():
        original_stop()
        entered.set()
        assert resume.wait(4)
    monkeypatch.setattr(capture, 'stop', delayed_stop)
    closing = threading.Thread(target=capture.close)
    errors = []
    def start():
        try: capture.start()
        except Exception as exc: errors.append(exc)
    starting = threading.Thread(target=start)
    closing.start()
    try:
        assert entered.wait(3)
        starting.start()
        time.sleep(0.05)
        resume.set()
        closing.join(2)
        starting.join(2)
        assert len(errors) == 1 and 'closed' in str(errors[0])
        assert capture.process is first_process and not first_process.is_alive()
    finally:
        resume.set()
        closing.join(2)
        if starting.ident is not None: starting.join(3)
        if capture.process is not None and capture.process.is_alive():
            capture.process.terminate()
            capture.process.join(2)


def test_stop_during_native_startup_wakes_application_before_ready_deadline(monkeypatch):
    capture = make_capture(5)
    from autonavy.app import Application
    from autonavy.capture import factory
    monkeypatch.setattr(factory, 'create_capture', lambda settings: capture)
    app = Application(capture.settings)
    results = []
    runner = threading.Thread(target=lambda: results.append(app.run()))
    runner.start()
    try:
        deadline = time.monotonic()+3
        while (capture.process is None or capture.process.pid is None) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert capture.process is not None and capture.process.pid is not None
        now = time.monotonic()
        app.stop()
        assert time.monotonic()-now < 0.2
        runner.join(2)
        assert results == [0] and app.last_error is None
        assert time.monotonic()-now < 2
        assert not capture.process.is_alive()
    finally:
        app.stop()
        runner.join(3)
        capture.close()


def test_stop_during_session_allocation_latches_before_native_launch(monkeypatch):
    capture = make_capture()
    from autonavy.capture import process as module
    original_shared = module._Shared
    entered, resume = threading.Event(), threading.Event()
    def delayed_shared(*args):
        entered.set()
        assert resume.wait(4)
        return original_shared(*args)
    monkeypatch.setattr(module, '_Shared', delayed_shared)
    errors = []
    def start():
        try: capture.start()
        except Exception as exc: errors.append(exc)
    runner = threading.Thread(target=start)
    runner.start()
    try:
        assert entered.wait(3)
        now = time.monotonic()
        capture.request_stop()
        assert time.monotonic()-now < 0.2
        resume.set()
        runner.join(2)
        assert errors == [] and not runner.is_alive()
        assert capture.process.pid is None
    finally:
        resume.set()
        runner.join(2)
        capture.close()


def test_cancel_between_read_preconditions_returns_cancellation(monkeypatch):
    capture = make_capture()
    from autonavy.capture import process as module
    capture.start()
    entered, resume = threading.Event(), threading.Event()
    original = module._Progress.__getattribute__
    def delayed_ready(self, name):
        if name == 'started' and threading.current_thread().name == 'ready-reader':
            entered.set()
            assert resume.wait(4)
        return original(self, name)
    monkeypatch.setattr(module._Progress, '__getattribute__', delayed_ready)
    results, errors = [], []
    def read():
        try: results.append(capture.read())
        except Exception as exc: errors.append(exc)
    reader = threading.Thread(target=read, name='ready-reader')
    reader.start()
    try:
        assert entered.wait(3)
        capture.stop()
        resume.set()
        reader.join(2)
        assert errors == [] and results == [None]
    finally:
        resume.set()
        reader.join(2)
        capture.close()


class GatedCleanupCapture:
    """A device-free resource whose one cleanup can be observed before completion."""
    def __init__(self, failure=False):
        self.failure = failure
        self.read_entered = threading.Event()
        self.read_resume = threading.Event()
        self.cleanup_entered = threading.Event()
        self.cleanup_resume = threading.Event()
        self.close_calls = 0
    def start(self): pass
    def request_stop(self): pass
    def read(self):
        self.read_entered.set()
        assert self.read_resume.wait(4)
        return None
    def close(self):
        self.close_calls += 1
        self.cleanup_entered.set()
        assert self.cleanup_resume.wait(4)
        if self.failure:
            raise RuntimeError('synthetic gated cleanup failure')


@pytest.mark.parametrize('failure', [False, True])
def test_run_finally_waits_for_external_cleanup_and_shares_its_result(monkeypatch, failure):
    from autonavy.app import Application
    from autonavy.capture import factory
    from autonavy.config import Settings
    from autonavy.models import RuntimeState
    capture = GatedCleanupCapture(failure)
    monkeypatch.setattr(factory, 'create_capture', lambda settings: capture)
    app = Application(Settings())
    original_close = app.close
    follower_entered, run_done = threading.Event(), threading.Event()
    def observed_close():
        if threading.current_thread().name == 'app-runner':
            follower_entered.set()
        return original_close()
    monkeypatch.setattr(app, 'close', observed_close)
    results, errors = [], []
    def run():
        results.append(app.run())
        run_done.set()
    def external_close():
        try: app.close()
        except Exception as exc: errors.append(exc)
    runner = threading.Thread(target=run, name='app-runner')
    closer = threading.Thread(target=external_close)
    runner.start()
    try:
        assert capture.read_entered.wait(2)
        closer.start()
        assert capture.cleanup_entered.wait(2)
        capture.read_resume.set()
        assert follower_entered.wait(2)
        assert not run_done.wait(0.05), 'Application returned while resource cleanup was still in progress'
        assert app.state is RuntimeState.STOPPING
        capture.cleanup_resume.set()
        runner.join(2)
        closer.join(2)
        assert not runner.is_alive() and not closer.is_alive()
        assert capture.close_calls == 1
        if failure:
            assert results == [3] and app.state is RuntimeState.ERROR
            assert 'synthetic gated cleanup failure' in app.last_error
            assert len(errors) == 1 and 'synthetic gated cleanup failure' in str(errors[0])
            with pytest.raises(RuntimeError, match='synthetic gated cleanup failure'):
                app.close()
        else:
            assert results == [0] and errors == [] and app.last_error is None
            assert app.state is RuntimeState.STOPPED
            app.close()
    finally:
        capture.read_resume.set()
        capture.cleanup_resume.set()
        runner.join(3)
        if closer.ident is not None: closer.join(3)


def test_concurrent_close_wait_budget_cannot_become_an_unbounded_wait():
    from autonavy.app import Application
    from autonavy.config import Settings
    settings = Settings()
    settings = replace(settings, capture=replace(settings.capture, stop_timeout_s=0.05),
                       runtime=replace(settings.runtime, join_timeout_s=0.05))
    app = Application(settings)
    capture = GatedCleanupCapture()
    app.capture = capture
    errors = []
    def external_close():
        try: app.close()
        except Exception as exc: errors.append(exc)
    closer = threading.Thread(target=external_close)
    closer.start()
    try:
        assert capture.cleanup_entered.wait(2)
        started = time.monotonic()
        with pytest.raises(RuntimeError, match='cleanup.*budget'):
            app.close()
        assert time.monotonic()-started < 0.5
    finally:
        capture.cleanup_resume.set()
        closer.join(2)
    assert errors == [] and capture.close_calls == 1
