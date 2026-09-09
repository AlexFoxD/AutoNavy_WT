"""OBS adapter contracts; no camera, GUI, or native device is opened."""
import builtins
import importlib.util
from dataclasses import replace

import numpy as np
import pytest

from autonavy.config import Settings, load_settings
from autonavy.geometry import GeometrySnapshot


def settings(**capture):
    s = Settings()
    return replace(s, capture=replace(s.capture, backend='obs', device_index=7, obs_api='dshow',
                                     width=1600, height=900, **capture),
                   geometry=replace(s.geometry, obs_content_rect=(100, 50, 1380, 770)))


class Geometry:
    def __init__(self):
        self.left = -1500
        self.dpi = 96
    def snapshot(self, size):
        return GeometrySnapshot((self.left, 100, self.left+1280, 820), size, (0, 0, *size),
                                window_handle=99, dpi=self.dpi)


class Camera:
    def __init__(self):
        self.opened = True
        self.released = 0
        self.requests = []
        self.image = np.full((900, 1600, 3), (11, 22, 33), np.uint8)
        self.result = (True, self.image)
    def isOpened(self): return self.opened
    def set(self, key, value):
        self.requests.append((key, value))
        return False  # Never infer actual negotiation from this value.
    def get(self, key): return {3: 800., 4: 600., 5: 29.97, 16: 1.}.get(key, 0.)
    def getBackendName(self): return 'DSHOW'
    def read(self):
        if isinstance(self.result, Exception): raise self.result
        return self.result
    def release(self): self.released += 1


def source(camera=None, geometry=None, configured=None):
    assert importlib.util.find_spec('autonavy.capture.obs'), 'OBS source is missing'
    from autonavy.capture.obs import OBSSource
    camera = camera or Camera()
    selected = []
    def factory(*args):
        selected.append(args)
        return camera
    return OBSSource(configured or settings(), camera_factory=factory,
                     geometry_adapter=geometry or Geometry()), camera, selected


def test_obs_selected_index_api_lazy_bgr_and_truthful_diagnostics():
    s, camera, selected = source()
    assert selected == []
    s.start()
    sample = s.read()
    assert selected == [(7, 700)]
    assert sample.image[0, 0].tolist() == [11, 22, 33]
    assert sample.geometry.content_rect == (100, 50, 1380, 770)
    assert sample.geometry.recognition_supported
    diagnostic = sample.diagnostic
    assert diagnostic['requested'] == dict(device_index=7, api='dshow', width=1600, height=900, fps=60, pixel_format='BGR')
    assert diagnostic['reported']['backend'] == 'DSHOW'
    assert diagnostic['reported']['width'] == 800
    assert diagnostic['reported']['height'] == 600
    assert diagnostic['delivered'] == dict(width=1600, height=900, channels=3, dtype='uint8', pixel_format='BGR')
    assert diagnostic['source_timestamp'] is None
    assert diagnostic['device_identity_verified'] is False
    s.close(); s.close()
    assert camera.released == 1


def test_obs_failed_open_releases_only_selected_device_then_can_reopen():
    s, camera, selected = source()
    camera.opened = False
    with pytest.raises(RuntimeError, match='open'): s.start()
    assert camera.released == 1 and selected == [(7, 700)]
    camera.opened = True
    s.start()
    assert s.read() is not None
    s.close()
    assert camera.released == 2 and selected == [(7, 700), (7, 700)]


@pytest.mark.parametrize('image', [None, np.zeros((900,1600),np.uint8), np.zeros((900,1600,4),np.uint8),
                                   np.zeros((900,1600,3),np.float32), np.zeros((600,800,3),np.uint8)])
def test_obs_rejects_actual_invalid_delivered_frame(image):
    s, camera, _ = source()
    camera.result = (True, image)
    s.start()
    with pytest.raises(RuntimeError, match='delivered'): s.read()
    s.close()
    assert camera.released == 1


def test_obs_read_failure_bound_and_success_resets_counter():
    s, camera, _ = source()
    s.start()
    camera.result = (False, None)
    assert s.read() is None and s.read() is None
    camera.result = (True, camera.image)
    assert s.read() is not None
    camera.result = (False, None)
    assert s.read() is None and s.read() is None
    with pytest.raises(RuntimeError, match='3 consecutive'): s.read()
    s.close()


def test_obs_identical_new_acquisitions_fresh_but_repeat_age_retained(monkeypatch):
    s, camera, _ = source(configured=settings(repeated_frames=True))
    from autonavy.capture import obs
    moments = iter((100, 200))
    monkeypatch.setattr(obs.time, 'monotonic_ns', lambda: next(moments))
    s.start()
    first = s.read(); second = s.read()
    camera.image[:] = 255
    camera.result = (False, None)
    repeated = s.read()
    assert first.received_at_ns == 100
    assert second.received_at_ns == repeated.received_at_ns == 200
    assert repeated.image[0,0].tolist() == [11,22,33]
    s.close()
    configured = load_settings(overrides={'capture': {'backend': 'obs', 'repeated_frames': True}})
    assert configured.capture.repeated_frames


def test_obs_move_during_read_discards_and_cannot_revive_repeat():
    geometry = Geometry()
    s, camera, _ = source(geometry=geometry, configured=settings(repeated_frames=True))
    s.start(); s.read()
    original = camera.read
    def moving():
        geometry.left += 10
        return original()
    camera.read = moving
    assert s.read() is None
    camera.read = original
    camera.result = (False, None)
    geometry.left -= 10
    assert s.read() is None
    s.close()


def test_obs_exception_retains_context_and_can_close():
    s, camera, _ = source()
    s.start()
    camera.result = RuntimeError('driver failed')
    with pytest.raises(RuntimeError, match='driver failed'): s.read()
    s.close()
    assert camera.released == 1


def test_factory_and_default_imports_do_not_import_cv2_or_open_any_device(monkeypatch):
    from autonavy.capture.factory import create_capture
    real_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in {'cv2', 'dxcam'}: raise AssertionError('optional hardware imported in parent')
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    default = create_capture(Settings())
    obs = create_capture(settings())
    assert not default.started and not obs.started
    # Exercise the factory-selected source against fake native boundaries. A
    # mistakenly selected DXcam source cannot satisfy the positional index/API.
    monkeypatch.setattr(builtins, '__import__', real_import)
    camera=Camera(); selected=[]
    def native(index,api):
        selected.append((index,api)); return camera
    adapter=obs._factory(settings(),camera_factory=native,geometry_adapter=Geometry())
    adapter.start()
    assert adapter.read().image[0,0].tolist()==[11,22,33]
    assert selected==[(7,700)]
    adapter.close(); default.close(); obs.close()


def test_obs_window_guard_maps_same_source_and_rejects_move_dpi_and_source():
    s, _, _ = source()
    from autonavy.input.windows import LiveWindowGuard
    from autonavy.models import FramePacket
    g = Geometry()
    guard = LiveWindowGuard(settings(), geometry=g, foreground=lambda:99)
    s.start(); sample = s.read()
    p = FramePacket(sample.image,'BGR',1,1,1,sample.geometry.geometry_id,geometry=sample.geometry)
    assert guard(p)
    g.left += 10
    assert not guard(p)
    g.left -= 10; g.dpi = 144
    assert not guard(p)
    g.dpi = 96
    assert not LiveWindowGuard(replace(settings(),capture=replace(settings().capture,device_index=8)),
                               geometry=g,foreground=lambda:99)(p)
    s.close()


@pytest.mark.parametrize('api,code',[('auto',0),('dshow',700),('msmf',1400)])
def test_obs_only_configured_api_and_requested_properties(api,code):
    configured=replace(settings(),capture=replace(settings().capture,obs_api=api))
    s,camera,selected=source(configured=configured)
    s.start(); s.read(); s.close()
    assert selected==[(7,code)]
    assert camera.requests==[(3,1600),(4,900),(5,60),(16,1)]


@pytest.mark.parametrize('boundary',['construct','properties','read'])
def test_obs_native_exceptions_include_selected_device_context(boundary):
    s,camera,selected=source()
    def fail(*args):raise RuntimeError('native failure')
    if boundary=='construct': s._factory=fail
    elif boundary=='properties':camera.set=fail
    else:camera.read=fail
    try:
        with pytest.raises(RuntimeError,match='device_index.*7') as error:
            s.start(); s.read()
        assert 'native failure' in str(error.value)
    finally:s.close()
    if boundary!='construct':assert camera.released==1


def test_obs_invalid_channels_diagnostic_does_not_label_them_bgr():
    s,camera,_=source()
    camera.result=(True,np.zeros((900,1600,4),np.uint8))
    s.start()
    try:
        with pytest.raises(RuntimeError) as error:s.read()
        assert "'channels': 4" in str(error.value)
        assert "'pixel_format': None" in str(error.value)
    finally:s.close()


def test_obs_partial_start_failure_preserves_primary_and_cleanup_errors():
    s,camera,_=source()
    def failed_set(*args):raise RuntimeError('configure failed')
    def failed_release():
        camera.released+=1
        raise RuntimeError('release failed')
    camera.set=failed_set; camera.release=failed_release
    with pytest.raises(RuntimeError) as error:s.start()
    assert 'configure failed' in str(error.value) and 'release failed' in str(error.value)
    s.close()
    assert camera.released==1
