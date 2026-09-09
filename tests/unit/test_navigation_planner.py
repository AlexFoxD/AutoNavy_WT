"""Native isolation uses owned children, bounded slots and stale-result rejection."""
import threading
import time
import pytest


def request(key='one'):
    from autonavy.navigation.planner import PlanRequest
    return PlanRequest((key,),b'encoded',(.1,.1),(.2,.2))


def until(predicate,timeout=3):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        result=predicate()
        if result: return result
        time.sleep(.005)
    raise AssertionError('Planner did not reach expected state')


class Jobs:
    def __init__(self): self.jobs=[]; self.result=None
    def __call__(self,req):
        job=Job(req,self); self.jobs.append(job); return job


class Job:
    def __init__(self,req,owner): self.req=req; self.owner=owner; self.closed=False
    def poll(self):
        from autonavy.navigation.planner import PlanResult
        if self.owner.result is None: return None
        return PlanResult(self.req.key,self.owner.result,None)
    def close(self): self.closed=True


def test_latest_request_replaces_busy_job_and_discards_its_result():
    from autonavy.navigation.planner import PlanningService
    jobs=Jobs(); service=PlanningService(job_factory=jobs,timeout_s=1,join_timeout_s=.3)
    try:
        service.submit(request('old')); until(lambda:len(jobs.jobs)==1)
        service.submit(request('new'))
        until(lambda:len(jobs.jobs)==2)
        assert jobs.jobs[0].closed
        jobs.result=((.1,.1),(.2,.2))
        result=until(service.poll)
        assert result.key==('new',)
        assert service.poll() is None
        service.submit(request('new')); time.sleep(.04)
        assert len(jobs.jobs)==2  # A completed key is not rebuilt every tick.
    finally: service.close()
    assert all(j.closed for j in jobs.jobs)
    with pytest.raises(RuntimeError): service.submit(request())


def test_no_route_has_bounded_attempts_and_backoff():
    from autonavy.navigation.planner import PlanningService,PlanResult
    starts=[]
    class Failed:
        def __init__(self,req): self.req=req; starts.append(time.monotonic())
        def poll(self): return PlanResult(self.req.key,None,'unreachable')
        def close(self): pass
    service=PlanningService(job_factory=Failed,attempts=3,backoff_s=.04,join_timeout_s=.3)
    try:
        service.submit(request())
        result=until(service.poll)
        assert result.points is None and result.error=='unreachable'
        assert len(starts)==3 and all(b-a>=.035 for a,b in zip(starts,starts[1:]))
        service.submit(request()); time.sleep(.08)
        assert len(starts)==3
    finally: service.close()


def test_timeout_reset_and_close_interrupt_pending_work():
    from autonavy.navigation.planner import PlanningService
    jobs=Jobs(); service=PlanningService(job_factory=jobs,attempts=1,timeout_s=.04,join_timeout_s=.3)
    service.submit(request()); result=until(service.poll)
    assert result.points is None and 'timeout' in result.error
    service.submit(request('reset')); until(lambda:len(jobs.jobs)==2)
    service.reset(); jobs.result=((.1,.1),(.2,.2))
    until(lambda:jobs.jobs[1].closed)
    assert service.poll() is None
    service.close(); service.close()


def hanging_child(req,points,count,error):
    # Native stand-in: never consults a stop flag; must be reclaimed by its owner.
    while True: time.sleep(1)


def test_real_process_hang_is_reclaimed_on_close():
    from autonavy.navigation.planner import NativeJob,PlanningService
    jobs=[]
    def factory(req):
        job=NativeJob(req,join_timeout_s=.5,worker=hanging_child)
        jobs.append(job)
        return job
    service=PlanningService(job_factory=factory,join_timeout_s=1,timeout_s=30)
    service.submit(request()); until(lambda:bool(jobs))
    started=time.monotonic(); service.close()
    assert time.monotonic()-started<1.5
    # Closing the Process after reaping also releases its OS sentinel/handles.
    with pytest.raises(ValueError,match='closed'): jobs[0].process.is_alive()


def test_cleanup_failure_is_shared_and_no_new_child_is_spawned():
    from autonavy.navigation.planner import PlanningService
    jobs=Jobs()
    def factory(req):
        job=jobs(req)
        def fail(): raise RuntimeError('child remained alive')
        job.close=fail
        return job
    service=PlanningService(job_factory=factory,timeout_s=.03,attempts=3,join_timeout_s=.3)
    service.submit(request()); until(lambda:bool(jobs.jobs))
    time.sleep(.08)
    with pytest.raises(RuntimeError,match='child remained alive'): service.close()
    with pytest.raises(RuntimeError,match='child remained alive'): service.close()
    assert len(jobs.jobs)==1


def test_native_adapter_and_supervised_encoded_route_on_exact_supported_host():
    import platform,struct,subprocess,sys
    if sys.platform!='win32' or sys.version_info[:2]!=(3,11) or struct.calcsize('P')!=8:
        pytest.skip('Bundled native ABI requires Windows x64 CPython 3.11')
    code='''
import json,sys,time,cv2,numpy as np
from autonavy.navigation.native import NativePathfinder
from autonavy.navigation.planner import PlanRequest,PlanningService
adapter=NativePathfinder()
grid=np.full((8,8,3),255,np.uint8)
assert adapter.find(grid,(1,1),(6,1))==tuple((x,1) for x in range(1,7))
assert adapter.find(grid,(1,1),(2,1))==((1,1),(2,1))
assert adapter.find(grid,(1,1),(1,1))==((1,1),)
grid[:,4]=0
assert adapter.find(grid,(1,1),(6,1)) is None
data=cv2.imencode('.png',np.full((512,512,3),(200,100,30),np.uint8))[1].tobytes()
service=PlanningService(attempts=1,timeout_s=5,join_timeout_s=1)
try:
    service.submit(PlanRequest(('native-smoke',),data,(.125,.125),(.25,.25)))
    deadline=time.monotonic()+8
    result=None
    while result is None and time.monotonic()<deadline:
        result=service.poll()
        time.sleep(.01)
    assert result is not None and result.error is None,result
    assert len(result.points)==17,result
    assert result.points[0]==(.125,.125) and result.points[-1]==(.25,.25)
    print(json.dumps({'python':sys.version.split()[0],'adapter_cases':4,'encoded_grid':'128x128','route_points':len(result.points)}))
finally: service.close()
'''
    result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
    assert '"route_points": 17' in result.stdout
    print(result.stdout.strip())


def test_concurrent_close_waits_for_shared_reap_completion():
    from autonavy.navigation.planner import PlanningService
    entered=threading.Event(); release=threading.Event(); completed=[]
    class SlowCleanup:
        def __init__(self,req): pass
        def poll(self): return None
        def close(self): entered.set(); release.wait(2)
    service=PlanningService(job_factory=SlowCleanup,join_timeout_s=.5)
    service.submit(request())
    # Ensure the worker acquired the job before closing.
    time.sleep(.04)
    def close(): service.close(); completed.append(True)
    first=threading.Thread(target=close); first.start()
    assert entered.wait(1)
    second=threading.Thread(target=close); second.start()
    time.sleep(.04); assert completed==[]
    release.set(); first.join(1); second.join(1)
    assert completed==[True,True]


def test_late_startup_reports_historical_cleanup_timeout_on_later_close():
    from autonavy.navigation.planner import PlanningService
    entered=threading.Event(); release=threading.Event(); jobs=Jobs()
    def factory(req):
        entered.set(); release.wait(2)
        return jobs(req)
    service=PlanningService(job_factory=factory,join_timeout_s=.02)
    service.submit(request()); assert entered.wait(1)
    try:
        with pytest.raises(RuntimeError,match='supervisor'): service.close()
    finally: release.set()
    until(lambda:bool(jobs.jobs) and jobs.jobs[0].closed)
    with pytest.raises(RuntimeError,match='supervisor'): service.close()
