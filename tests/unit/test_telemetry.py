"""Exercise real parsing/polling at a fake, strictly offline HTTP boundary."""
import importlib.util
import io
import json
import queue
import threading
import time
from dataclasses import FrozenInstanceError, replace

import pytest
from PIL import Image

from autonavy.config import TelemetrySettings


META = {'valid': True, 'map_min': [-500, -500], 'map_max': [500, 500], 'grid_steps': [100, 100]}
PLAYER = {'icon': 'Player', 'x': .2, 'y': .3, 'dx': 0, 'dy': -1}
SHIP = {'icon': 'Ship', 'type': 'ground_model', 'color[]': [250, 12, 0], 'x': .5, 'y': .7}


def api():
    assert importlib.util.find_spec('autonavy.telemetry'), 'owned telemetry service is missing'
    from autonavy import telemetry
    return telemetry


def png():
    output = io.BytesIO()
    Image.new('RGB', (2, 2), (23, 77, 255)).save(output, format='PNG')
    return output.getvalue()


class Response:
    def __init__(self, data, status=200):
        self.data = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.status_code = status
        self.closed = False
    def iter_content(self, chunk_size):
        for start in range(0, len(self.data), chunk_size):
            yield self.data[start:start + chunk_size]
    def close(self): self.closed = True


class FakeSession:
    def __init__(self):
        self.objects = queue.Queue()
        self.metadata = META.copy()
        self.image = png()
        self.calls = []
        self.closed = False
        self.entered = threading.Event()
        self.release = threading.Event()
    def get(self, url, **kwargs):
        assert not self.closed
        assert kwargs == {'timeout': (.5, .5), 'stream': True, 'allow_redirects': False}
        self.calls.append((url, threading.get_ident()))
        if url.endswith('map_info.json'):
            value = self.metadata
        elif 'map.img' in url:
            value = self.image
        else:
            self.entered.set()
            value = self.objects.get(timeout=3)
            if callable(value): value = value()
        if isinstance(value, Exception): raise value
        return value if isinstance(value, Response) else Response(value)
    def close(self): self.closed = True


def until(predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        value = predicate()
        if value: return value
        time.sleep(.002)
    raise AssertionError('worker did not publish expected result')


@pytest.fixture
def running():
    instances = []
    def make(objects=None):
        module = api()
        session = FakeSession()
        now = [1_000_000_000]
        session.objects.put([PLAYER, SHIP] if objects is None else objects)
        service = module.TelemetryService(replace(TelemetrySettings(), poll_hz=100, retry_backoff_s=.01),
                                          session_factory=lambda: session, clock_ns=lambda: now[0], join_timeout_s=.3)
        instances.append((service, session))
        service.start()
        until(lambda: service.snapshot().received_at_ns is not None)
        return service, session, now
    yield make
    for service, session in instances:
        service.request_stop()
        session.release.set()
        session.objects.put([PLAYER])
        service.close()


def test_snapshot_is_immutable_and_classifier_requires_documented_ship_color(running):
    objects = [dict(PLAYER), SHIP, dict(SHIP, icon='unknown'), dict(SHIP, **{'color[]': [255, 0, 0]}),
               {'icon': 'capture_zone', 'color[]': [23, 77, 255], 'x': .1, 'y': .1},
               {'icon': 'capture_zone', 'color[]': [255, 255, 255], 'x': .9, 'y': .8}]
    service, _, _ = running(objects)
    snapshot = service.snapshot()
    assert snapshot.valid and snapshot.generation == 1
    assert snapshot.player.position == (.2, .3)
    assert snapshot.enemies[0].position == (.5, .7) and len(snapshot.enemies) == 1
    assert snapshot.zones == ((.9, .8),)
    assert snapshot.metadata.scale == 1000
    objects[0]['x'] = .99
    assert snapshot.player.position == (.2, .3)
    with pytest.raises(FrozenInstanceError): snapshot.player.dx = 2


@pytest.mark.parametrize('bad', [TimeoutError('timeout'), Response([], 503), b'not json', {},
                                    [dict(PLAYER, x=float('nan'))], [dict(PLAYER, dy=float('inf'))],
                                    [dict(PLAYER, x=True)], [dict(PLAYER, x=2)], [PLAYER, PLAYER]])
def test_failed_poll_never_refreshes_success_and_recovery_changes_generation(running, bad):
    service, session, now = running()
    before = service.snapshot()
    now[0] += 100_000_000
    session.objects.put(bad)
    failed = until(lambda: (s := service.snapshot()).error and s)
    assert failed.received_at_ns == before.received_at_ns
    assert not failed.valid and failed.player is None and failed.enemies == () and failed.zones == ()
    now[0] += 100_000_000
    session.objects.put([dict(PLAYER), SHIP])
    recovered = until(lambda: (s := service.snapshot()).valid and s)
    assert recovered.received_at_ns == now[0] and recovered.generation > before.generation


def test_missing_player_clears_old_player_with_empty_zones(running):
    service, session, now = running()
    now[0] += 1
    session.objects.put([SHIP])
    missing = until(lambda: (s := service.snapshot()).received_at_ns == now[0] and s)
    assert not missing.valid and missing.player is None and missing.enemies == () and missing.zones == ()


def test_consumption_expiry_and_stale_recovery_invalidate_retained_snapshot(running):
    service, session, now = running()
    retained = service.snapshot()
    now[0] += 1_000_000_000
    stale = service.snapshot()
    assert not stale.valid and stale.player is None and stale.received_at_ns == retained.received_at_ns
    assert not retained.at(now[0]).valid
    session.objects.put([dict(PLAYER), SHIP])
    recovered = until(lambda: (s := service.snapshot()).valid and s)
    assert recovered.generation > retained.generation


@pytest.mark.parametrize('metadata', [dict(META, valid=False), dict(META, valid=1),
                                      dict(META, map_min=[0]), dict(META, grid_steps=[0, 1]),
                                      dict(META, map_max=[float('inf'), 10])])
def test_invalid_metadata_cannot_authorize_objects(running, metadata):
    service, session, now = running()
    now[0] += 31_000_000_000
    session.metadata = metadata
    session.objects.put([dict(PLAYER)])
    until(lambda: len([c for c in session.calls if c[0].endswith('map_info.json')]) >= 2)
    assert not service.snapshot().valid and service.snapshot().metadata is None


def test_metadata_image_cache_is_bounded_separate_and_map_change_invalidates(running):
    service, session, now = running()
    image = until(service.map_image)
    before = service.snapshot()
    now[0] += 100_000_000
    session.objects.put([dict(PLAYER)])
    until(lambda: service.snapshot().received_at_ns == now[0])
    assert len([c for c in session.calls if 'map_info' in c[0]]) == 1
    assert service.map_image() == image and image.received_at_ns < service.snapshot().received_at_ns
    session.metadata = dict(META, map_max=[1000, 1000])
    session.image = b'broken image'
    now[0] += 31_000_000_000
    session.objects.put([dict(PLAYER)])
    changed = until(lambda: (s := service.snapshot()).valid and s.metadata.scale == 1500 and s)
    assert changed.generation > before.generation and service.map_image() is None
    assert image.data == png()


def test_stream_limit_rejects_oversized_body_and_closes_response(running):
    service, session, _ = running()
    response = Response(b' ' * (api().MAX_JSON_BYTES + 1))
    session.objects.put(response)
    failed = until(lambda: (s := service.snapshot()).error and s)
    assert not failed.valid and response.closed


def test_stop_is_signal_only_join_is_bounded_and_late_result_is_not_published(running):
    service, session, now = running()
    before = service.snapshot()
    def hang():
        session.release.wait(3)
        return [dict(PLAYER)]
    session.objects.put(hang)
    until(lambda: len([c for c in session.calls if 'map_obj' in c[0]]) >= 2)
    now[0] += 1
    start = time.monotonic()
    service.request_stop()
    assert time.monotonic() - start < .1
    with pytest.raises(RuntimeError, match='telemetry.*join|Telemetry.*join'):
        service.close()
    assert time.monotonic() - start < .7 and not session.closed
    session.release.set()
    until(lambda: session.closed)
    service.close()
    assert not service.snapshot().valid and service.snapshot().received_at_ns == before.received_at_ns
    assert len({thread for _, thread in session.calls}) == 1


def test_backoff_is_stop_aware_and_fault_reporting_is_rate_limited(caplog):
    module = api()
    session = FakeSession()
    for _ in range(10): session.objects.put(TimeoutError('timeout'))
    service = module.TelemetryService(replace(TelemetrySettings(), retry_backoff_s=.01, max_backoff_s=.02),
                                      session_factory=lambda: session)
    service.start()
    until(lambda: len([c for c in session.calls if 'map_obj' in c[0]]) >= 4)
    start = time.monotonic()
    service.close()
    assert time.monotonic() - start < .3 and session.closed
    assert len([r for r in caplog.records if r.name == 'autonavy.telemetry']) <= 2


def test_legacy_facades_consume_snapshot_without_io(running, monkeypatch):
    service, _, now = running()
    from info import info
    from toolkit.map import get_point, download_map
    facade = info(service)
    facade.update()
    assert facade.connected and facade.player['pos'] == [.2, .3]
    assert facade.enemy[0]['dis'] == pytest.approx(500)
    assert get_point(source=service, onlyplayer=True) == ([.2, .3], 0)
    assert download_map(source=service) == until(service.map_image).data
    now[0] += 1_000_000_000
    facade.update()
    assert not facade.connected and facade.player is None and facade.enemy == []
    assert get_point(source=service, onlyplayer=True) == ([], None)


def test_slow_success_after_ttl_gap_changes_generation_even_if_poll_started_fresh(running):
    service, session, now = running()
    before = service.snapshot()
    entered, resume = threading.Event(), threading.Event()
    def delayed():
        entered.set()
        assert resume.wait(2)
        return [dict(PLAYER)]
    session.objects.put(delayed)
    assert entered.wait(2)
    now[0] += 2_000_000_000
    resume.set()
    recovered = until(lambda: (s := service.snapshot()).valid and s.received_at_ns == now[0] and s)
    assert recovered.generation > before.generation


def test_finite_metadata_endpoints_cannot_overflow_derived_scale(running):
    service, session, now = running()
    now[0] += 31_000_000_000
    session.metadata = dict(META, map_min=[-1e308, 0], map_max=[1e308, 100])
    session.objects.put([dict(PLAYER)])
    until(lambda: service.snapshot().received_at_ns == now[0])
    assert not service.snapshot().valid and service.snapshot().metadata is None


def test_stop_during_session_factory_closes_without_http_and_cannot_restart():
    module = api()
    session = FakeSession()
    entered, resume = threading.Event(), threading.Event()
    factories = []
    def factory():
        factories.append(True)
        entered.set()
        assert resume.wait(2)
        return session
    service = module.TelemetryService(TelemetrySettings(), session_factory=factory, join_timeout_s=.05)
    service.start()
    assert entered.wait(2)
    try:
        service.request_stop()
        with pytest.raises(RuntimeError, match='join'): service.close()
        with pytest.raises(RuntimeError, match='closed'): service.start()
    finally:
        resume.set()
        until(lambda: session.closed)
        service.close()
    assert session.calls == [] and factories == [True] and not service.snapshot().valid


def test_session_cleanup_failure_remains_visible_on_repeated_close():
    module = api()
    session = FakeSession()
    session.objects.put([dict(PLAYER)])
    def fail_close():
        raise RuntimeError('transport close failed')
    session.close = fail_close
    service = module.TelemetryService(TelemetrySettings(), session_factory=lambda: session)
    service.start()
    until(lambda: service.snapshot().valid)
    service.request_stop()
    session.objects.put([dict(PLAYER)])
    for _ in range(2):
        with pytest.raises(RuntimeError, match='transport close failed'): service.close()


def test_repeated_start_owns_one_transport_and_prestart_stop_constructs_none():
    module = api()
    session = FakeSession()
    session.objects.put([dict(PLAYER)])
    factories = []
    def factory():
        factories.append(threading.get_ident())
        return session
    service = module.TelemetryService(TelemetrySettings(), session_factory=factory)
    service.start()
    service.start()
    until(lambda: service.snapshot().valid)
    service.request_stop()
    session.objects.put([dict(PLAYER)])
    service.close()
    assert len(factories) == 1 and factories[0] != threading.get_ident()
    never_started = module.TelemetryService(TelemetrySettings(), session_factory=factory)
    never_started.request_stop()
    never_started.start()
    never_started.close()
    assert len(factories) == 1


def test_zero_player_direction_is_unavailable(running):
    service, session, _ = running()
    session.objects.put([dict(PLAYER, dx=0, dy=0)])
    failed = until(lambda: (s := service.snapshot()).error and s)
    assert not failed.valid


def test_truncated_image_is_not_cached_after_header_verification(running):
    service, session, now = running()
    encoded = io.BytesIO()
    Image.new('RGB', (32, 32)).save(encoded, format='JPEG')
    session.image = encoded.getvalue()[:-10]
    now[0] += 31_000_000_000
    session.objects.put([dict(PLAYER)])
    # The next object poll proves the serial image refresh has finished decoding.
    until(lambda: len([c for c in session.calls if 'map_obj' in c[0]]) >= 3)
    assert service.map_image() is None
