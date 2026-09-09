"""One serialized physical owner with bounded, guarded and cancellable intents."""
from collections import deque
from dataclasses import dataclass
import math
import threading
import time
from autonavy.input.scheduler import Pending


@dataclass(frozen=True)
class InputIntent:
    owner: str
    action: str
    resource: str
    value: object
    created_at_ns: int
    deadline_ns: int
    generation: int
    duration_ns: int = 0
    priority: int = 10
    source_generation: int | None = None
    geometry_id: str | None = None
    telemetry_generation: int | None = None
    requires_telemetry: bool = True

    def __post_init__(self):
        if self.action not in {'key','mouse','axis','button','move','position','wheel'}:
            raise ValueError('Unknown input action')
        if self.deadline_ns < self.created_at_ns or self.duration_ns < 0 or not self.owner:
            raise ValueError('Invalid intent identity or deadline')
        values = self.value if isinstance(self.value, tuple) else (self.value,)
        if not all(isinstance(v, (int,float)) and math.isfinite(v) for v in values):
            raise ValueError('Input values must be finite')


@dataclass(frozen=True)
class Hold:
    intent: InputIntent
    expires_at_ns: int
    token: int


class RecordingBackend:
    physical = False
    def __init__(self, *, max_events=10000):
        if type(max_events) is not int or max_events<1: raise ValueError('Recording history bound must be positive')
        self._events=deque(maxlen=max_events)
        self.total_events=0
    @property
    def events(self): return list(self._events)
    @property
    def dropped_events(self): return self.total_events-len(self._events)
    def start(self): pass
    def dispatch(self, action, resource, value):
        self._events.append((action,resource,value))
        self.total_events+=1
    def close(self): pass


class InputController:
    """All dispatch and release paths serialize here, including error cleanup."""
    def __init__(self, backend, *, guard, clock_ns=time.monotonic_ns, max_pending=64):
        self.backend, self.guard, self.clock_ns = backend, guard, clock_ns
        self._pending = Pending(max_pending)
        self._generations = {}
        self._epoch = 0
        self.held = {}
        self.release_errors = ()
        self.emergency = threading.Event()
        self._lock = threading.RLock()
        self.mode = 'paused'
        self._token = 0
        self._closed = False
        self._started = False

    def start(self):
        with self._lock:
            if self.emergency.is_set() or self._closed or self._started: return
            self.backend.start()
            if self.emergency.is_set():
                self.backend.close()
                return
            self._started = True
            now = self.clock_ns()
            for action,resource in getattr(self.backend, 'neutral_resources', ()):
                intent = InputIntent('startup',action,resource,0,now,now,0)
                self._token += 1
                self.held[action,resource] = Hold(intent,now,self._token)
            self.release_all()

    def close(self):
        with self._lock:
            self.emergency.set()
            self._closed = True
            try:
                self.release_all()
                self.backend.close()
            finally:
                if hasattr(self.backend,'restore_timing'): self.backend.restore_timing()

    def generation(self, owner): return self._generations.get(owner,self._epoch)
    @property
    def pending_count(self): return len(self._pending.items)

    def _allowed(self, intent):
        if self.mode == 'ui': return intent.owner == 'ui'
        if self.mode == 'recovery': return intent.owner == 'recovery'
        if self.mode == 'battle': return intent.owner != 'ui'
        return False

    def submit(self, intent):
        with self._lock:
            if (self.emergency.is_set() or not self._allowed(intent)
                    or intent.generation != self.generation(intent.owner)
                    or self.clock_ns() >= intent.deadline_ns):
                return False
            return self._pending.put(intent)

    def set_mode(self, mode):
        if mode not in {'ui','battle','recovery','paused'}: raise ValueError('Unknown input mode')
        with self._lock:
            if self.mode != mode:
                self.mode = mode
                self.cancel()

    def _release(self, resource, hold):
        # Identity test prevents a queued/old expiry from releasing a newer hold.
        if self.held.get(resource) is not hold: return
        self.backend.dispatch(*resource, 0)
        del self.held[resource]

    def _release_many(self, selected):
        errors = []
        for resource,hold in selected:
            try: self._release(resource,hold)
            except BaseException as exc: errors.append(exc)
        self.release_errors = tuple(str(e) for e in errors)
        if errors: raise RuntimeError('; '.join(self.release_errors)) from errors[0]

    def cancel(self, owner=None):
        with self._lock:
            if owner is None:
                self._epoch=max([self._epoch,*self._generations.values()])+1
                self._generations.clear()
            else:
                self._generations[owner]=self.generation(owner)+1
            self._pending.cancel(owner)
            self._release_many([(r,h) for r,h in self.held.items() if owner is None or h.intent.owner == owner])

    def release_all(self):
        self.cancel()

    def tick(self):
        with self._lock:
            now = self.clock_ns()
            if self.emergency.is_set():
                self.release_all()
                return
            releases = []
            for resource,hold in tuple(self.held.items()):
                i = hold.intent
                if (now >= hold.expires_at_ns or i.generation != self.generation(i.owner)
                        or not self._allowed(i) or not self.guard(i) or self.clock_ns()>=hold.expires_at_ns):
                    releases.append((resource,hold))
            self._release_many(releases)
            pointer_owner = None
            for intent in self._pending.take():
                if (self.emergency.is_set() or self.clock_ns() >= intent.deadline_ns
                        or intent.generation != self.generation(intent.owner)
                        or not self._allowed(intent)):
                    continue
                # Relative movement, absolute positioning, wheel and mouse-button
                # acquisition share the pointer. Sorted priority selects one owner
                # per batch; same-owner position/click pairs remain ordered.
                pointer = (intent.action in {'move','position'} or
                           intent.action in {'mouse','wheel'} and intent.value != 0)
                if pointer:
                    if pointer_owner is not None and pointer_owner != intent.owner: continue
                    conflicts = [(r,h) for r,h in self.held.items()
                                 if r[0]=='mouse' and h.intent.owner != intent.owner]
                    if any(h.intent.priority > intent.priority for _,h in conflicts): continue
                    # Never move under another owner's held button: release it first.
                    self._release_many(conflicts)
                resource = intent.action,intent.resource
                hold = self.held.get(resource)
                if hold is not None:
                    if intent.value == 0 and hold.intent.owner != intent.owner: continue
                    if hold.intent.owner != intent.owner and hold.intent.priority > intent.priority: continue
                    self._release(resource,hold)
                if (not self.guard(intent) or self.emergency.is_set()
                        or self.clock_ns() >= intent.deadline_ns
                        or intent.generation != self.generation(intent.owner)
                        or not self._allowed(intent)): continue
                if intent.action in {'key','mouse','axis','button'}:
                    if intent.value == 0:
                        # Releases use the same ownership path, never a blind release.
                        continue
                    self._token += 1
                    # A failed OS call is uncertain: retain it for retryable cleanup.
                    self.held[resource] = Hold(intent, self.clock_ns()+intent.duration_ns, self._token)
                self.backend.dispatch(intent.action,intent.resource,intent.value)
                if pointer: pointer_owner = intent.owner
