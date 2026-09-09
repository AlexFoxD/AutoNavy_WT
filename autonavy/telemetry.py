"""Serial telemetry with immutable snapshots and consumption-time expiry.

Requests tuple timeouts bound connect/read inactivity, not total wall time.
Cancellation cannot interrupt arbitrary socket calls; a bounded join reports this.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import io
import json
import logging
import math
import threading
import time
from autonavy.config import TelemetrySettings

LOG = logging.getLogger(__name__)
MAX_JSON_BYTES = 1_048_576
MAX_IMAGE_BYTES = 8_388_608
MAX_IMAGE_PIXELS = 16_777_216


@dataclass(frozen=True)
class Player:
    position: tuple[float, float]
    dx: float
    dy: float


@dataclass(frozen=True)
class Enemy:
    position: tuple[float, float]


@dataclass(frozen=True)
class MapMetadata:
    map_min: tuple[float, float]
    map_max: tuple[float, float]
    grid_steps: tuple[float, float]
    received_at_ns: int

    @property
    def key(self):
        return self.map_min, self.map_max, self.grid_steps

    @property
    def scale(self):
        return self.map_max[0] - self.map_min[0]


@dataclass(frozen=True)
class MapImage:
    data: bytes
    key: tuple
    generation: int
    received_at_ns: int


@dataclass(frozen=True)
class TelemetrySnapshot:
    generation: int = 0
    player: Player | None = None
    enemies: tuple[Enemy, ...] = ()
    zones: tuple[tuple[float, float], ...] = ()
    metadata: MapMetadata | None = None
    received_at_ns: int | None = None
    valid: bool = False
    error: str | None = None
    object_ttl_ns: int = 1_000_000_000
    metadata_ttl_ns: int = 30_000_000_000

    def at(self, now_ns: int) -> TelemetrySnapshot:
        """Recheck this retained value immediately before making a decision."""
        metadata = self.metadata
        if metadata is not None and not 0 <= now_ns - metadata.received_at_ns < self.metadata_ttl_ns:
            metadata = None
        fresh = self.received_at_ns is not None and 0 <= now_ns - self.received_at_ns < self.object_ttl_ns
        if not self.valid or not fresh or metadata is None:
            return replace(self, valid=False, player=None, enemies=(), zones=(), metadata=metadata,
                           error=self.error or ('stale objects' if not fresh else 'metadata unavailable'))
        return self


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Expected a finite numeric telemetry value')
    return float(value)


def _pair(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('Expected a two-element telemetry vector')
    return tuple(_number(v) for v in value)


def _position(obj):
    point = _pair((obj['x'], obj['y']))
    if not all(0 <= value <= 1 for value in point):
        raise ValueError('Object position is outside normalized map bounds')
    return point


def _color(obj):
    value = obj.get('color[]')
    if not isinstance(value, list) or len(value) != 3 or not all(type(v) is int and 0 <= v <= 255 for v in value):
        raise ValueError('Expected an RGB telemetry color')
    return tuple(value)


def _metadata(data, received_at_ns):
    if not isinstance(data, dict) or data.get('valid') is not True:
        raise ValueError('Map metadata is not valid')
    result = MapMetadata(_pair(data['map_min']), _pair(data['map_max']), _pair(data['grid_steps']), received_at_ns)
    if any(b <= a or not math.isfinite(b - a) for a, b in zip(result.map_min, result.map_max)) or any(v <= 0 for v in result.grid_steps):
        raise ValueError('Map dimensions and grid steps must be positive')
    return result


def _objects(data):
    if not isinstance(data, list) or len(data) > 10_000:
        raise ValueError('Expected a bounded map object list')
    player = None
    enemies, zones = [], []
    for obj in data:
        if not isinstance(obj, dict):
            raise ValueError('Expected a map object')
        icon = obj.get('icon')
        if icon == 'Player':
            if player is not None:
                raise ValueError('Ambiguous duplicate Player objects')
            player = Player(_position(obj), _number(obj['dx']), _number(obj['dy']))
            if player.dx == 0 and player.dy == 0:
                raise ValueError('Player direction is unavailable')
        elif icon == 'Ship':
            # Hue alone is ambiguous; preserve the two documented hostile Ship colors.
            if _color(obj) in ((250, 12, 0), (240, 12, 0)):
                enemies.append(Enemy(_position(obj)))
        elif icon == 'capture_zone':
            if _color(obj) != (23, 77, 255):
                zones.append(_position(obj))
    return player, tuple(enemies), tuple(zones)


def _session_factory():
    import requests
    session = requests.Session()
    session.trust_env = False
    return session


class OfflineTelemetry:
    """Inert replay source; construction/start never import Requests."""
    def start(self): pass
    def request_stop(self): pass
    def close(self): pass
    def snapshot(self): return TelemetrySnapshot(error='offline telemetry')
    def map_image(self): return None


class TelemetryService:
    def __init__(self, settings: TelemetrySettings, *, session_factory=None, clock_ns=time.monotonic_ns,
                 join_timeout_s=2.0, fault_interval_s=5.0):
        self.settings = settings
        self._factory = session_factory or _session_factory
        self._clock = clock_ns
        self._join_timeout = join_timeout_s
        self._fault_interval_ns = int(fault_interval_s * 1e9)
        self._last_fault_ns = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._closed = False
        self._close_error = None
        self._snapshot = TelemetrySnapshot(object_ttl_ns=int(settings.object_ttl_s * 1e9),
                                           metadata_ttl_ns=int(settings.metadata_ttl_s * 1e9))
        self._metadata = None
        self._image = None
        self._next_metadata_ns = 0
        self._next_image_ns = 0
        self._recovery = False

    def start(self):
        with self._lock:
            if self._closed:
                raise RuntimeError('Telemetry service is closed')
            if self._stop.is_set() or self._thread is not None:
                return
            self._thread = threading.Thread(target=self._run, name='telemetry', daemon=True)
            self._thread.start()

    def request_stop(self):
        self._stop.set()

    def close(self):
        self.request_stop()
        with self._lock:
            self._closed = True
            thread = self._thread
        if thread is not None:
            thread.join(self._join_timeout)
            if thread.is_alive():
                raise RuntimeError('Telemetry worker exceeded its bounded join allowance')
        if self._close_error is not None:
            raise RuntimeError(self._close_error)

    def snapshot(self):
        with self._lock:
            value = self._snapshot
        if self._stop.is_set():
            value = replace(value, valid=False, error='telemetry stopped')
        return value.at(self._clock())

    def map_image(self):
        with self._lock:
            image, metadata, generation = self._image, self._metadata, self._snapshot.generation
        now = self._clock()
        ttl = int(self.settings.metadata_ttl_s * 1e9)
        if self._stop.is_set() or metadata is None or image is None:
            return None
        if image.generation != generation or image.key != metadata.key:
            return None
        if not (0 <= now - image.received_at_ns < ttl and 0 <= now - metadata.received_at_ns < ttl):
            return None
        return image

    def _read(self, session, path, limit):
        if self._stop.is_set():
            raise RuntimeError('telemetry stopped')
        response = session.get(self.settings.base_url.rstrip('/') + path,
                               timeout=(self.settings.connect_timeout_s, self.settings.read_timeout_s),
                               stream=True, allow_redirects=False)
        try:
            if not 200 <= response.status_code < 300:
                raise ValueError(f'HTTP status {response.status_code}')
            data = bytearray()
            for chunk in response.iter_content(chunk_size=65_536):
                if self._stop.is_set():
                    raise RuntimeError('telemetry stopped')
                if len(data) + len(chunk) > limit:
                    raise ValueError('Telemetry response exceeds byte limit')
                data.extend(chunk)
            return bytes(data)
        finally:
            response.close()

    def _json(self, session, path):
        return json.loads(self._read(session, path, MAX_JSON_BYTES))

    def _fault(self, component, exc):
        now = self._clock()
        if self._last_fault_ns is None or now - self._last_fault_ns >= self._fault_interval_ns:
            from autonavy.diagnostics import exception_text
            LOG.warning('Telemetry %s failed: %s', component, exception_text(exc).decode('utf-8', errors='replace'))
            self._last_fault_ns = now

    def _poll(self, session):
        now = self._clock()
        old = self._snapshot
        stale = old.received_at_ns is not None and now - old.received_at_ns >= old.object_ttl_ns
        if stale or self._recovery:
            self._next_metadata_ns = 0
        metadata_error = None
        if now >= self._next_metadata_ns:
            try:
                data = self._json(session, '/map_info.json')
                metadata = _metadata(data, self._clock())
                with self._lock:
                    changed = self._metadata is None or self._metadata.key != metadata.key
                    self._metadata = metadata
                    if changed:
                        self._image = None
                        self._next_image_ns = 0
                        self._snapshot = replace(self._snapshot, generation=self._snapshot.generation + 1,
                                                 valid=False, player=None, enemies=(), zones=(), metadata=metadata)
                self._next_metadata_ns = metadata.received_at_ns + old.metadata_ttl_ns
            except Exception as exc:
                metadata_error = f'metadata: {type(exc).__name__}: {str(exc)[:240]}'
                with self._lock:
                    self._metadata = None
                    self._image = None
                    self._snapshot = replace(self._snapshot, valid=False, player=None,
                                             enemies=(), zones=(), metadata=None, error=metadata_error)
                self._next_metadata_ns = 0
                self._fault('metadata', exc)
        try:
            data = self._json(session, '/map_obj.json')
            player, enemies, zones = _objects(data)
            received = self._clock()
            # A request can cross the TTL even if it began while the old sample was fresh.
            stale = stale or (old.received_at_ns is not None and received - old.received_at_ns >= old.object_ttl_ns)
            if stale:
                self._next_metadata_ns = 0
            with self._lock:
                if self._stop.is_set():
                    return False
                generation = self._snapshot.generation
                if (self._recovery or stale) and generation == old.generation:
                    generation += 1
                    self._image = None
                    self._next_image_ns = 0
                self._snapshot = TelemetrySnapshot(generation, player, enemies, zones, self._metadata, received,
                    player is not None and self._metadata is not None,
                    metadata_error or (None if player is not None else 'Player unavailable'),
                    old.object_ttl_ns, old.metadata_ttl_ns)
                self._recovery = player is None or self._metadata is None
        except Exception as exc:
            if not self._stop.is_set():
                with self._lock:
                    self._snapshot = replace(self._snapshot, valid=False, player=None, enemies=(), zones=(),
                        metadata=self._metadata, error=f'objects: {type(exc).__name__}: {str(exc)[:240]}')
                    self._image = None
                self._recovery = True
                self._fault('objects', exc)
            return False
        if self._metadata is not None and self._clock() >= self._next_image_ns and not self._stop.is_set():
            self._refresh_image(session)
        return self._snapshot.valid

    def _refresh_image(self, session):
        self._next_image_ns = self._clock() + int(self.settings.metadata_ttl_s * 1e9)
        try:
            from PIL import Image
            data = self._read(session, '/map.img?gen=2', MAX_IMAGE_BYTES)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {'PNG', 'JPEG'} or image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError('Map image format or dimensions exceed limits')
                image.verify()
            # verify() only checks headers for JPEG; decode within the dimension cap.
            with Image.open(io.BytesIO(data)) as image:
                image.load()
            with self._lock:
                if not self._stop.is_set():
                    self._image = MapImage(data, self._metadata.key, self._snapshot.generation, self._clock())
        except Exception as exc:
            self._fault('map image', exc)

    def _run(self):
        session = None
        backoff = self.settings.retry_backoff_s
        try:
            if self._stop.is_set():
                return
            session = self._factory()
            while not self._stop.is_set():
                started = time.monotonic()
                success = self._poll(session)
                delay = max(0, 1 / self.settings.poll_hz - (time.monotonic() - started)) if success else backoff
                backoff = self.settings.retry_backoff_s if success else min(backoff * 2, self.settings.max_backoff_s)
                if self._stop.wait(delay):
                    break
        except Exception as exc:
            with self._lock:
                self._snapshot = replace(self._snapshot, valid=False, error=f'worker: {type(exc).__name__}: {str(exc)[:240]}')
            self._fault('worker', exc)
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception as exc:
                    self._close_error = f'Telemetry Session cleanup failed: {type(exc).__name__}: {exc}'
