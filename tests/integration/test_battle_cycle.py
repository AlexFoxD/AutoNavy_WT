"""Synthetic observations exercise the real runtime policy and input owner."""
from dataclasses import replace
from types import MappingProxyType
import numpy as np
import pytest
from autonavy.app import Application
from autonavy.config import Settings
from autonavy.geometry import GeometrySnapshot
from autonavy.models import FramePacket, RuntimeState
from autonavy.telemetry import TelemetrySnapshot, OfflineTelemetry, Player, MapMetadata
from autonavy.vision.detectors import VisionObservations, MatchObservation, DegreeObservation
from autonavy.input.controller import RecordingBackend


class Clock:
    now = 1_000_000_000
    def __call__(self): return self.now
    def advance(self,s): self.now += int(s*1e9)


class Telemetry(OfflineTelemetry):
    def __init__(self,clock): self.clock=clock; self.valid=False; self.generation=1
    def snapshot(self):
        if not self.valid: return TelemetrySnapshot(generation=self.generation)
        return TelemetrySnapshot(generation=self.generation, player=Player((.5,.5),0,-1),
            metadata=MapMetadata((0,0),(100,100),(10,10),self.clock()),
            received_at_ns=self.clock(),valid=True)


class Vision:
    def __init__(self): self.markers={}; self.baselines=[]; self.selections=[]
    def begin_battle(self,packet): self.baselines.append(packet.publication_id)
    def observe(self,packet,selection=None):
        self.selections.append(selection)
        matches={name:MatchObservation(packet.publication_id,packet.source_generation,packet.geometry_id,
            True,True,1,box,packet.geometry.frame_to_desktop(((box[0]+box[2])//2,(box[1]+box[3])//2)))
            for name,box in self.markers.items()}
        return VisionObservations(packet,MappingProxyType(matches),DegreeObservation(packet.publication_id,
                                  packet.source_generation,packet.geometry_id,True,0),True)


def rig():
    clock=Clock(); telemetry=Telemetry(clock); vision=Vision(); backend=RecordingBackend()
    app=Application(Settings(),telemetry=telemetry,clock_ns=clock,input_backend=backend,vision=vision,wait=lambda seconds:clock.advance(seconds))
    geometry=GeometrySnapshot((-1400,50,-120,770),(1280,720),(0,0,1280,720),window_handle=42)
    serial=[0]
    def step(seconds=0,markers=(),fresh=True):
        clock.advance(seconds); vision.markers={name:(638,358,642,362) for name in markers}
        serial[0]+=1
        packet=FramePacket(np.zeros((720,1280,3),np.uint8),'BGR',serial[0],1,clock(),geometry.geometry_id,geometry=geometry) if fresh else None
        app.tick(packet)
    return app,backend,clock,telemetry,vision,step


def enter_battle(app,t,step):
    step(markers=['start']); step(.1,markers=['join_game'])
    step(20); t.valid=True; step(.1); step(15)
    for _ in range(4): step(.1)
    assert app.state == RuntimeState.IN_BATTLE


def test_complete_real_policy_cycle_queue_init_fire_recovery_end_manual_pause():
    app,b,clock,t,v,step=rig()
    enter_battle(app,t,step)
    assert len(v.baselines)==1 and b.events.count(('key','s',1))==3
    step(.1)  # Search: zoom and X fallback.
    assert ('key','shift',1) in b.events and ('key','x',1) in b.events
    step(.1,markers=['aim','ammo']); step(.5,markers=['aim','ammo'])
    assert ('mouse','left',1) in b.events
    step(.1,markers=['crashed'])
    assert app.state == RuntimeState.RECOVERING and ('key','s') in app.input.held
    step(3); assert ('key','s') not in app.input.held
    step(59.9); assert ('key','w') not in app.input.held
    step(.1); assert ('key','w') in app.input.held
    step(5); assert ('key','w') not in app.input.held
    for _ in range(3): step(.1)
    step(10); assert app.state == RuntimeState.IN_BATTLE
    step(.1,markers=['back']); assert app.state == RuntimeState.WAITING
    step(.2,markers=['purchase_confirm']); assert app.state == RuntimeState.PAUSED
    assert not app.input.held
    app.pause(); step(.1,markers=['purchase_confirm']); assert app.state == RuntimeState.PAUSED
    app.pause(); step(.1); assert app.state != RuntimeState.PAUSED
    app.stop(); app.tick(); assert not app.input.held


def test_no_frame_ticks_expire_holds_and_telemetry_loss_cancels_battle_not_ui():
    app,b,clock,t,v,step=rig()
    step(markers=['start'])
    assert ('key','enter') in app.input.held
    t.generation+=1
    step(.025,fresh=False); assert ('key','enter') in app.input.held
    step(.03,fresh=False); assert not app.input.held
    step(.1,markers=['join_game']); step(20); t.valid=True; step(.1); step(15)
    for _ in range(4): step(.1)
    step(.1,markers=['crashed']); assert app.input.held
    t.valid=False; step(.01,fresh=False)
    assert not app.input.held and app.state != RuntimeState.RECOVERING


def test_paused_stop_and_cleanup_release_before_capture_or_telemetry_errors():
    app,b,clock,t,v,step=rig(); enter_battle(app,t,step)
    step(.1,markers=['crashed'])
    class Broken:
        def request_stop(self): pass
        def close(self):
            assert not app.input.held
            raise RuntimeError('camera cleanup')
    app.capture=Broken()
    with pytest.raises(RuntimeError,match='camera cleanup'): app.close()
    assert not app.input.held


@pytest.mark.parametrize('mutation', ['geometry','focus','profile','frame','source','telemetry','session','optin'])
def test_application_dispatch_guard_uses_current_prerequisites(mutation):
    app,b,clock,t,v,step=rig(); enter_battle(app,t,step)
    from autonavy.input.controller import InputIntent
    p=app.last_frame
    i=InputIntent('navigation','key','w',1,clock(),clock()+250_000_000,
        app.input.generation('navigation'),duration_ns=1_000_000_000,
        source_generation=1,geometry_id=p.geometry_id,telemetry_generation=t.generation)
    app.input.submit(i)
    if mutation in ('geometry','focus'):
        app.input.backend.physical=True; app.settings=replace(app.settings,input=replace(app.settings.input,enable_input=True))
        app.window_guard=lambda packet: False
    elif mutation=='profile': app.last_observations=replace(app.last_observations,recognition_supported=False)
    elif mutation=='frame': clock.advance(.5)
    elif mutation=='source': app.last_frame=replace(p,source_generation=2)
    elif mutation=='telemetry': t.valid=False
    elif mutation=='session': t.generation+=1
    elif mutation=='optin': app.input.backend.physical=True
    count=len(b.events); app.input.tick()
    assert ('key','w',1) not in b.events[count:]

def test_real_vision_selected_match_counts_and_critical_detectors(monkeypatch):
    from autonavy.vision import detectors
    from autonavy.behavior import PURCHASE, END, BATTLE, MENU
    app,b,clock,t,v,step=rig(); step()
    pipeline=detectors.VisionPipeline(app.settings)
    calls=[]
    original=detectors.match_template
    def count(*args,**kwargs):
        calls.append(args[2]); return original(*args,**kwargs)
    monkeypatch.setattr(detectors,'match_template',count)
    for selected,expected_max in ((PURCHASE|END|BATTLE,15),(PURCHASE|END|MENU,28)):
        calls.clear()
        observations=pipeline.observe(app.last_frame,selection=selected)
        assert len(calls)<=expected_max
        assert PURCHASE <= set(calls)
        assert {'back','base','data','cart','start'} <= set(calls)
        if selected & BATTLE:
            assert 'confirm' not in calls
            assert not observations.matches['confirm'].available
        else: assert 'aim' not in calls


def test_actual_run_ticks_on_capture_timeout_and_releases_before_cleanup(monkeypatch):
    from autonavy.capture import factory
    from autonavy.capture.base import CaptureTimeout
    app,b,clock,t,v,step=rig()
    # Build a packet without advancing the policy, then run the real loop.
    geometry=GeometrySnapshot((0,0,1280,720),(1280,720),(0,0,1280,720))
    p=FramePacket(np.zeros((720,1280,3),np.uint8),'BGR',1,1,clock(),geometry.geometry_id,geometry=geometry)
    v.markers={'start':(10,10,20,20)}
    class Capture:
        count=0
        def start(self): pass
        def read(self,timeout=None):
            assert timeout == 1/app.settings.runtime.tick_hz
            self.count+=1
            if self.count==1: return p
            if self.count==2:
                assert ('key','enter') in app.input.held
                clock.advance(.06); raise CaptureTimeout('static frame')
            assert not app.input.held
            return None
        def request_stop(self): pass
        def close(self): assert not app.input.held
    monkeypatch.setattr(factory,'create_capture',lambda settings:Capture())
    assert app.run()==0
    assert ('key','enter',1) in b.events and ('key','enter',0) in b.events

def test_ui_source_change_cancels_spawn_but_missing_player_does_not():
    app,b,clock,t,v,step=rig(); step(markers=['join_game'])
    assert app.policy.stage=='spawn'
    t.generation+=1; step(.1)
    assert app.policy.stage=='spawn'
    packet=replace(app.last_frame,source_generation=2,publication_id=99)
    app.tick(packet)
    assert app.policy.stage=='hangar'


def test_purchase_and_end_are_consumed_even_when_battle_telemetry_disappears():
    app,b,clock,t,v,step=rig(); enter_battle(app,t,step)
    t.valid=False; step(.1,markers=['purchase_confirm'])
    assert app.state==RuntimeState.PAUSED and not app.input.held


def test_runtime_deadlines_still_expire_with_frozen_no_frame_source():
    app,b,clock,t,v,step=rig(); step(markers=['join_game'])
    step(20); assert app.policy.stage=='player'
    with pytest.raises(RuntimeError,match='player deadline'): step(31,fresh=False)


def test_full_scripted_cycle_uses_real_application_run(monkeypatch):
    from autonavy.capture import factory
    from autonavy.capture.base import CaptureTimeout
    app,b,clock,t,v,unused=rig()
    geometry=GeometrySnapshot((-1400,50,-120,770),(1280,720),(0,0,1280,720),window_handle=42)
    # This is a synthetic scripted source, not a recorded game replay.
    script=[(0,['start'],False),(.1,['join_game'],False),(20,[],False),(.1,[],True),(15,[],True)]
    script += [(.1,[],True)]*4
    script += [(.1,['aim','ammo'],True),(.5,['aim','ammo'],True),(.1,['crashed'],True),
               (3,[],True),(60,[],True),(5,[],True)]
    script += [(.1,[],True)]*3+[(10,[],True),(.1,['back'],True),(.2,['purchase_confirm'],False),
                              (.1,[],False),(.1,['start'],False)]
    seen=[]
    class Capture:
        index=0
        source_generation=1
        def start(self): pass
        def read(self,timeout=None):
            seen.append((app.state,app.policy.stage,dict(app.input.held)))
            if self.index==len(script):
                app.emergency_stop(); return None
            delay,markers,valid=script[self.index]
            if app.state==RuntimeState.PAUSED and not markers: app.pause()
            clock.advance(delay);t.valid=valid
            v.markers={name:(638,358,642,362) for name in markers}
            self.index+=1
            return FramePacket(np.zeros((720,1280,3),np.uint8),'BGR',self.index,1,clock(),geometry.geometry_id,geometry=geometry)
        def request_stop(self): pass
        def close(self): assert not app.input.held
    monkeypatch.setattr(factory,'create_capture',lambda settings:Capture())
    assert app.run()==0
    states={state for state,_,_ in seen}
    assert {RuntimeState.WAITING,RuntimeState.QUEUEING,RuntimeState.IN_BATTLE,
            RuntimeState.RECOVERING,RuntimeState.PAUSED} <= states
    assert len(v.baselines)==1 and ('mouse','left',1) in b.events
    assert b.events.count(('key','s',1))==7  # Three init taps, reverse hold, three recovery taps.
    assert app.state==RuntimeState.STOPPED and not app.input.held


def test_search_uses_actual_enemy_position_and_source_equivalent_pid_sign():
    from autonavy.telemetry import Enemy
    app,b,clock,t,v,step=rig();enter_battle(app,t,step)
    original=t.snapshot
    t.snapshot=lambda:replace(original(),enemies=(Enemy((.6,.4)),))
    step(.2)
    assert ('move','pointer',(27,0)) in b.events


def test_zoom_levels_schedule_shift_and_right_click_without_blocking():
    app,b,clock,t,v,step=rig();enter_battle(app,t,step)
    app.policy.set_zoom(2);app.input.tick()
    assert ('key','shift',1) in b.events and ('mouse','right',1) in b.events
    step(.2,markers=['lock']);app.policy.set_zoom(0);app.input.tick()
    assert b.events.count(('key','shift',1))==2 and b.events.count(('mouse','right',1))==2

@pytest.mark.parametrize('failure', ['capture_start','telemetry_start','capture_read','vision'])
def test_actual_run_input_cleanup_on_startup_worker_and_observation_errors(monkeypatch,failure):
    from autonavy.capture import factory
    app,b,clock,t,v,step=rig()
    geometry=GeometrySnapshot((0,0,1280,720),(1280,720),(0,0,1280,720))
    p=FramePacket(np.zeros((720,1280,3),np.uint8),'BGR',1,1,clock(),geometry.geometry_id,geometry=geometry)
    v.markers={'start':(10,10,20,20)}
    def failed():raise RuntimeError(failure)
    if failure=='telemetry_start':t.start=failed
    old_observe=v.observe
    def observe(*args,**kwargs):
        if app.frames_processed:failed()
        return old_observe(*args,**kwargs)
    if failure=='vision':v.observe=observe
    closed=[]
    class Capture:
        count=0
        def start(self):
            if failure=='capture_start':failed()
        def read(self,timeout=None):
            self.count+=1
            if self.count==2 and failure=='capture_read':failed()
            return p
        def request_stop(self):pass
        def close(self):assert not app.input.held;closed.append(True)
    monkeypatch.setattr(factory,'create_capture',lambda settings:Capture())
    assert app.run()==3 and failure in app.last_error
    assert closed==[True] and not app.input.held


def test_pause_then_stop_signals_never_dispatch_again():
    app,b,clock,t,v,step=rig();enter_battle(app,t,step)
    step(.1,markers=['crashed']);app.pause();step(.1)
    assert app.state==RuntimeState.PAUSED and not app.input.held
    count=len(b.events);app.emergency_stop();step(.1,markers=['start'])
    assert len(b.events)==count

def test_live_guard_window_query_delay_cannot_make_old_frame_actionable():
    app,b,clock,t,v,step=rig();enter_battle(app,t,step)
    app.settings=replace(app.settings,input=replace(app.settings.input,enable_input=True))
    b.physical=True
    def slow_window(packet):clock.advance(.5);return True
    app.window_guard=slow_window
    intent=app.policy._intent('navigation','key','w',hold_s=1)
    assert not app._input_guard(intent)


@pytest.mark.parametrize('angle',[-10,10])
def test_search_nonwrap_sign_matches_active_legacy_pid(angle):
    import math
    from autonavy.telemetry import Enemy
    app,b,clock,t,v,step=rig();enter_battle(app,t,step)
    original=t.snapshot
    t.snapshot=lambda:replace(original(),enemies=(Enemy((.5+math.tan(math.radians(angle))*.1,.4)),))
    step(.2)
    assert ('move','pointer',(int(angle*.6),0)) in b.events

@pytest.mark.parametrize('stall', [0,.35])
def test_actual_run_caps_ready_source_cadence_without_catchup(monkeypatch,stall):
    from autonavy.capture import factory
    clock=Clock();v=Vision();t=Telemetry(clock);times=[];waits=[]
    settings=Settings()
    settings=replace(settings,runtime=replace(settings.runtime,tick_hz=10),capture=replace(settings.capture,max_frames=4))
    def wait(seconds):waits.append(seconds);clock.advance(seconds);return False
    app=Application(settings,telemetry=t,clock_ns=clock,vision=v,input_backend=RecordingBackend(),wait=wait)
    geometry=GeometrySnapshot((0,0,1280,720),(1280,720),(0,0,1280,720))
    origin=clock()
    class Capture:
        def start(self):pass
        def request_stop(self):pass
        def close(self):pass
        def read(self,timeout=None):
            assert timeout==.1
            times.append((clock()-origin)/1e9)
            if len(times)==1:clock.advance(stall)
            return FramePacket(np.zeros((720,1280,3),np.uint8),'BGR',len(times),1,clock(),geometry.geometry_id,geometry=geometry)
    monkeypatch.setattr(factory,'create_capture',lambda settings:Capture())
    assert app.run()==0
    assert times==pytest.approx([0,.1,.2,.3] if not stall else [0,.45,.55,.65])
    assert all(0<duration<=.1 for duration in waits)


def test_emergency_wakes_run_cadence_wait_before_another_read(monkeypatch):
    from autonavy.capture import factory
    app,b,clock,t,v,step=rig()
    def wait(seconds):app.emergency_stop();return True
    app._wait=wait
    geometry=GeometrySnapshot((0,0,1280,720),(1280,720),(0,0,1280,720))
    reads=[]
    class Capture:
        def start(self):pass
        def request_stop(self):pass
        def close(self):pass
        def read(self,timeout=None):
            reads.append(True)
            assert len(reads)==1,'emergency did not wake decision wait'
            return FramePacket(np.zeros((720,1280,3),np.uint8),'BGR',1,1,clock(),geometry.geometry_id,geometry=geometry)
    monkeypatch.setattr(factory,'create_capture',lambda settings:Capture())
    assert app.run()==0 and reads==[True]

def test_battle_producer_cannot_opt_out_of_required_player_prerequisite():
    app,b,clock,t,v,step=rig();enter_battle(app,t,step)
    intent=replace(app.policy._intent('navigation','axis','Z',50,1),requires_telemetry=False)
    t.valid=False
    assert not app._input_guard(intent)


@pytest.mark.parametrize('existing_hold', [False,True])
def test_review_pause_during_final_dispatch_guard_inhibits_acquisition_and_releases_existing_holds(existing_hold):
    app,b,clock,t,v,step=rig();enter_battle(app,t,step)
    app.settings=replace(app.settings,input=replace(app.settings.input,enable_input=True))
    b.physical=True
    app.window_guard=lambda packet:True
    if existing_hold:
        app.policy.emit('navigation','key','s',hold_s=10);app.input.tick()
    class Navigation:
        def tick(self,application,observations,snapshot):
            application.policy.emit('navigation','key','w',hold_s=10)
            def signal_once(packet):
                application.pause();application.window_guard=lambda packet:True
                return True
            application.window_guard=signal_once
        def reset(self):pass
    app.policy.navigation=Navigation()
    before=len(b.events);step(.1,markers=['lock'])
    assert ('key','w',1) not in b.events[before:]
    assert not app.input.held
    assert app.state==RuntimeState.PAUSED or app.pause_event.is_set()
    step(.1,markers=['lock'])
    assert app.state==RuntimeState.PAUSED
    # A fresh pause/resume signal still resumes menu handling.
    t.valid=False;app.pause();step(.1,markers=['start'])
    assert app.state==RuntimeState.QUEUEING


def test_review_pending_pause_rejects_guard_without_querying_window():
    app,b,clock,t,v,step=rig();enter_battle(app,t,step)
    app.settings=replace(app.settings,input=replace(app.settings.input,enable_input=True))
    b.physical=True
    app.window_guard=lambda packet: (_ for _ in ()).throw(AssertionError('window queried after pending pause'))
    intent=app.policy._intent('navigation','key','w',hold_s=1)
    app.pause()
    assert not app._input_guard(intent)


def test_review_persistent_start_retries_keep_original_queue_deadline():
    app,b,clock,t,v,step=rig()
    app.settings=replace(app.settings,runtime=replace(app.settings.runtime,queue_timeout_s=3))
    step(markers=['start']);deadline=app.policy.deadline
    for _ in range(2):
        step(1,markers=['start'])
        assert app.policy.deadline==deadline
    assert b.events.count(('key','enter',1))==3
    with pytest.raises(RuntimeError,match='queue deadline'):step(1,markers=['start'])


@pytest.mark.parametrize('cancellation',['pause','source','telemetry'])
def test_review_cancelled_recovery_deadline_never_delays_fresh_menu(cancellation):
    app,b,clock,t,v,step=rig();enter_battle(app,t,step)
    step(.1,markers=['crashed'])
    assert app.policy.next_action>clock()+60_000_000_000
    if cancellation=='pause':
        app.pause();step(.1)
        assert app.state==RuntimeState.PAUSED
        t.valid=False;app.pause();step(.1,markers=['start'])
    elif cancellation=='telemetry':
        t.valid=False;step(.1)
        # Loss of frame freshness cancels the abandoned player wait back to menu.
        step(.5,fresh=False);step(.1,markers=['start'])
    else:
        t.valid=False
        packet=replace(app.last_frame,source_generation=2,publication_id=99,received_at_ns=clock())
        app.tick(packet)
        step(.5,fresh=False);step(.1,markers=['start'])
    assert app.policy.stage=='queue'
    assert ('key','enter') in app.input.held
