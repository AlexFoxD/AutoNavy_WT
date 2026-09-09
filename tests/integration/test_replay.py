"""Run supported entrypoints with networking and hardware imports prohibited."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/smoke'
GUARD = '''
import importlib.abc, socket, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'runtime_preflight','dxcam','pyvjoy','win32gui','win32api','win32con','pydirectinput','keyboard','mouse','requests','pilot','firesystem','info'} or fullname in {'toolkit.scn','toolkit.MnK'}:
            raise AssertionError('forbidden import: ' + fullname)
sys.meta_path.insert(0, Guard())
def forbidden(*args, **kwargs):
    raise AssertionError('network access is forbidden')
socket.socket.connect = forbidden
socket.create_connection = forbidden
'''


def run_guarded(code, cwd=ROOT):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT)
    return subprocess.run([sys.executable, '-c', GUARD + '\n' + code], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=20)


def test_all_supported_imports_are_side_effect_free():
    result = run_guarded('import autonavy, start_prog, main\nimport runpy\nrunpy.run_path("autonavy.py", run_name="entry_import")')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('entry', ['module', 'autonavy.py', 'start_prog.py', 'main.py'])
@pytest.mark.parametrize('arguments,expected', [
    (['--help'], 0),
    (['--check-config', '--config', str(ROOT / 'configs/default.toml')], 0),
    (['--dry-run', '--capture', 'replay', '--fixture', str(FIXTURE), '--max-frames', '2'], 0),
    (['--capture', 'replay', '--enable-input'], 2),
    (['--capture', 'replay', '--enable-input', '--preflight'], 2),
    (['--capture', 'replay', '--preflight'], 2),
    (['--check-config', '--preflight'], 2),
])
def test_entrypoints_use_safe_cli_from_unrelated_cwd(entry, arguments, expected, tmp_path):
    command = "runpy.run_module('autonavy', run_name='__main__')" if entry == 'module' else f'runpy.run_path({str(ROOT / entry)!r}, run_name="__main__")'
    result = run_guarded(f'import runpy\nsys.argv = ["autonavy"] + {arguments!r}\n{command}', tmp_path)
    assert result.returncode == expected, result.stdout + result.stderr
    assert 'forbidden import' not in result.stderr
    if '--max-frames' in arguments:
        assert 'frames=2' in result.stdout


def test_non_utf8_config_returns_exit_two_without_device_or_network_access(tmp_path):
    path = tmp_path / 'non-utf8.toml'
    path.write_bytes(b'[geometry]\nprofile_id = "\xff"\n')
    result = run_guarded(f'from autonavy.cli import main\nsys.exit(main(["--check-config", "--config", {str(path)!r}]))', tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert 'Configuration error' in result.stderr
    assert 'forbidden import' not in result.stderr


def replay_class():
    assert importlib.util.find_spec('autonavy').submodule_search_locations is not None, 'safe replay package is missing'
    from autonavy.capture.replay import ReplayCapture
    return ReplayCapture


def test_finite_replay_budget_restart_and_packet_identity():
    source = replay_class()(FIXTURE, max_frames=2)
    with pytest.raises(RuntimeError):
        source.read()
    source.start()
    source.start()
    first, second = source.read(), source.read()
    assert first.publication_id < second.publication_id
    assert first.received_at_ns <= second.received_at_ns
    assert first.source_timestamp is None
    assert tuple(second.image[0, 0]) == (10, 20, 30)
    assert source.read() is None
    assert source.read() is None
    source.stop()
    source.start()
    restarted = source.read()
    assert restarted.source_generation > first.source_generation
    assert restarted.publication_id > second.publication_id
    source.close()
    source.close()
    with pytest.raises(RuntimeError):
        source.start()


def test_manifest_eof_and_application_cleanup():
    source = replay_class()(FIXTURE)
    source.start()
    assert len(list(iter(source.read, None))) == 3
    from autonavy.app import Application
    from autonavy.config import load_settings
    from autonavy.models import RuntimeState
    settings = load_settings(overrides={'capture': {'backend': 'replay', 'fixture': str(FIXTURE)}})
    app = Application(settings)
    assert app.run() == 0
    assert app.frames_processed == 3
    assert app.last_frame.source_sequence == 2
    assert app.state is RuntimeState.STOPPED
    app.stop()
    app.close()
    app.close()


@pytest.mark.parametrize('change', [
    {'schema_version': 2}, {'synthetic': False}, {'width': 0}, {'height': 1.5},
    {'pixel_format': 'RGB'}, {'frames': []}, {'frames': [{'color': [256, 0, 0]}]},
    {'frames': [{'url': 'https://example.invalid/frame.png'}]}, {'unexpected': True},
])
def test_malformed_replay_manifest_is_rejected(tmp_path, change):
    source_type = replay_class()
    data = json.loads((FIXTURE / 'manifest.json').read_text(encoding='utf-8-sig'))
    data.update(change)
    (tmp_path / 'manifest.json').write_text(json.dumps(data))
    with pytest.raises(ValueError):
        source_type(tmp_path).start()


def test_application_failure_and_ctrl_c_cleanup(monkeypatch):
    source_type = replay_class()
    from autonavy.app import Application
    from autonavy.config import load_settings
    from autonavy.models import RuntimeState
    settings = load_settings(overrides={'capture': {'backend': 'replay', 'fixture': str(FIXTURE)}})
    original = source_type.read
    for failure, expected, state in [(ValueError('broken replay'), 3, RuntimeState.ERROR),
                                     (KeyboardInterrupt(), 0, RuntimeState.STOPPED)]:
        def failing_read(self, timeout=None):
            raise failure
        monkeypatch.setattr(source_type, 'read', failing_read)
        app = Application(settings)
        assert app.run() == expected
        assert app.state is state
        assert app.capture.closed
    monkeypatch.setattr(source_type, 'read', original)


def test_stop_before_run_never_starts_capture():
    replay_class()
    from autonavy.app import Application
    from autonavy.config import load_settings
    settings = load_settings(overrides={'capture': {'backend': 'replay', 'fixture': str(FIXTURE)}})
    app = Application(settings)
    app.stop()
    assert app.run() == 0
    assert app.capture is None
    assert app.frames_processed == 0


def test_bad_manifest_failure_closes_source(tmp_path):
    replay_class()
    from autonavy.app import Application
    from autonavy.config import load_settings
    (tmp_path / 'manifest.json').write_text('{}')
    app = Application(load_settings(overrides={'capture': {'backend': 'replay', 'fixture': str(tmp_path)}}))
    assert app.run() == 3
    assert app.capture.closed
    assert app.frames_processed == 0
