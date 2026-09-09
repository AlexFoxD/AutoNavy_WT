"""Actual Application/BattlePolicy/RecordingBackend consume route completions."""
from dataclasses import replace
import math
import pytest
from test_battle_cycle import rig,enter_battle
from autonavy.telemetry import MapImage,Player,Enemy


class Planner:
    def __init__(self): self.requests=[]; self.result=None; self.resets=0; self.closed=False; self.stopped=False
    def submit(self,request):
        if not self.requests or request.key!=self.requests[-1].key:self.requests.append(request)
    def poll(self): result=self.result; self.result=None; return result
    def reset(self): self.resets+=1
    def close(self): self.closed=True
    def request_stop(self): self.stopped=True


def navigation_rig():
    from autonavy.navigation.pilot import Navigation
    app,backend,clock,t,vision,step=rig(); enter_battle(app,t,step)
    original=t.snapshot
    t.position=(.5,.5); t.zones=((.7,.5),); t.image_valid=True
    t.snapshot=lambda:replace(original(),player=Player(t.position,0,-1),zones=t.zones)
    t.map_image=lambda:MapImage(b'cached bytes',t.snapshot().metadata.key,t.generation,clock()) if t.image_valid else None
    planner=Planner(); app.policy.navigation=Navigation(app.settings.control,planner=planner)
    return app,backend,clock,t,vision,step,planner


def complete(planner,points=((.5,.5),(.51,.5),(.52,.5),(.7,.5)),key=None):
    from autonavy.navigation.planner import PlanResult
    planner.result=PlanResult(planner.requests[-1].key if key is None else key,points)


def test_default_application_wires_navigation_and_actual_tick_emits_negative_heading_axis():
    from autonavy.navigation.pilot import Navigation
    app,*_=rig()
    assert isinstance(app.policy.navigation,Navigation)
    app.close()
    app,b,clock,t,v,step,p=navigation_rig()
    try:
        step(.1)
        assert len(p.requests)==1 and p.requests[0].data==b'cached bytes'
        assert p.requests[0].origin==(.5,.5) and p.requests[0].destination==(.7,.5)
        complete(p); step(.1)
        assert ('axis','Z',-45.0) in b.events
        assert ('axis','Z') in app.input.held
        step(.1); assert len(p.requests)==1
        app.pause(); step(.1)
        assert not app.input.held and p.resets>0
        assert app.policy.navigation.cursor is None
    finally: app.close()
    assert p.closed


@pytest.mark.parametrize('change',['generation','map','destination','source','geometry','missing_map'])
def test_stale_result_is_not_retagged_with_current_identity(change):
    app,b,clock,t,v,step,p=navigation_rig()
    try:
        step(.1); old=p.requests[-1].key
        if change=='generation': t.generation+=1
        elif change=='map':
            original=t.snapshot
            t.snapshot=lambda:replace(original(),metadata=replace(original().metadata,map_max=(200,200)))
        elif change=='destination': t.zones=((.2,.2),)
        elif change=='source': app.last_frame=replace(app.last_frame,source_generation=2)
        elif change=='geometry':
            geometry=replace(app.last_frame.geometry,window_handle=43)
            app.last_frame=replace(app.last_frame,geometry=geometry,geometry_id=geometry.geometry_id)
        elif change=='missing_map': t.image_valid=False
        complete(p,key=old)
        count=len(b.events)
        # Source/geometry invalidation is detected against the existing observation packet.
        step(.1,fresh=change not in {'source','geometry'})
        assert not any(e[0]=='axis' and e[2]!=0 for e in b.events[count:])
    finally: app.close()


def test_deviation_replans_once_and_destination_arrival_neutralizes():
    app,b,clock,t,v,step,p=navigation_rig()
    try:
        step(.1); complete(p); step(.1)
        t.position=(.5,.8); step(.1)
        assert len(p.requests)==2 and not app.input.held.get(('axis','Z'))
        step(.1); assert len(p.requests)==2
        complete(p,((.5,.8),(.7,.5))); step(.1)
        t.position=(.7,.5); step(.1)
        assert not app.input.held.get(('axis','Z'))
        step(.1); assert len(p.requests)==2
    finally: app.close()


def test_fresh_service_change_during_poll_cannot_emit_stale_steering():
    app,b,clock,t,v,step,p=navigation_rig()
    try:
        step(.1); complete(p)
        poll=p.poll
        def changed():
            result=poll(); t.generation+=1; return result
        p.poll=changed
        count=len(b.events); step(.1)
        assert not any(e[0]=='axis' and e[2]!=0 for e in b.events[count:])
    finally: app.close()


def test_cleanup_releases_axis_before_planner_wait_and_reports_shared_failure():
    app,b,clock,t,v,step,p=navigation_rig()
    step(.1); complete(p); step(.1)
    def broken():
        assert not app.input.held
        assert ('axis','Z',0) in b.events
        raise RuntimeError('planner cleanup failed')
    p.close=broken
    for _ in range(2):
        with pytest.raises(RuntimeError,match='planner cleanup failed'): app.close()


def test_pixel_pid_uses_derivative_and_resets_on_search_and_pause():
    app,b,clock,t,v,step=rig(); enter_battle(app,t,step)
    try:
        original=v.observe
        displacement=[10]
        def offset(packet,selection=None):
            observations=original(packet,selection)
            if 'aim' in observations.matches:
                match=observations.matches['aim']
                dx=displacement[0]
                observations=replace(observations,matches={'aim':replace(match,frame_box=(638+dx,358,642+dx,362))})
            return observations
        v.observe=offset
        step(.1,markers=['aim'])
        assert ('move','pointer',(6,0)) in b.events
        assert app.policy.controllers.aim_x.previous==10
        displacement[0]=20
        step(.1,markers=['aim'])
        assert b.events[-1]==('move','pointer',(14,0))  # P12 + D2.
        step(.1)
        assert app.policy.controllers.aim_x.previous is None
        app.pause(); step(.1)
        assert app.policy.controllers.search_pid.previous is None
    finally: app.close()


@pytest.mark.parametrize('available,degrees',[(False,None),(True,float('nan'))])
def test_missing_turret_observation_resets_search_without_mouse_movement(available,degrees):
    app,b,clock,t,v,step=rig(); enter_battle(app,t,step)
    original=t.snapshot
    t.snapshot=lambda:replace(original(),enemies=(Enemy((.6,.4)),))
    original_observe=v.observe
    def observe(packet,selection=None):
        observations=original_observe(packet,selection)
        return replace(observations,degree=replace(observations.degree,available=available,degrees=degrees))
    v.observe=observe
    try:
        count=len(b.events); step(.1)
        assert not any(event[0]=='move' for event in b.events[count:])
        assert app.policy.controllers.search_pid.previous is None
    finally: app.close()


def test_stop_resets_all_pid_states_and_signals_planner_before_waits():
    app,b,clock,t,v,step,p=navigation_rig()
    step(.1); complete(p); step(.1)
    app.policy.controllers.pixel(4,4,.1)
    app.policy.controllers.search(20,0,.1)
    app.stop(); app.tick()
    assert p.stopped
    assert app.policy.controllers.aim_x.previous is None
    assert app.policy.controllers.search_pid.previous is None
    assert app.policy.navigation.controllers.heading_pid.previous is None
    app.close()


def test_waypoint_change_resets_heading_integral_and_derivative():
    app,b,clock,t,v,step,p=navigation_rig()
    try:
        t.zones=((.55,.55),)
        step(.1); complete(p,((.5,.5),(.55,.5),(.55,.55))); step(.1)
        step(.1)
        assert app.policy.navigation.controllers.heading_pid.integral!=0
        t.position=(.55,.5); step(.1)
        assert app.policy.navigation.controllers.heading_pid.integral==0
        assert ('axis','Z',90.0) in b.events
    finally: app.close()


def test_player_moved_during_planning_rejects_departed_origin_before_steering():
    app,b,clock,t,v,step,p=navigation_rig()
    try:
        step(.1); t.position=(.5,.8); complete(p)
        count=len(b.events); step(.1)
        assert not any(e[0]=='axis' and e[2]!=0 for e in b.events[count:])
        step(.1)
        assert len(p.requests)==2 and p.requests[-1].origin==(.5,.8)
    finally: app.close()
