"""Capture ownership and selection without importing native devices."""
import importlib.util
import builtins
import sys
import threading
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest


def require_capture():
    assert importlib.util.find_spec('autonavy.capture.latest'), 'managed latest capture is missing'


def test_latest_replaces_owned_packets_and_close_wakes_waiter():
    require_capture()
    from autonavy.capture.latest import LatestFrameSlot
    from autonavy.models import FramePacket
    pixels = np.zeros((2, 3, 3), dtype=np.uint8)
    one = FramePacket(pixels, 'BGR', 1, 1, 1, 'test')
    slot = LatestFrameSlot()
    slot.publish(one)
    pixels[:] = 4
    two = FramePacket(pixels, 'BGR', 2, 1, 2, 'test')
    slot.publish(two)
    assert slot.read() is two
    assert slot.wait(after=(1, 1), timeout=0) is two
    assert not one.image.any()
    result = []
    waiter = threading.Thread(target=lambda: result.append(slot.wait(after=(1, 2), timeout=10)))
    waiter.start()
    slot.close()
    waiter.join(1)
    assert not waiter.is_alive() and result == [None]
    with pytest.raises(RuntimeError):
        slot.publish(one)


class FakeCamera:
    def __init__(self):
        self._output = SimpleNamespace(desc=SimpleNamespace(DesktopCoordinates=SimpleNamespace(left=-1920, top=0, right=0, bottom=1080)))
        self.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.calls = []
        self.result = self.image
        self.released = 0
    def grab(self, region=None):
        self.calls.append(region)
        if isinstance(self.result, Exception): raise self.result
        return self.result
    def release(self): self.released += 1


class FakeGeometry:
    def __init__(self): self.left = -1500
    def snapshot(self, frame_size):
        from autonavy.geometry import GeometrySnapshot
        return GeometrySnapshot((self.left, 100, self.left + 1280, 820), frame_size, (0, 0, *frame_size))


def test_dxcam_native_adapter_uses_selected_output_and_detects_move_during_grab():
    require_capture()
    from autonavy.capture.dxcam import DXcamSource
    from autonavy.config import Settings
    camera, geometry = FakeCamera(), FakeGeometry()
    selected = []
    def factory(**kwargs):
        selected.append(kwargs)
        return camera
    settings = replace(Settings(), capture=replace(Settings().capture, device_index=2, output_index=3))
    source = DXcamSource(settings, camera_factory=factory, geometry_adapter=geometry)
    assert not selected
    source.start()
    sample = source.read()
    snapshot = sample.geometry
    assert selected == [dict(device_idx=2, output_idx=3, output_color='BGR', max_buffer_len=1)]
    assert camera.calls == [(420, 100, 1700, 820)]
    assert snapshot.client_rect == (-1500, 100, -220, 820)
    camera.result = None
    assert source.read() is None
    camera.result = RuntimeError('native error')
    with pytest.raises(RuntimeError, match='native error'): source.read()
    camera.result = camera.image
    original = camera.grab
    def moving(region=None):
        result = original(region)
        geometry.left += 10
        return result
    camera.grab = moving
    assert source.read() is None
    source.close()
    source.close()
    assert camera.released == 1


def test_repeat_only_republishes_under_identical_geometry():
    require_capture()
    from autonavy.capture.dxcam import DXcamSource
    from autonavy.config import Settings
    camera, geometry = FakeCamera(), FakeGeometry()
    settings = replace(Settings(), capture=replace(Settings().capture, repeated_frames=True))
    source = DXcamSource(settings, camera_factory=lambda **kw: camera, geometry_adapter=geometry)
    source.start()
    first = source.read()
    camera.result = None
    repeated = source.read()
    assert repeated.geometry == first.geometry and np.array_equal(first.image, repeated.image)
    assert repeated.received_at_ns == first.received_at_ns
    geometry.left += 10
    assert source.read() is None
    geometry.left -= 10
    assert source.read() is None  # Returning to the old bounds cannot revive its cached frame.
    source.close()


def test_factory_selects_live_without_native_import_and_obs_has_no_fallback(monkeypatch):
    require_capture()
    from autonavy.capture.factory import create_capture
    from autonavy.capture.process import ProcessCapture
    from autonavy.config import load_settings
    capture = create_capture(load_settings())
    assert isinstance(capture, ProcessCapture) and not capture.started
    capture.close()
    with pytest.raises(RuntimeError, match='closed'):
        capture.start()
    with pytest.raises(RuntimeError, match='OBS'):
        create_capture(load_settings(overrides={'capture': {'backend': 'obs'}}))


def test_legacy_screen_import_cannot_acquire_or_start_native_capture(monkeypatch):
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in {'dxcam', 'win32gui', 'pyvjoy', 'pydirectinput'}:
            raise AssertionError('Legacy capture attempted a native import')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    sys.modules.pop('toolkit.scn', None)
    module = __import__('toolkit.scn', fromlist=['match_img'])
    assert callable(module.match_img)


def test_static_new_acquisition_refreshes_time_but_cached_repeat_never_does(monkeypatch):
    from autonavy.capture.dxcam import DXcamSource
    from autonavy.capture import dxcam as adapter
    from autonavy.config import Settings
    camera = FakeCamera()
    moments = iter((100, 200))
    monkeypatch.setattr(adapter.time, 'monotonic_ns', lambda: next(moments))
    settings = replace(Settings(), capture=replace(Settings().capture, repeated_frames=True))
    source = DXcamSource(settings, camera_factory=lambda **kw: camera, geometry_adapter=FakeGeometry())
    source.start()
    first = source.read()
    second = source.read()  # Same pixels, genuinely acquired from source.
    camera.result = None
    repeated = source.read()
    assert first.received_at_ns == 100 and second.received_at_ns == repeated.received_at_ns == 200
    source.close()


def test_invalid_profile_reference_dimensions_cannot_be_recognized():
    from autonavy.windows import WindowsGeometry
    from autonavy.config import GeometrySettings
    from test_geometry import WindowAPI
    snapshot = WindowsGeometry(replace(GeometrySettings(), width=1920, height=1080), api=WindowAPI()).snapshot((1280, 720))
    assert not snapshot.recognition_supported


def test_common_replay_read_can_poll_without_losing_finite_eof():
    from autonavy.capture.factory import create_capture
    from autonavy.config import load_settings
    capture = create_capture(load_settings(overrides={'capture': {'backend': 'replay', 'fixture': 'tests/fixtures/smoke', 'max_frames': 1}}))
    capture.start()
    assert capture.read(timeout=0) is not None
    assert capture.read(timeout=0) is None
    capture.close()
