"""Device-free runtime vision wiring and import/resource startup boundaries."""
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pytest
from autonavy.telemetry import OfflineTelemetry

from autonavy.app import Application
from autonavy.config import load_settings
from autonavy.geometry import GeometrySnapshot
from autonavy.models import FramePacket

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_observes_the_packet_delivered_by_its_only_reader(monkeypatch):
    g = GeometrySnapshot((100,50,1380,770),(1280,720),(0,0,1280,720))
    image = np.zeros((720,1280,3),np.uint8)
    image[300:328,500:602] = cv2.imread(str(ROOT/'src/game_image/start.png'))
    p = FramePacket(image,'BGR',1,4,10,g.geometry_id,geometry=g)
    class Capture:
        def start(self): pass
        def read(self, timeout=None): return p
        def close(self): pass
    monkeypatch.setattr('autonavy.capture.factory.create_capture', lambda settings: Capture())
    app = Application(load_settings(overrides={'capture': {'max_frames':1}}), telemetry=OfflineTelemetry())
    assert app.run() == 0
    assert getattr(app, 'last_observations', None) is not None, 'runtime never called vision'
    assert app.last_observations.packet is p
    assert app.last_observations.matches['start'].matched
    assert app.last_observations.matches['start'].desktop_center == (651,364)


@pytest.mark.parametrize('filename', ['start.png','lock.png','confirm1.png'])
def test_missing_selected_template_fails_before_capture_factory(tmp_path, monkeypatch, filename):
    import shutil
    folder = tmp_path/'templates'
    shutil.copytree(ROOT/'src/game_image',folder)
    (folder/filename).unlink()
    called = []
    monkeypatch.setattr('autonavy.capture.factory.create_capture', lambda settings: called.append(True))
    app = Application(load_settings(overrides={'paths': {'templates': str(folder)}}), telemetry=OfflineTelemetry())
    assert app.run() == 3
    assert not called, 'capture factory ran before template validation'
    assert filename in app.last_error


def test_undecodable_aim_fails_before_capture_factory(tmp_path, monkeypatch):
    bad = tmp_path/'aim.png'
    bad.write_text('not an image')
    called = []
    monkeypatch.setattr('autonavy.capture.factory.create_capture', lambda settings: called.append(True))
    app = Application(load_settings(overrides={'paths': {'aim_template':str(bad)}}), telemetry=OfflineTelemetry())
    assert app.run() == 3 and not called
    assert 'aim' in app.last_error and 'decode' in app.last_error


def test_legacy_vision_imports_do_not_read_assets_sleep_or_open_devices():
    code = '''
import builtins, time, cv2, numpy as np
original = builtins.__import__
def guard(name, *args, **kwargs):
    if name.split('.')[0] in {'dxcam','win32gui','win32con','pyvjoy','requests','pydirectinput','keyboard','mouse'} or name in {'toolkit.MnK','toolkit.map'}:
        raise AssertionError('device/network import: ' + name)
    return original(name,*args,**kwargs)
def forbidden(*a,**k): raise AssertionError('import side effect')
builtins.__import__ = guard
time.sleep = forbidden
np.fromfile = forbidden
cv2.imread = forbidden
cv2.imshow = forbidden
import toolkit.scn, toolkit.img_map, toolkit.deg_cal, firesystem
'''
    result = subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf-8',timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('filename', ['crash_warning.png','crashed.png'])
def test_missing_collision_template_is_named_before_capture(tmp_path,monkeypatch,filename):
    import shutil
    (tmp_path/'src').mkdir()
    for name in ('crash_warning.png','crashed.png'):
        if name != filename:
            shutil.copy(ROOT/'src'/name,tmp_path/'src'/name)
    from autonavy.vision import templates
    monkeypatch.setattr(templates,'resource_root',lambda:tmp_path)
    called = []
    monkeypatch.setattr('autonavy.capture.factory.create_capture',lambda settings:called.append(True))
    app = Application(load_settings(), telemetry=OfflineTelemetry())
    assert app.run() == 3 and not called
    assert filename in app.last_error
