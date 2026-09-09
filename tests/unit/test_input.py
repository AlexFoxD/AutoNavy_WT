"""Deterministic controller contract; every backend here records only."""
import importlib.util
from dataclasses import replace
import pytest


def api():
    assert importlib.util.find_spec('autonavy.input'), 'coordinated input package is missing'
    from autonavy.input.controller import InputController, InputIntent, RecordingBackend
    return InputController, InputIntent, RecordingBackend


class Clock:
    now = 0
    def __call__(self): return self.now
    def advance(self, seconds): self.now += int(seconds * 1e9)


def rig(**kwargs):
    Controller, Intent, Backend = api()
    clock = Clock()
    backend = Backend()
    controller = Controller(backend, clock_ns=clock, guard=kwargs.pop('guard', lambda intent: True), **kwargs)
    controller.set_mode('battle')
    def intent(owner='navigation', action='key', resource='w', value=1, duration=1, **changes):
        return Intent(owner=owner, action=action, resource=resource, value=value,
                      created_at_ns=clock(), deadline_ns=clock()+250_000_000,
                      duration_ns=int(duration*1e9), generation=controller.generation(owner),
                      **changes)
    return controller, backend, clock, intent


def test_expiry_ticks_without_new_frame_and_old_release_cannot_release_new_owner():
    c,b,t,i = rig()
    c.submit(i()); c.tick()
    t.advance(.2)
    c.cancel('navigation')
    c.submit(i(owner='recovery', duration=3)); c.tick()
    t.advance(.8); c.tick()
    assert ('key', 'w') in c.held
    t.advance(2.2); c.tick()
    assert not c.held
    assert b.events == [('key','w',1), ('key','w',0), ('key','w',1), ('key','w',0)]


def test_recovery_preempts_navigation_and_ui_excludes_battle():
    c,b,t,i = rig()
    c.submit(i()); c.tick()
    c.set_mode('recovery')
    assert not c.held
    assert not c.submit(i())
    assert c.submit(i(owner='recovery', resource='s'))
    c.tick(); c.set_mode('ui')
    assert not c.held and not c.submit(i(owner='recovery'))
    assert c.submit(i(owner='ui', resource='enter', requires_telemetry=False))
    c.tick()
    assert ('key','enter') in c.held


@pytest.mark.parametrize('reason', ['focus','geometry','profile','frame','source','telemetry','session','optin'])
def test_guard_is_rechecked_before_dispatch_and_for_existing_holds(reason):
    allowed = [True]
    c,b,t,i = rig(guard=lambda intent: allowed[0])
    c.submit(i()); allowed[0] = False; c.tick()
    assert not b.events
    allowed[0] = True; c.submit(i()); c.tick()
    allowed[0] = False; c.tick()
    assert not c.held and b.events[-1] == ('key','w',0)


def test_emergency_latches_and_releases_every_actually_held_resource():
    c,b,t,i = rig()
    for key in ('w','s','x','shift','esc','up','down','enter'):
        c.submit(i(resource=key))
    c.submit(i(action='mouse',resource='left'))
    c.submit(i(action='axis',resource='Z',value=100))
    c.tick(); c.emergency.set(); c.tick()
    assert not c.held and not c.submit(i())
    assert ('axis','Z',0) in b.events


def test_release_failures_attempt_others_and_retain_retryable_held_state():
    c,b,t,i = rig()
    for key in ('w','s'): c.submit(i(resource=key))
    c.tick()
    original = b.dispatch
    def fail(action, resource, value):
        if resource == 'w' and value == 0: raise RuntimeError('release failed')
        original(action,resource,value)
    b.dispatch = fail
    with pytest.raises(RuntimeError, match='release failed'): c.release_all()
    assert set(c.held) == {('key','w')} and ('key','s',0) in b.events
    b.dispatch = original
    c.release_all()
    assert not c.held


def test_bounded_coalescing_priority_and_generation_cancellation():
    c,b,t,i = rig(max_pending=2)
    for value in range(100): assert c.submit(i(action='move',resource='pointer',value=(value,0)))
    assert c.pending_count == 1
    c.submit(i(resource='x')); assert not c.submit(i(resource='s'))
    c.cancel('navigation'); c.tick()
    assert not b.events
    stale = i(); c.cancel('navigation'); assert not c.submit(stale)


def test_dispatch_error_retains_uncertain_press_for_cleanup():
    c,b,t,i = rig()
    def fail(*args): raise RuntimeError('transport failed')
    b.dispatch = fail
    c.submit(i())
    with pytest.raises(RuntimeError): c.tick()
    assert ('key','w') in c.held


def test_windows_transport_signed_wheel_negative_desktop_and_failsafe():
    api()
    from autonavy.input.windows import WindowsBackend
    class Pdi:
        FAILSAFE = True
        PAUSE = .1
        def failSafeCheck(self): events.append(('failsafe',))
        def keyDown(self,key): events.append(('down',key))
        def keyUp(self,key): events.append(('up',key))
    class Win:
        def mouse_event(self,*args): events.append(('mouse_event',*args))
        def SetCursorPos(self,xy): events.append(('position',xy))
    events=[]
    pdi=Pdi()
    backend=WindowsBackend(pdi=pdi, win32=Win(), vjoy_factory=lambda: None,
                           pointer=type('Pointer',(),{'move':lambda self,x,y:events.append(('position',(x,y)))})())
    backend.start()
    for value in (2,-3,0): backend.dispatch('wheel','wheel',value)
    backend.dispatch('position','pointer',(-1500,100))
    assert ('mouse_event',0x0800,0,0,-360,0) in events
    assert ('mouse_event',0x0800,0,0,240,0) in events
    assert ('position',(-1500,100)) in events
    assert len([e for e in events if e[0]=='mouse_event']) == 2
    assert pdi.FAILSAFE is True and ('failsafe',) in events

def test_live_geometry_guard_requeries_window_even_without_new_packet():
    from autonavy.input.windows import LiveWindowGuard
    from autonavy.config import Settings
    from autonavy.geometry import GeometrySnapshot
    from types import SimpleNamespace
    g=GeometrySnapshot((-1500,0,-220,720),(1280,720),(0,0,1280,720),window_handle=42)
    current=[g]; focus=[42]; calls=[]
    class Geometry:
        def snapshot(self,size): calls.append(size); return current[0]
    guard=LiveWindowGuard(Settings(),geometry=Geometry(),foreground=lambda:focus[0])
    packet=SimpleNamespace(geometry=g,geometry_id=g.geometry_id)
    assert guard(packet)
    current[0]=replace(g,client_rect=(-1490,0,-210,720))
    assert not guard(packet)
    current[0]=g; focus[0]=41
    assert not guard(packet) and len(calls)==3


def test_owned_hotkeys_callbacks_only_signal_and_partial_registration_is_removable():
    from autonavy.input.windows import Hotkeys
    from autonavy.config import InputSettings
    callbacks={}; removed=[]
    class Keyboard:
        def add_hotkey(self,key,callback): callbacks[key]=callback; return key+'-owned'
        def remove_hotkey(self,handle): removed.append(handle)
    signaled=[]
    hooks=Hotkeys(InputSettings(),lambda:signaled.append('stop'),lambda:signaled.append('pause'),keyboard=Keyboard())
    hooks.start(); assert signaled==[]
    callbacks['f8'](); callbacks['f9']()
    assert signaled==['stop','pause']
    hooks.close(); hooks.close()
    assert removed==['f8-owned','f9-owned']


def test_axis_startup_neutralizes_all_configured_resources_and_release_is_retryable():
    Controller,Intent,Backend=api()
    class Device(Backend):
        neutral_resources=tuple(('axis',axis) for axis in ('X','Y','Z','RY'))+tuple(('button',str(n)) for n in range(1,9))
    backend=Device(); controller=Controller(backend,guard=lambda i:True)
    controller.start()
    assert backend.events==[(a,r,0) for a,r in backend.neutral_resources]
    assert not controller.held


def test_legacy_input_and_thread_modules_have_no_raw_hardware_or_kill_paths():
    from pathlib import Path
    for file in ('toolkit/MnK.py','toolkit/joystick.py','toolkit/th_pool.py','dxin.py'):
        text=Path(file).read_text(encoding="utf-8")
        assert 'PyThreadState_SetAsyncExc' not in text
        assert 'FAILSAFE = False' not in text
        assert 'import pydirectinput' not in text and 'import pyvjoy' not in text


def test_release_bypasses_only_failsafe_decorator_and_rejects_unsent_events():
    from autonavy.input.windows import WindowsBackend
    import functools
    events=[]
    def checked(func):
        @functools.wraps(func)
        def wrapped(*args,**kwargs): raise RuntimeError('failsafe corner')
        return wrapped
    class Pdi:
        PAUSE=.1; FAILSAFE=True
        def failSafeCheck(self): raise RuntimeError('failsafe corner')
        @checked
        def keyUp(self,key,_pause=True): events.append(key); return True
        def keyDown(self,key): return False
    pdi=Pdi(); backend=WindowsBackend(pdi=pdi,win32=object())
    backend.start(); backend.dispatch('key','w',0)
    assert events==['w'] and pdi.FAILSAFE
    pdi.failSafeCheck=lambda:None
    with pytest.raises(RuntimeError,match='input'): backend.dispatch('key','s',1)


def test_physical_cursor_uses_signed_physical_coordinates_and_checks_failure():
    from autonavy.input.windows import PhysicalPointer
    class API:
        def SetPhysicalCursorPos(self,x,y): calls.append((x,y)); return success[0]
    calls=[]; success=[True]
    pointer=PhysicalPointer(api=API())
    pointer.move(-1800,125)
    assert calls==[(-1800,125)]
    success[0]=False
    with pytest.raises(OSError): pointer.move(-1800,125)


def test_vjoy_queried_ranges_units_buttons_and_void_release():
    from autonavy.input.windows import OwnedVJoy
    class API:
        def AcquireVJD(self,device): calls.append(('acquire',device)); return True
        def GetVJDAxisMin(self,device,axis,out): out._obj.value=1; return True
        def GetVJDAxisMax(self,device,axis,out): out._obj.value=32768; return True
        def GetVJDAxisExist(self,device,axis): return True
        def GetVJDButtonNumber(self,device): return 8
        def SetAxis(self,value,device,axis): calls.append(('axis',value,device,axis)); return True
        def SetBtn(self,value,device,button): calls.append(('button',value,device,button)); return True
        def RelinquishVJD(self,device): calls.append(('release',device))
    calls=[]; joy=OwnedVJoy(1,api=API())
    for value in (-200,0,200): joy.axis('Z',value,16384)
    joy.axis('RY',0,16384); joy.button(8,0); joy.close(); joy.close()
    assert calls==[('acquire',1),('axis',1,1,0x32),('axis',16384,1,0x32),
                   ('axis',32768,1,0x32),('axis',1,1,0x34),('button',0,1,8),('release',1)]


def test_guard_is_rechecked_after_preemption_release_changes_focus():
    allowed=[True]
    c,b,t,i=rig(guard=lambda intent:allowed[0])
    c.submit(i()); c.tick()
    original=b.dispatch
    def release_focus(action,resource,value):
        original(action,resource,value)
        if value==0: allowed[0]=False
    b.dispatch=release_focus
    c.submit(i(owner='recovery',priority=100)); c.tick()
    assert b.events==[('key','w',1),('key','w',0)]

def test_hotkey_close_before_start_and_registration_race_cannot_leave_hooks():
    from autonavy.input.windows import Hotkeys
    from autonavy.config import InputSettings
    class Keyboard:
        def add_hotkey(self,*args): raise AssertionError('hook created after close')
    hooks=Hotkeys(InputSettings(),lambda:None,lambda:None,keyboard=Keyboard())
    hooks.close();hooks.start()


def test_controller_failed_neutralization_does_not_relinquish_and_close_retries():
    c,b,t,i=rig();c.submit(i());c.tick()
    original=b.dispatch;closed=[]
    b.close=lambda:closed.append(True)
    b.dispatch=lambda *args: (_ for _ in ()).throw(RuntimeError('release unavailable'))
    with pytest.raises(RuntimeError,match='release unavailable'): c.close()
    assert not closed and c.held
    b.dispatch=original;c.close()
    assert closed==[True] and not c.held


def test_vjoy_missing_axis_rejected_before_acquisition():
    from autonavy.input.windows import OwnedVJoy
    class API:
        def GetVJDAxisExist(self,device,axis): return False
        def AcquireVJD(self,device): raise AssertionError('invalid device acquired')
    with pytest.raises(RuntimeError,match='axis'): OwnedVJoy(1,api=API())


def test_owned_hotkey_registration_failure_removes_only_successful_handles():
    from autonavy.input.windows import Hotkeys
    from autonavy.config import InputSettings
    removed=[]
    class Keyboard:
        def add_hotkey(self,key,callback):
            if key=='f9':raise RuntimeError('registration failed')
            return 'owned-f8'
        def remove_hotkey(self,handle):removed.append(handle)
    hooks=Hotkeys(InputSettings(),lambda:None,lambda:None,keyboard=Keyboard())
    with pytest.raises(RuntimeError,match='registration failed'):hooks.start()
    hooks.close();assert removed==['owned-f8']

def test_search_defaults_preserve_the_active_fire_controller_not_unused_pilot_gains():
    from autonavy.config import load_settings
    for settings in (load_settings(),load_settings('configs/default.toml')):
        c=settings.control
        assert (c.search_kp,c.search_ki,c.search_kd,c.search_limit)==(.6,0,.02,30)

def test_recording_history_is_bounded_and_reports_dropped_events():
    _,_,Backend=api()
    backend=Backend(max_events=3)
    for n in range(7):backend.dispatch('move','pointer',(n,0))
    assert backend.events==[('move','pointer',(n,0)) for n in range(4,7)]
    assert backend.total_events==7 and backend.dropped_events==4


def test_slow_guard_cannot_dispatch_after_intent_deadline():
    c,b,t,i=rig()
    def guard(intent):t.advance(.3);return True
    c.guard=guard;c.submit(i());c.tick()
    assert not b.events

def test_physical_owner_neutralizes_vjoy_before_relinquish_and_retries_failed_axis():
    from autonavy.input.windows import WindowsBackend
    from autonavy.config import InputSettings
    c,unused,t,i=rig();events=[];fail=[False]
    class Pdi:
        PAUSE=.1
        def failSafeCheck(self):pass
    class Joy:
        def axis(self,name,value,neutral):
            events.append(('axis',name,value))
            if name=='Z' and value==0 and fail[0]:raise RuntimeError('axis neutral failed')
        def button(self,name,value):events.append(('button',name,value))
        def close(self):events.append(('relinquish',))
    backend=WindowsBackend(InputSettings(),pdi=Pdi(),win32=object(),vjoy_factory=Joy)
    c.backend=backend;c.start();c.submit(i(action='axis',resource='Z',value=50));c.tick()
    fail[0]=True
    with pytest.raises(RuntimeError,match='axis neutral failed'):c.close()
    assert ('relinquish',) not in events
    fail[0]=False;c.close()
    assert events[-2:]==[('axis','Z',0),('relinquish',)]


def test_zero_release_intent_cannot_release_another_owners_hold():
    c,b,t,i=rig();c.submit(i());c.tick()
    c.submit(i(owner='aim',value=0));c.tick()
    assert ('key','w') in c.held and b.events==[('key','w',1)]

def test_zero_wheel_is_a_true_noop_even_at_failsafe_corner():
    from autonavy.input.windows import WindowsBackend
    class Pdi:
        def failSafeCheck(self):raise AssertionError('zero wheel consulted hardware')
    WindowsBackend(pdi=Pdi(),win32=object()).dispatch('wheel','wheel',0)

def test_mode_round_trip_invalidates_issued_but_not_yet_submitted_intents():
    c,b,t,i=rig();stale=i()
    c.set_mode('ui');c.set_mode('battle')
    assert not c.submit(stale)
    assert c.submit(i())
