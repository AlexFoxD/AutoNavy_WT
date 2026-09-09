"""Real spawned OBS adapter and runtime, fake VideoCapture and Windows only."""
from dataclasses import replace
import multiprocessing
import threading
from functools import partial
import time

import numpy as np
import pytest

from autonavy.config import Settings
from autonavy.geometry import GeometrySnapshot


class Geometry:
    def snapshot(self, size):
        return GeometrySnapshot((-1500,100,-220,820),size,(0,0,*size),window_handle=99)


class Camera:
    def __init__(self, index, api, entered=None):
        assert multiprocessing.parent_process() is not None
        assert api == 700
        self.mode = index
        if index == 1:
            if entered is not None: entered.set()
            while True: time.sleep(.01)
    def isOpened(self): return self.mode != 4
    def set(self, key, value): return True
    def get(self, key): return {3: 800.,4:600.,5:30.}.get(key,0.)
    def getBackendName(self): return 'FAKE_DSHOW'
    def read(self):
        if self.mode == 2:
            while True: time.sleep(.01)
        if self.mode == 5: return False, None
        return True, np.full((900,1600,3),(3,5,7),np.uint8)
    def release(self):
        if self.mode == 3:
            while True: time.sleep(.01)


def obs_factory(settings, entered=None):
    from autonavy.capture.obs import OBSSource
    return OBSSource(settings,camera_factory=partial(Camera,entered=entered),geometry_adapter=Geometry())


def capture(mode=0):
    from autonavy.capture.process import ProcessCapture
    s=Settings()
    s=replace(s,capture=replace(s.capture,backend='obs',device_index=mode,obs_api='dshow',width=1600,height=900,
                                startup_timeout_s=3,stop_timeout_s=.6,frame_timeout_s=.5),
                geometry=replace(s.geometry,obs_content_rect=(100,50,1380,770)))
    return ProcessCapture(s,source_factory=obs_factory)


def test_spawned_obs_delivers_diagnostics_owned_pixels_and_new_generation():
    c=capture()
    try:
        c.start(); first=c.read()
        assert first.image[0,0].tolist()==[3,5,7]
        assert first.source_timestamp is None and first.source_clock is None
        assert first.geometry.content_rect==(100,50,1380,770)
        assert c.diagnostic['requested']['device_index']==0
        assert c.diagnostic['reported']['width']==800
        assert c.diagnostic['delivered']['width']==1600
        exposed=c.diagnostic; exposed['reported']['width']=4
        assert c.diagnostic['reported']['width']==800
        c.stop(); assert not c.process.is_alive()
        c.start(); second=c.read()
        assert second.source_generation==2
        assert second.received_at_ns>first.received_at_ns
        assert first.image[0,0].tolist()==[3,5,7] and not first.image.flags.writeable
    finally: c.close()


def test_obs_actual_runtime_logs_requested_reported_delivered_and_mapping(monkeypatch,caplog):
    from autonavy.app import Application
    from autonavy.capture import factory
    from autonavy.telemetry import OfflineTelemetry
    c=capture(); c.settings=replace(c.settings,capture=replace(c.settings.capture,max_frames=2))
    monkeypatch.setattr(factory,'create_capture',lambda s:c)
    app=Application(c.settings,telemetry=OfflineTelemetry())
    with caplog.at_level('INFO',logger='autonavy.app'):
        assert app.run()==0
    records=[r for r in caplog.records if r.msg=='capture_source=%s']
    assert len(records)==1
    assert records[0].args['delivered']['width']==1600
    assert app.last_frame.geometry.recognition_supported and c.closed


@pytest.mark.parametrize('mode,fragment',[(4,'open'),(5,'3 consecutive')])
def test_obs_failed_open_and_reads_are_reclaimed_and_restartable(mode,fragment):
    c=capture(mode)
    try:
        with pytest.raises(RuntimeError,match=fragment):
            c.start(); c.read()
        c.stop()
        assert not c.process.is_alive()
        c.settings=replace(c.settings,capture=replace(c.settings.capture,device_index=0))
        c.start()
        assert c.read().source_generation==2
    finally: c.close()


@pytest.mark.parametrize('mode',[1,2,3])
def test_obs_hanging_open_read_release_reclaimed_after_input_cleanup(mode,monkeypatch):
    from test_battle_cycle import rig,enter_battle
    app,backend,clock,t,v,step=rig(); enter_battle(app,t,step)
    step(.1,markers=['crashed']); assert app.input.held
    c=capture(mode); app.capture=c
    if mode==1:
        # Test real startup timeout path separately from application shutdown.
        c.settings=replace(c.settings,capture=replace(c.settings.capture,startup_timeout_s=.5))
        app.input.release_all()
        with pytest.raises(RuntimeError,match='startup deadline'): c.start()
    else:
        c.start()
        if mode==3: c.read()
        original=c.process.terminate
        def terminate():
            assert not app.input.held
            assert ('key','s',0) in backend.events
            return original()
        monkeypatch.setattr(c.process,'terminate',terminate)
    now=time.monotonic()
    app.close()
    assert time.monotonic()-now<1.6
    assert not c.process.is_alive() and not app.input.held


def test_asymmetric_obs_aim_error_uses_content_center_through_real_controller():
    from test_battle_cycle import rig,enter_battle
    from autonavy.models import FramePacket
    app,b,clock,t,v,step=rig(); enter_battle(app,t,step)
    g=GeometrySnapshot((-1500,100,-220,820),(1600,900),(100,50,1380,770))
    def next_frame(x):
        clock.advance(.1)
        v.markers={'aim':(x-2,408,x+2,412)}
        p=FramePacket(np.zeros((900,1600,3),np.uint8),'BGR',100,1,clock(),g.geometry_id,geometry=g)
        app.last_frame=p; app.last_observations=v.observe(p)
        app.policy.identity=app.policy._identity(True)
        app.tick(p)
    try:
        next_frame(750)
        assert b.events[-1]==('move','pointer',(6,0))
        count=len(b.events)
        next_frame(740)
        assert not any(e[0]=='move' for e in b.events[count:])
    finally: app.close()


def test_obs_letterbox_real_vision_matches_native_rois_ammo_degree_and_clicks():
    import cv2
    from autonavy.config import load_settings
    from autonavy.models import FramePacket
    from autonavy.vision.detectors import VisionPipeline
    from autonavy.geometry import source_geometry
    s=load_settings()
    native=VisionPipeline(s)
    obs_settings=replace(s,capture=replace(s.capture,backend='obs',width=1600,height=900),
                         geometry=replace(s.geometry,obs_content_rect=(100,50,1380,770)))
    obs=VisionPipeline(obs_settings)
    image=np.zeros((720,1280,3),np.uint8)
    asset=cv2.imread(str(s.paths.templates/'start.png'))
    h,w=asset.shape[:2]; image[300:300+h,500:500+w]=asset
    cv2.fillPoly(image,[np.array([(110,550),(120,550),(115,580)],np.int32)],(0,255,0))
    image[660:690,480:520]=np.random.default_rng(5).integers(0,256,(30,40,3),dtype=np.uint8)
    native_geometry=Geometry().snapshot((1280,720))
    obs_geometry=source_geometry(obs_settings,Geometry().snapshot((1600,900)))
    canvas=np.zeros((900,1600,3),np.uint8); canvas[50:770,100:1380]=image
    def packet(pixels,g):return FramePacket(pixels,'BGR',1,1,1,g.geometry_id,geometry=g)
    p=packet(image,native_geometry); q=packet(canvas,obs_geometry)
    native.begin_battle(p); obs.begin_battle(q)
    a=native.observe(p); b=obs.observe(q)
    assert a.recognition_supported and b.recognition_supported
    assert a.matches['start'].matched and b.matches['ammo'].matched
    assert a.degree.available and b.degree.degrees==a.degree.degrees
    for name,first in a.matches.items():
        second=b.matches[name]
        assert (first.available,first.matched)==(second.available,second.matched),name
        assert first.desktop_center==second.desktop_center,name
        if first.frame_box:
            l,t,r,bottom=first.frame_box
            assert second.frame_box==(l+100,t+50,r+100,bottom+50),name
    shifted=replace(obs_geometry,client_rect=(-1490,100,-210,820))
    assert not obs.observe(packet(canvas,shifted)).matches['ammo'].available
    assert not obs.observe(q).matches['ammo'].available


@pytest.mark.parametrize('mutation',['move','dpi','source','scaled','content'])
def test_obs_live_guard_rejects_queued_intent_through_real_input_controller(mutation):
    from test_battle_cycle import Clock,Telemetry,Vision
    from autonavy.app import Application
    from autonavy.models import FramePacket
    from autonavy.input.controller import RecordingBackend,InputIntent
    from autonavy.input.windows import LiveWindowGuard
    from autonavy.geometry import source_geometry
    clock=Clock(); t=Telemetry(clock); v=Vision(); b=RecordingBackend(); b.physical=True
    c=capture(); settings=replace(c.settings,input=replace(c.settings.input,enable_input=True))
    current=[Geometry().snapshot((1600,900))]
    class Current:
        def snapshot(self,size):return current[0]
    guard=LiveWindowGuard(settings,geometry=Current(),foreground=lambda:99)
    app=Application(settings,telemetry=t,vision=v,input_backend=b,window_guard=guard,clock_ns=clock)
    g=source_geometry(settings,current[0])
    p=FramePacket(np.zeros((900,1600,3),np.uint8),'BGR',1,1,clock(),g.geometry_id,geometry=g)
    app.last_frame=p; app.last_observations=v.observe(p); app.input.set_mode('ui')
    intent=InputIntent('ui','key','enter',1,clock(),clock()+200_000_000,app.input.generation('ui'),
                       duration_ns=100_000_000,source_generation=1,geometry_id=p.geometry_id,requires_telemetry=False)
    assert app._input_guard(intent)
    assert app.input.submit(intent)
    if mutation=='move': current[0]=replace(current[0],client_rect=(-1490,100,-210,820))
    elif mutation=='dpi': current[0]=replace(current[0],dpi=144)
    elif mutation=='source': guard.settings=replace(settings,capture=replace(settings.capture,device_index=8))
    elif mutation=='content': guard.settings=replace(settings,geometry=replace(settings.geometry,obs_content_rect=(110,50,1390,770)))
    else: guard.settings=replace(settings,geometry=replace(settings.geometry,obs_content_rect=(100,50,740,410)))
    try:
        app.input.tick()
        assert not b.events and not app.input.held
    finally: app.close(); c.close()


def test_obs_stop_during_confirmed_native_open_releases_input_then_cancels_start(monkeypatch):
    from test_battle_cycle import rig,enter_battle
    app,backend,clock,t,v,step=rig(); enter_battle(app,t,step)
    step(.1,markers=['crashed']); assert app.input.held
    c=capture(1); app.capture=c
    entered=multiprocessing.get_context('spawn').Event()
    c._factory=partial(obs_factory,entered=entered)
    results=[]; errors=[]
    def start():
        try: results.append(c.start())
        except Exception as exc: errors.append(exc)
    runner=threading.Thread(target=start); runner.start()
    try:
        assert entered.wait(2.5), 'Fake VideoCapture open was not reached'
        original=c.process.terminate
        terminated=[]
        def terminate():
            assert not app.input.held
            assert ('key','s',0) in backend.events
            terminated.append(True)
            original()
        monkeypatch.setattr(c.process,'terminate',terminate)
        now=time.monotonic(); app.close(); runner.join(1)
        assert time.monotonic()-now<1.6
        assert terminated and not runner.is_alive() and not c.process.is_alive()
        assert results==[None] and not errors and c.closed and not c.started
        with pytest.raises(RuntimeError,match='closed'): c.start()
    finally:
        app.close(); runner.join(2)
