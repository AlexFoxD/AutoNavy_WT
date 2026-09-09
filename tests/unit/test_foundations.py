"""Foundation behavior tests: unsafe defaults and malformed settings must fail closed."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def config_module():
    assert importlib.util.find_spec('autonavy').submodule_search_locations is not None, 'safe package is missing'
    from autonavy import config
    return config


def test_config_precedence_and_default_resource_resolution(tmp_path, monkeypatch):
    config = config_module()
    path = tmp_path / 'settings.toml'
    path.write_text('[capture]\nfps = 120\n[telemetry]\npoll_hz = 5.0\n')
    monkeypatch.chdir(tmp_path)
    settings = config.load_settings(path, {'capture': {'fps': 30}})
    assert settings.capture.fps == 30
    assert settings.telemetry.poll_hz == 5
    assert settings.paths.templates == ROOT / 'src/game_image'
    assert settings.input.enable_input is False
    assert settings.capture.backend == 'dxcam'
    assert settings.diagnostics.preview is False
    assert config.load_settings(ROOT / 'configs/default.toml') == config.load_settings()


@pytest.mark.parametrize('overrides', [
    {'unknown': 1}, {'capture': {'fpz': 60}}, {'capture': {'fps': 0}},
    {'capture': {'fps': True}}, {'capture': {'fps': '60'}},
    {'capture': {'backend': 'webcam'}}, {'capture': {'pixel_format': 'RGB'}},
    {'schema_version': 2}, {'geometry': {'width': 0}},
    {'geometry': {'obs_content_rect': (0, 0, 1400, 720)}},
    {'vision': {'fire_roi': (0, 0, 1400, 720)}},
    {'vision': {'heading_roi': (40, 40, 20, 20)}},
    {'vision': {'fire_hsv_lower': (180, 0, 0)}},
    {'vision': {'template_threshold': 1.01}},
    {'telemetry': {'connect_timeout_s': 0}}, {'telemetry': {'object_ttl_s': -1}},
    {'control': {'heading_kp': float('nan')}}, {'runtime': {'tick_hz': float('inf')}},
    {'input': {'max_pending': 0}}, {'paths': {'templates': 'absent-directory'}},
    {'input': {'require_focus': False}},
    {'paths': {'logs': 'src/game_image'}},
    {'capture': {'backend': 'replay'}},
    {'capture': {'backend': 'replay', 'fixture': 'tests/fixtures/smoke'}, 'input': {'enable_input': True}},
    {'capture': {'backend': 'obs', 'pixel_format': 'BGRA'}},
    {'capture': {'backend': 'replay', 'fixture': 'tests/fixtures/smoke', 'repeated_frames': True}},
    {'capture': {'backend': 'dxcam', 'obs_api': 'dshow'}},
    {'capture': {'backend': 'obs', 'output_index': 1}},
    {'telemetry': {'base_url': 'http://[invalid'}},
    {'telemetry': {'base_url': 'http://localhost:wrong'}},
])
def test_invalid_config_is_rejected_before_startup(overrides):
    config = config_module()
    with pytest.raises(config.ConfigurationError):
        config.load_settings(overrides=overrides)


def test_toml_errors_are_configuration_errors(tmp_path):
    config = config_module()
    for text in ('[capture', '[capture]\nfps = -5'):
        path = tmp_path / 'bad.toml'
        path.write_text(text)
        with pytest.raises(config.ConfigurationError):
            config.load_settings(path)
    with pytest.raises(config.ConfigurationError):
        config.load_settings(tmp_path / 'missing.toml')


def test_non_utf8_config_is_classified_as_invalid_configuration(tmp_path):
    config = config_module()
    path = tmp_path / 'non-utf8.toml'
    path.write_bytes(b'[geometry]\nprofile_id = "\xff"\n')
    with pytest.raises(config.ConfigurationError):
        config.load_settings(path)


@pytest.mark.parametrize('arguments', [
    ['--capture', 'replay', '--enable-input'], ['--capture', 'replay'],
    ['--check-config'], ['--dry-run'], ['--enable-input'],
    ['--fixture', 'tests/fixtures/smoke'], ['--max-frames', '2'],
    ['--config', 'configs/default.toml'], ['--run'],
])
def test_preflight_conflicts_are_rejected_before_diagnostic_dispatch(arguments, monkeypatch):
    config_module()
    from autonavy import cli
    def forbidden_preflight(status_file):
        raise AssertionError('Conflicting modes must not dispatch preflight')
    monkeypatch.setattr(cli, '_preflight', forbidden_preflight)
    assert cli.main(arguments + ['--preflight']) == 2


def test_frame_packet_owns_readonly_pixels_and_rejects_bad_metadata():
    config_module()
    from autonavy.models import FramePacket
    producer = np.zeros((2, 3, 3), dtype=np.uint8)
    packet = FramePacket(producer, 'BGR', 1, 1, 10, 'test')
    producer[:] = 255
    assert not packet.image.any()
    with pytest.raises(ValueError):
        packet.image[0, 0] = 1
    with pytest.raises(ValueError):
        FramePacket(producer, 'BGRA', 1, 1, 10, 'test')
    with pytest.raises(ValueError):
        FramePacket(producer, 'BGR', 1, 1, 10, 'test', source_timestamp=1.0)


def test_cli_input_requires_explicit_flag_and_replay_rejects_it(tmp_path, capsys, monkeypatch):
    config_module()
    from autonavy.cli import main
    assert main(['--capture', 'replay', '--enable-input']) == 2
    path = tmp_path / 'input.toml'
    path.write_text('[input]\nenable_input = true\n')
    assert main(['--check-config', '--config', str(path)]) == 2
    assert main(['--check-config', '--config', str(path), '--dry-run']) == 0
    assert main(['--capture', 'dxcam', '--dry-run', '--enable-input']) == 2
    from autonavy.capture import factory
    from autonavy.capture.replay import ReplayCapture
    selected = []
    def fake_selected_capture(settings):
        selected.append(settings.capture.backend)
        return ReplayCapture(ROOT / 'tests/fixtures/smoke')
    monkeypatch.setattr(factory, 'create_capture', fake_selected_capture)
    assert main(['--capture', 'dxcam', '--dry-run']) == 0
    assert selected == ['dxcam']


def test_explicit_preflight_reports_missing_resources_instead_of_config_failure(tmp_path, monkeypatch):
    config_module()
    from autonavy import cli
    from autonavy import config
    from runtime_preflight import CheckResult
    import runtime_preflight
    monkeypatch.setattr(cli, 'resource_root', lambda: tmp_path)
    monkeypatch.setattr(config, 'resource_root', lambda: tmp_path)
    monkeypatch.setattr(runtime_preflight, 'run_preflight', lambda root: [CheckResult(False, 'resources', 'Missing resources')])
    status = tmp_path / 'status.json'
    assert cli.main(['--preflight', '--status-file', str(status)]) != 0
    assert status.is_file()
