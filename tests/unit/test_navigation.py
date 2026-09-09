"""Ordered topology, native protocol and independent controller boundaries."""
from dataclasses import FrozenInstanceError
import math
from types import SimpleNamespace
import numpy as np
import pytest


def test_cursor_immutable_and_crossing_cannot_skip_contiguous_waypoints():
    from autonavy.navigation.route import RouteCursor
    points = [(0,0), (1,0), (1,1), (0,0), (-1,0)]
    cursor = RouteCursor(points)
    points.append((9,9))
    progressed = cursor.advance((0,0), .1)
    assert progressed.index == 1 and progressed.target(.5) == (1,.5)
    assert cursor.index == 0 and len(cursor.points) == 5
    assert progressed.points is cursor.points
    assert progressed.advance((0,0), .1).index == 1
    assert progressed.advance((1,0), .1).index == 2
    with pytest.raises(FrozenInstanceError): cursor.index = 3
    assert RouteCursor([]).target(.1) is None
    assert RouteCursor([(0,0)]).advance((0,0),.1).done


@pytest.mark.parametrize('target,current,expected', [(1,359,2),(359,1,-2),(180,0,-180),(0,180,-180),(3,3,0),(-1,1,-2)])
def test_shortest_signed_angular_error(target,current,expected):
    from autonavy.navigation.control import angular_error
    assert angular_error(target,current) == expected


def test_pid_integral_derivative_clamps_and_reset():
    from autonavy.navigation.control import PID
    p = PID(1,2,3,limit=100,integral_limit=2,max_dt_s=1)
    assert p.update(2,.1) == 2
    assert p.update(3,.5) == 12  # P3 + I3 + D6.
    assert p.update(3,1) == 7   # Integral limited to 2.
    p.reset()
    assert p.update(3,.5) == 3
    assert PID(20,0,0,limit=10).update(2,.1)==10


@pytest.mark.parametrize('dt', [0,-1,float('nan'),float('inf'),2])
def test_invalid_dt_resets_without_spike(dt):
    from autonavy.navigation.control import PID
    p=PID(1,1,1,limit=100,max_dt_s=1)
    p.update(4,.1); p.update(5,.1)
    assert p.update(20,dt)==0
    assert p.update(4,.1)==4
    assert p.update(float('nan'),.1)==0
    assert p.update(4,.1)==4


def test_controller_states_and_source_boundary_signs():
    from autonavy.navigation.control import Controllers
    from autonavy.config import ControlSettings
    c=Controllers(ControlSettings())
    assert c.pixel(10,-10,.1)==pytest.approx((6,-6))
    assert c.search(90,80,.1)==6
    assert c.heading(90,80,.1)==-5
    c.search_pid.reset()  # A changed target starts a fresh angular state.
    assert c.search(1,359,.1)>0
    c.reset()
    assert c.heading(359,1,.1)==1
    assert c.pixel(10,-10,.1)==pytest.approx((6,-6))


class NativeModule:
    def __init__(self,result): self.result=result; self.calls=0; self.tiles=[]
    def MapGrid(self,h,w):
        self.size=(h,w)
        return SimpleNamespace(set_grid=lambda x,y,t:self.tiles.append((x,y,t)))
    def Point(self,x,y): return (x,y)
    def Jps(self,origin,goal,grid):
        self.calls+=1
        return SimpleNamespace(Process=lambda:self.result)


def test_native_reverse_once_endpoints_jump_ignored_and_black_obstacles():
    from autonavy.navigation.native import NativePathfinder
    module=NativeModule(([],[(3,1),(2,1)],[(2,1)])); loads=[]
    adapter=NativePathfinder(lambda: loads.append(1) or module)
    assert loads==[]
    grid=np.full((4,6,3),255,np.uint8); grid[3,5]=0
    assert adapter.find(grid,(1,1),(4,1)) == ((1,1),(2,1),(3,1),(4,1))
    assert module.size==(4,6) and (5,3,'obstacle') in module.tiles


def test_native_adjacent_empty_unreachable_samepoint_and_bad_topology():
    from autonavy.navigation.native import NativePathfinder
    grid=np.full((4,6,3),255,np.uint8)
    module=NativeModule(([],[],[])); adapter=NativePathfinder(lambda:module)
    assert adapter.find(grid,(1,1),(1,1))==((1,1),) and module.calls==0
    assert adapter.find(grid,(1,1),(2,1))==((1,1),(2,1))
    module.result=(None,None,None)
    assert adapter.find(grid,(1,1),(4,1)) is None
    for bad in (([],[],[]),([],[(2,99)],[]),([],[(2.5,1)],[]),([],[(3,1),(1,2)],[]),(None,[(3,1),(2,1)],None)):
        module.result=bad
        with pytest.raises(ValueError): adapter.find(grid,(1,1),(4,1))


def test_angular_derivative_wrap_does_not_spike_at_half_turn():
    from autonavy.navigation.control import PID
    p=PID(0,0,1,limit=100,angular=True)
    assert p.update(179,.1)==0
    assert p.update(-179,.1)==pytest.approx(20)


def test_legacy_preparation_and_rectangular_normalized_mapping():
    import cv2
    from autonavy.navigation.native import prepare_map,plan_encoded
    # BGR blue water survives as white; a solid white island becomes black.
    image=np.full((512,1024,3),(200,100,30),np.uint8)
    image[200:300,400:600]=255
    grid=prepare_map(image)
    assert grid.shape==(128,256,3)
    assert tuple(grid[10,10])==(255,255,255)
    assert tuple(grid[60,125])==(0,0,0)
    class Adapter:
        def find(self,processed,origin,goal):
            assert processed.shape==(128,256,3)
            assert origin==(64,32) and goal==(192,96)
            return origin,goal
    encoded=cv2.imencode('.png',image)[1].tobytes()
    assert plan_encoded(encoded,(.25,.25),(.75,.75),Adapter())==((.25,.25),(.75,.75))


def test_pure_compatibility_cursor_preserves_caller_data_and_requires_explicit_endpoints(monkeypatch):
    from toolkit import process_path
    path=[(0,0),(1,0),(1,1),(0,0)]
    point=process_path.get_next_point(path,(0,0))
    assert point==(1,0) and path==[(0,0),(1,0),(1,1),(0,0)]
    with pytest.raises(ValueError,match='endpoints'):
        process_path.pathfinding(np.zeros((8,8,3),np.uint8))


def test_native_rejects_obstacle_endpoints_without_loading_extension():
    from autonavy.navigation.native import NativePathfinder
    def forbidden(): raise AssertionError('Native should not load for blocked endpoint')
    grid=np.full((4,4,3),255,np.uint8); grid[1,1]=0
    assert NativePathfinder(forbidden).find(grid,(1,1),(2,2)) is None


def test_legacy_imports_and_default_application_do_not_start_devices_or_planner():
    import subprocess,sys
    code='''
import importlib.abc,sys,threading,multiprocessing.process
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname in {'toolkit.way_search','pyvjoy','dxcam','requests','keyboard','mouse'}:
            raise AssertionError('Forbidden import: '+fullname)
sys.meta_path.insert(0,Guard())
def forbidden(*args,**kwargs): raise AssertionError('Unexpected worker startup')
threading.Thread.start=forbidden
multiprocessing.process.BaseProcess.start=forbidden
import pilot,toolkit.process_path
from autonavy.app import Application
from autonavy.config import Settings
from autonavy.telemetry import OfflineTelemetry
app=Application(Settings(),telemetry=OfflineTelemetry())
app.close()
'''
    result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+result.stderr
