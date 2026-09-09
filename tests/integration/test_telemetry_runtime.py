"""Actual application consumers and cleanup with offline injected sources only."""
import importlib.util
import threading
import time
from dataclasses import replace

import pytest

from autonavy.app import Application
from autonavy.config import load_settings
from tests.integration.test_replay import run_guarded


def test_telemetry_import_construction_replay_and_config_never_construct_session():
    code = '''
from autonavy.telemetry import TelemetryService
from autonavy.config import TelemetrySettings
service = TelemetryService(TelemetrySettings())
from autonavy.cli import main
assert main(['--check-config']) == 0
assert main(['--dry-run','--capture','replay','--fixture','tests/fixtures/smoke','--max-frames','2']) == 0
'''
    result = run_guarded(code)
    assert result.returncode == 0, result.stderr


def setup_app(monkeypatch, *, fail_capture=False, fail_telemetry=False):
    assert importlib.util.find_spec('autonavy.telemetry'), 'owned telemetry missing'
    from autonavy.telemetry import TelemetryService
    from tests.unit.test_telemetry import FakeSession, PLAYER, until
    session = FakeSession()
    session.objects.put([PLAYER])
    now = [1_000_000_000]
    service = TelemetryService(load_settings().telemetry, session_factory=lambda: session,
                               clock_ns=lambda: now[0], join_timeout_s=.1)
    closed = []
    class Capture:
        def start(self): pass
        def read(self):
            until(lambda: service.snapshot().valid)
            # Application evaluates one real snapshot before deciding on this frame.
            from autonavy.capture.replay import ReplayCapture
            replay = ReplayCapture('tests/fixtures/smoke')
            replay.start()
            try: return replay.read()
            finally: replay.close()
        def close(self):
            closed.append('capture')
            if fail_capture: raise RuntimeError('capture cleanup failed')
    original_close = service.close
    def close():
        closed.append('telemetry')
        session.objects.put([PLAYER])
        original_close()
        if fail_telemetry: raise RuntimeError('telemetry cleanup failed')
    service.close = close
    monkeypatch.setattr('autonavy.capture.factory.create_capture', lambda settings: Capture())
    app = Application(load_settings(overrides={'capture':{'max_frames':1}}), telemetry=service, clock_ns=lambda: now[0])
    return app, service, closed, now


def test_application_owns_live_service_and_consumes_expiring_snapshot(monkeypatch):
    app, service, closed, now = setup_app(monkeypatch)
    assert app.run() == 0
    assert app.last_snapshot.received_at_ns == now[0]
    now[0] += 1_000_000_000
    assert not app.last_snapshot.valid and app.last_snapshot.player is None
    assert closed == ['capture', 'telemetry']


@pytest.mark.parametrize('fail_capture,fail_telemetry', [(True, False), (False, True), (True, True)])
def test_cleanup_attempts_every_resource_and_reports_each_failure(monkeypatch, fail_capture, fail_telemetry):
    app, _, closed, _ = setup_app(monkeypatch, fail_capture=fail_capture, fail_telemetry=fail_telemetry)
    assert app.run() == 3
    assert closed == ['capture', 'telemetry']
    if fail_capture: assert 'capture cleanup failed' in app.last_error
    if fail_telemetry: assert 'telemetry cleanup failed' in app.last_error
    with pytest.raises(RuntimeError): app.close()
    assert closed == ['capture', 'telemetry']


def test_stop_before_start_never_constructs_a_transport(monkeypatch):
    from autonavy.telemetry import TelemetryService
    called = []
    service = TelemetryService(load_settings().telemetry, session_factory=lambda: called.append(True))
    app = Application(load_settings(), telemetry=service)
    app.stop()
    assert app.run() == 0 and called == []
    assert not app.last_snapshot.valid


def test_default_live_selection_and_actual_runtime_stale_recovery(monkeypatch):
    from autonavy.telemetry import TelemetryService
    from autonavy.capture.replay import ReplayCapture
    from tests.unit.test_telemetry import FakeSession, PLAYER, until
    session = FakeSession()
    session.objects.put([PLAYER])
    factories, snapshots = [], []
    now = [1_000_000_000]
    def factory():
        factories.append(True)
        return session
    monkeypatch.setattr('autonavy.telemetry._session_factory', factory)
    replay = ReplayCapture('tests/fixtures/smoke')
    class Capture:
        count = 0
        def start(self):
            assert factories == [], 'transport was constructed before capture startup'
            replay.start()
        def read(self):
            self.count += 1
            if self.count == 1:
                until(lambda: app.telemetry.snapshot().valid)
            else:
                snapshots.append(app.last_snapshot)
                now[0] += 1_000_000_000
                snapshots.append(app.last_snapshot)
                session.objects.put([PLAYER])
                until(lambda: app.telemetry.snapshot().valid)
            return replay.read()
        def close(self):
            session.objects.put([PLAYER])
            replay.close()
    monkeypatch.setattr('autonavy.capture.factory.create_capture', lambda settings: Capture())
    app = Application(load_settings(overrides={'capture':{'max_frames':2}}), clock_ns=lambda: now[0])
    assert isinstance(app.telemetry, TelemetryService) and factories == []
    assert app.run() == 0
    assert snapshots[0].valid and not snapshots[1].valid and snapshots[1].player is None
    assert app.last_snapshot.generation > snapshots[0].generation
    assert factories == [True] and session.closed


def test_stop_at_telemetry_start_boundary_never_constructs_session(monkeypatch):
    from autonavy.telemetry import TelemetryService
    entered, resume = threading.Event(), threading.Event()
    factories = []
    service = TelemetryService(load_settings().telemetry, session_factory=lambda: factories.append(True))
    original_start = service.start
    def start():
        entered.set()
        assert resume.wait(2)
        original_start()
    monkeypatch.setattr(service, 'start', start)
    class Capture:
        def start(self): pass
        def close(self): pass
        def read(self): raise AssertionError('read after cancellation')
    monkeypatch.setattr('autonavy.capture.factory.create_capture', lambda settings: Capture())
    app = Application(load_settings(), telemetry=service)
    results = []
    runner = threading.Thread(target=lambda: results.append(app.run()))
    runner.start()
    try:
        assert entered.wait(2)
        app.stop()
        resume.set()
        runner.join(2)
        assert not runner.is_alive() and results == [0] and factories == []
    finally:
        resume.set()
        app.stop()
        runner.join(3)
