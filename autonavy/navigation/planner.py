"""One latest planning request; only the native boundary runs in a child process.

Jps.Process has no cancellation API and its GIL behavior is undocumented. The
supervisor owns spawning/reaping; runtime tick never waits for IPC/native work.
"""
from dataclasses import dataclass
import multiprocessing
import threading
import time
from autonavy.navigation.native import MAX_ROUTE_POINTS


@dataclass(frozen=True)
class PlanRequest:
    key: tuple
    data: bytes
    origin: tuple[float,float]
    destination: tuple[float,float]


@dataclass(frozen=True)
class PlanResult:
    key: tuple
    points: tuple[tuple[float,float],...] | None
    error: str | None = None


def _native_worker(request,points,count,error):
    try:
        from autonavy.navigation.native import plan_encoded
        route=plan_encoded(request.data,request.origin,request.destination)
        if route is None:
            count.value=-1
            return
        if not 0<len(route)<=MAX_ROUTE_POINTS: raise ValueError('Native route exceeds result capacity')
        for i,(x,y) in enumerate(route): points[2*i],points[2*i+1]=x,y
        count.value=len(route)
    except BaseException as exc:
        from autonavy.diagnostics import exception_text
        error.value=exception_text(exc,511)
        count.value=-2


class NativeJob:
    """Fixed 1 MiB route result, read only after child exit; no pipe to deadlock."""
    def __init__(self,request,*,join_timeout_s=2,worker=_native_worker):
        ctx=multiprocessing.get_context('spawn')
        self.request=request; self.join_timeout_s=join_timeout_s
        self.points=ctx.RawArray('d',MAX_ROUTE_POINTS*2)
        self.count=ctx.RawValue('i',-3)
        self.error=ctx.RawArray('c',512)
        self.process=ctx.Process(target=worker,args=(request,self.points,self.count,self.error),
                                 name='autonavy-native-route',daemon=True)
        self._closed=False
        try: self.process.start()
        except BaseException:
            self.close()
            raise

    def poll(self):
        if self.process.is_alive(): return None
        self.process.join(0)
        n=self.count.value
        if self.process.exitcode!=0 or n==-3:
            return PlanResult(self.request.key,None,f'Native worker exited {self.process.exitcode} without result')
        if n==-1: return PlanResult(self.request.key,None,'No reachable route')
        if n==-2: return PlanResult(self.request.key,None,self.error.value.decode('utf-8',errors='replace'))
        if not 0<n<=MAX_ROUTE_POINTS: return PlanResult(self.request.key,None,'Invalid native result count')
        return PlanResult(self.request.key,tuple((self.points[2*i],self.points[2*i+1]) for i in range(n)))

    def close(self):
        if self._closed: return
        if self.process.pid is not None:
            if self.process.is_alive(): self.process.terminate()
            self.process.join(self.join_timeout_s/2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(self.join_timeout_s/2)
            if self.process.is_alive(): raise RuntimeError('Native route child remained alive after cleanup budget')
        self.process.close()
        self._closed=True


class PlanningService:
    """One managed supervisor, one child and one pending/result slot, all owned."""
    def __init__(self,*,attempts=3,backoff_s=1,timeout_s=10,join_timeout_s=2,job_factory=None):
        if attempts<1 or min(backoff_s,timeout_s,join_timeout_s)<=0: raise ValueError('Invalid planning limits')
        self.attempts,self.backoff_s,self.timeout_s,self.join_timeout_s=attempts,backoff_s,timeout_s,join_timeout_s
        self._factory=job_factory or (lambda req:NativeJob(req,join_timeout_s=join_timeout_s))
        self._condition=threading.Condition()
        self._request=None; self._result=None; self._serial=0
        self._stopped=False; self._thread=None; self._error=None
        self._complete=threading.Event()

    def submit(self,request):
        from autonavy.telemetry import MAX_IMAGE_BYTES
        if not isinstance(request.data,bytes) or len(request.data)>MAX_IMAGE_BYTES:
            raise ValueError('Planning request exceeds encoded-image capacity')
        with self._condition:
            if self._stopped or self._error: raise RuntimeError(self._error or 'Planner is closed')
            if self._request is not None and self._request.key==request.key: return
            self._request=request; self._result=None; self._serial+=1
            if self._thread is None:
                self._thread=threading.Thread(target=self._run,name='autonavy-planner',daemon=True)
                self._thread.start()
            self._condition.notify_all()

    def poll(self):
        with self._condition:
            if self._error: raise RuntimeError(self._error)
            result=self._result; self._result=None
            return result

    def reset(self):
        with self._condition:
            self._serial+=1; self._request=None; self._result=None
            self._condition.notify_all()

    def request_stop(self):
        with self._condition:
            self._stopped=True; self._serial+=1; self._request=None; self._result=None
            self._condition.notify_all()

    def _current(self,serial):
        return not self._stopped and self._serial==serial

    def _run(self):
        handled=-1
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda:self._stopped or (self._request is not None and self._serial!=handled))
                    if self._stopped: return
                    request=self._request; serial=self._serial; handled=serial
                for attempt in range(self.attempts):
                    with self._condition:
                        if not self._current(serial): break
                    started=time.monotonic(); job=None
                    try:
                        job=self._factory(request)
                        while True:
                            with self._condition:
                                if not self._current(serial): break
                            result=job.poll()
                            if result is not None: break
                            if time.monotonic()-started>=self.timeout_s:
                                result=PlanResult(request.key,None,'Native planning timeout')
                                break
                            with self._condition:
                                if self._current(serial): self._condition.wait(.02)
                    except Exception as exc:
                        from autonavy.diagnostics import exception_text
                        result=PlanResult(request.key,None,exception_text(exc).decode('utf-8',errors='replace'))
                    finally:
                        # Failure to reclaim is fatal; never spawn another child.
                        if job is not None: job.close()
                    with self._condition:
                        if not self._current(serial): break
                        if result.points is not None or attempt+1==self.attempts:
                            self._result=result
                            break
                        self._condition.wait_for(lambda:not self._current(serial),timeout=self.backoff_s)
        except BaseException as exc:
            with self._condition:
                self._error=f'{type(exc).__name__}: {exc}'
                self._stopped=True
        finally:
            self._complete.set()

    def close(self):
        self.request_stop()
        with self._condition: thread=self._thread
        if thread is not None:
            # Includes native reap allowance and a short supervisor scheduling margin.
            if not self._complete.wait(self.join_timeout_s+.25):
                with self._condition:
                    self._error=self._error or 'Planner supervisor did not complete within cleanup budget'
                    error=self._error
                raise RuntimeError(error)
            thread.join(0)
        with self._condition: error=self._error
        if error: raise RuntimeError(error)
