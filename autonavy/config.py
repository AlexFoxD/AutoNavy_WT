"""Validated v2 settings. Relative resource paths use the distribution root."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
import math
from pathlib import Path
import sys
import tomllib
from typing import Mapping, get_args, get_origin, get_type_hints
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Settings are invalid; resources have not been opened."""


def resource_root() -> Path:
    if getattr(sys, 'frozen', False) or '__compiled__' in globals():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CaptureSettings:
    backend: str = 'dxcam'
    device_index: int = 0
    output_index: int = 0
    pixel_format: str = 'BGR'
    fps: int = 60
    repeated_frames: bool = False
    obs_api: str = 'auto'
    width: int = 1280
    height: int = 720
    read_failure_limit: int = 3
    startup_timeout_s: float = 10.0
    stop_timeout_s: float = 2.0
    frame_timeout_s: float = 1.0
    fixture: Path | None = None
    max_frames: int | None = None


@dataclass(frozen=True)
class GeometrySettings:
    window_class: str = 'DagorWClass'
    window_title: str = ''
    profile_id: str = 'legacy-1280x720'
    width: int = 1280
    height: int = 720
    ui_scale: float = 1.0
    obs_content_rect: tuple[int, int, int, int] = (0, 0, 1280, 720)


@dataclass(frozen=True)
class VisionSettings:
    fire_roi: tuple[int, int, int, int] = (370, 200, 910, 510)
    heading_roi: tuple[int, int, int, int] = (85, 545, 145, 615)
    ammo_roi: tuple[int, int, int, int] = (480, 660, 520, 690)
    fire_hsv_lower: tuple[int, int, int] = (33, 109, 149)
    fire_hsv_upper: tuple[int, int, int] = (137, 255, 255)
    heading_hsv_lower: tuple[int, int, int] = (35, 43, 46)
    heading_hsv_upper: tuple[int, int, int] = (77, 255, 255)
    canny_low: int = 100
    canny_high: int = 200
    canny_input: str = 'color'
    morphology_size: int = 1
    template_threshold: float = 0.8
    start_threshold: float = 0.9
    confirm_threshold: float = 0.95
    join_threshold: float = 0.9
    aim_threshold: float = 0.3
    collision_threshold: float = 0.2
    research_threshold: float = 0.7
    preprocess_version: int = 1


@dataclass(frozen=True)
class TelemetrySettings:
    base_url: str = 'http://127.0.0.1:8111'
    poll_hz: float = 10.0
    connect_timeout_s: float = 0.5
    read_timeout_s: float = 0.5
    object_ttl_s: float = 1.0
    metadata_ttl_s: float = 30.0
    retry_backoff_s: float = 0.5
    max_backoff_s: float = 5.0


@dataclass(frozen=True)
class InputSettings:
    enable_input: bool = False
    emergency_stop_key: str = 'f8'
    pause_key: str = 'f9'
    require_focus: bool = True
    vjoy_device_id: int = 1
    vjoy_neutral: int = 16384
    max_pending: int = 64
    intent_ttl_s: float = 0.25
    press_duration_s: float = 0.05
    click_duration_s: float = 0.1
    throttle_interval_s: float = 0.1


@dataclass(frozen=True)
class ControlSettings:
    aim_kp: float = 0.6
    aim_ki: float = 0.0
    aim_kd: float = 0.02
    aim_limit_px: float = 30.0
    heading_kp: float = 0.5
    heading_ki: float = 0.1
    heading_kd: float = 0.1
    heading_limit: float = 100.0
    search_kp: float = 0.6
    search_ki: float = 0.0
    search_kd: float = 0.02
    search_limit: float = 30.0
    integral_limit: float = 100.0
    max_dt_s: float = 1.0
    arrival_distance: float = 0.01
    lookahead_distance: float = 0.02
    replan_deviation: float = 0.1
    replan_attempts: int = 3
    replan_backoff_s: float = 1.0
    plan_timeout_s: float = 10.0


@dataclass(frozen=True)
class RuntimeSettings:
    tick_hz: float = 30.0
    frame_ttl_s: float = 0.5
    join_timeout_s: float = 2.0
    menu_timeout_s: float = 120.0
    queue_timeout_s: float = 540.0
    spawn_delay_s: float = 20.0
    player_timeout_s: float = 30.0
    battle_settle_s: float = 15.0
    recovery_reverse_s: float = 60.0
    recovery_settle_s: float = 3.0
    recovery_turn_s: float = 5.0
    recovery_forward_s: float = 10.0


@dataclass(frozen=True)
class DiagnosticsSettings:
    preview: bool = False
    preview_fps: float = 5.0
    log_level: str = 'INFO'
    log_max_bytes: int = 2_000_000
    log_backups: int = 3
    fault_interval_s: float = 5.0
    per_frame: bool = False


@dataclass(frozen=True)
class PathSettings:
    templates: Path = Path('src/game_image')
    aim_template: Path = Path('src/cir.png')
    route: Path = Path('path.json')
    logs: Path = Path('logs/v2')
    cache: Path = Path('logs/v2/cache')


@dataclass(frozen=True)
class Settings:
    schema_version: int = 1
    capture: CaptureSettings = field(default_factory=CaptureSettings)
    geometry: GeometrySettings = field(default_factory=GeometrySettings)
    vision: VisionSettings = field(default_factory=VisionSettings)
    telemetry: TelemetrySettings = field(default_factory=TelemetrySettings)
    input: InputSettings = field(default_factory=InputSettings)
    control: ControlSettings = field(default_factory=ControlSettings)
    runtime: RuntimeSettings = field(default_factory=RuntimeSettings)
    diagnostics: DiagnosticsSettings = field(default_factory=DiagnosticsSettings)
    paths: PathSettings = field(default_factory=PathSettings)


def _typed(value, annotation, name):
    args = get_args(annotation)
    origin = get_origin(annotation)
    if args and type(None) in args:
        return None if value is None else _typed(value, next(a for a in args if a is not type(None)), name)
    if origin is tuple:
        if not isinstance(value, (tuple, list)) or len(value) != len(args):
            raise ConfigurationError(f'{name} must contain {len(args)} values')
        return tuple(_typed(v, t, name) for v, t in zip(value, args))
    if annotation is Path:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise ConfigurationError(f'{name} must be a nonempty path')
        return Path(value)
    if annotation is float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ConfigurationError(f'{name} must be a finite number')
        return float(value)
    if type(value) is not annotation:
        raise ConfigurationError(f'{name} must be {annotation.__name__}')
    return value


def _merge(instance, values, prefix=''):
    if not isinstance(values, Mapping):
        raise ConfigurationError(f'{prefix or "settings"} must be a table')
    known = {f.name for f in fields(instance)}
    unknown = set(values) - known
    if unknown:
        raise ConfigurationError(f'Unknown setting: {prefix}{next(iter(unknown))}')
    changes = {}
    hints = get_type_hints(type(instance))
    for key, value in values.items():
        current = getattr(instance, key)
        name = f'{prefix}{key}'
        changes[key] = _merge(current, value, name + '.') if is_dataclass(current) else _typed(value, hints[key], name)
    return replace(instance, **changes)


def _require(condition, message):
    if not condition:
        raise ConfigurationError(message)


def _rect(rect, width, height, name):
    left, top, right, bottom = rect
    _require(0 <= left < right <= width and 0 <= top < bottom <= height,
             f'{name} must be within {width}x{height}')


def validate_settings(settings: Settings) -> Settings:
    """Validate even directly constructed dataclasses; return resolved paths."""
    settings = _merge(Settings(), asdict(settings))
    c, g, v, t, i = settings.capture, settings.geometry, settings.vision, settings.telemetry, settings.input
    _require(settings.schema_version == 1, 'schema_version must be 1')
    _require(c.backend in {'dxcam', 'obs', 'replay'}, 'capture.backend must be dxcam, obs, or replay')
    _require(c.pixel_format in {'BGR', 'BGRA'}, 'capture.pixel_format must be BGR or BGRA')
    _require(c.obs_api in {'auto', 'dshow', 'msmf'}, 'capture.obs_api must be auto, dshow, or msmf')
    _require(c.backend == 'obs' or c.obs_api == 'auto', 'capture.obs_api requires OBS')
    _require(c.backend == 'dxcam' or c.output_index == 0, 'capture.output_index is DXcam-only')
    _require(c.device_index >= 0 and c.output_index >= 0, 'Capture device/output indexes must be nonnegative')
    _require(c.fps <= 1000, 'capture.fps must not exceed 1000')
    _require(c.width * c.height <= 33_177_600, 'Capture dimensions exceed supported allocation limit')
    _require(c.max_frames is None or c.max_frames > 0, 'capture.max_frames must be positive')
    _require(c.backend in {'dxcam', 'obs'} or not c.repeated_frames, 'repeated_frames requires native capture')
    _require(c.backend != 'obs' or c.pixel_format == 'BGR', 'OBS delivers BGR; configure capture.pixel_format=BGR')
    _require(c.backend == 'replay' or c.fixture is None, 'capture.fixture requires replay')
    _require(c.backend != 'replay' or c.fixture is not None, 'Replay requires --fixture or capture.fixture')
    _require(not (c.backend == 'replay' and i.enable_input), 'Replay cannot enable physical input')
    _require(i.require_focus, 'input.require_focus must remain enabled')
    _require(1 <= i.vjoy_device_id <= 16 and 0 <= i.vjoy_neutral <= 32768, 'Invalid vJoy configuration')
    _require(bool(i.emergency_stop_key.strip()) and bool(i.pause_key.strip()), 'Input hotkeys must be nonempty')
    _require(i.emergency_stop_key != i.pause_key, 'Emergency stop and pause hotkeys must differ')
    _require(bool(g.profile_id.strip()) and bool(g.window_class.strip()), 'Geometry profile and window class are required')
    for section in (c, g, t, settings.runtime, settings.diagnostics):
        for key, value in asdict(section).items():
            if key.endswith(('_s', '_hz', '_fps')) or key in {'fps', 'width', 'height', 'ui_scale', 'read_failure_limit', 'log_max_bytes', 'log_backups'}:
                _require(value > 0, f'{type(section).__name__}.{key} must be positive')
    for key, value in asdict(i).items():
        if key.endswith('_s') or key == 'max_pending':
            _require(value > 0, f'input.{key} must be positive')
    for key, value in asdict(settings.control).items():
        _require(value >= 0 if key.endswith(('_kp', '_ki', '_kd')) else value > 0, f'control.{key} is out of range')
    _require(t.retry_backoff_s <= t.max_backoff_s, 'Telemetry backoff exceeds maximum')
    try:
        url = urlsplit(t.base_url)
        port = url.port
    except ValueError as exc:
        raise ConfigurationError('telemetry.base_url has an invalid host or port') from exc
    _require(port is None or port > 0, 'telemetry.base_url port must be positive')
    _require(url.scheme in {'http', 'https'} and bool(url.hostname) and not url.username and not url.password and not url.query and not url.fragment,
             'telemetry.base_url must be an HTTP(S) URL without credentials, query, or fragment')
    _rect(g.obs_content_rect, c.width, c.height, 'geometry.obs_content_rect')
    for name in ('fire_roi', 'heading_roi', 'ammo_roi'):
        _rect(getattr(v, name), g.width, g.height, f'vision.{name}')
    for prefix in ('fire', 'heading'):
        lower, upper = getattr(v, prefix + '_hsv_lower'), getattr(v, prefix + '_hsv_upper')
        _require(all(0 <= a <= b <= maximum for a, b, maximum in zip(lower, upper, (179, 255, 255))), f'Invalid {prefix} HSV bounds')
    _require(0 <= v.canny_low < v.canny_high and v.canny_input in {'color', 'gray'}, 'Invalid Canny settings')
    _require(v.morphology_size > 0 and v.morphology_size % 2 == 1 and v.preprocess_version > 0, 'Invalid morphology/preprocessing version')
    for key, value in asdict(v).items():
        if key.endswith('_threshold'):
            _require(0 <= value <= 1, f'vision.{key} must be between 0 and 1')
    _require(settings.diagnostics.log_level in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}, 'Invalid diagnostics.log_level')
    root = resource_root()
    def resolve(path):
        return (root / path).resolve() if not path.is_absolute() else path.resolve()
    paths = replace(settings.paths, **{key: resolve(value) for key, value in asdict(settings.paths).items()})
    _require(paths.templates.is_dir(), f'Template directory does not exist: {paths.templates}')
    for path in (paths.aim_template, paths.route):
        _require(path.is_file(), f'Required resource does not exist: {path}')
    for output in (paths.logs, paths.cache):
        _require(not output.exists() or output.is_dir(), f'Output path must be a directory: {output}')
        for protected in (root / 'src', paths.templates, paths.aim_template, paths.route):
            _require(not output.is_relative_to(protected) and not protected.is_relative_to(output), f'Output path overlaps protected assets: {output}')
    if c.fixture is not None:
        fixture = resolve(c.fixture)
        _require((fixture / 'manifest.json').is_file(), f'Replay manifest does not exist: {fixture / "manifest.json"}')
        c = replace(c, fixture=fixture)
    return replace(settings, capture=c, paths=paths)


def load_settings(path: str | Path | None = None, overrides: Mapping[str, object] | None = None) -> Settings:
    settings = Settings()
    if path is not None:
        try:
            with Path(path).open('rb') as stream:
                settings = _merge(settings, tomllib.load(stream))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(f'Cannot load configuration {path}: {exc}') from exc
    if overrides is not None:
        settings = _merge(settings, overrides)
    return validate_settings(settings)
