"""Offline distribution diagnostics must use the production child boundaries."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('arguments', [['--enable-input'], ['--capture', 'dxcam'], ['--preflight']])
def test_offline_smoke_rejects_live_options(arguments, tmp_path):
    result = subprocess.run([sys.executable, str(ROOT/'autonavy.py'), '--offline-smoke', *arguments], cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    assert 'standalone' in result.stderr

@pytest.mark.skipif(sys.platform != 'win32', reason='Real bundled Windows CPython3.11x64 native planner')
def test_offline_smoke_spawns_real_capture_and_native_planner(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT/'autonavy.py'), '--offline-smoke'], cwd=tmp_path, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report['capture_publication'] >= 1
    assert report['capture_child_exit'] == report['planner_child_exit'] == 0
    assert report['route_points'] >= 2
    assert report['resources'] >= 4
    assert report['hardware_opened'] is False


def test_relative_config_uses_distribution_root_from_unrelated_cwd(tmp_path):
    # A misleading same-name file in the caller cwd must not shadow bundled config.
    (tmp_path/'configs').mkdir()
    (tmp_path/'configs/default.toml').write_text('invalid toml')
    result = subprocess.run([sys.executable, str(ROOT/'autonavy.py'), '--check-config', '--config', 'configs/default.toml'], cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Configuration valid' in result.stdout
    assert str(ROOT/'configs/default.toml') in result.stdout
