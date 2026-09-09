"""Battle navigation from current telemetry/map snapshots to owned axis intents."""
import math
import random
from autonavy.navigation.control import Controllers
from autonavy.navigation.planner import PlanningService,PlanRequest
from autonavy.navigation.route import RouteCursor


class Navigation:
    def __init__(self,settings,*,planner=None,join_timeout_s=2,rng=None):
        self.settings=settings
        self.planner=planner if planner is not None else PlanningService(attempts=settings.replan_attempts,
            backoff_s=settings.replan_backoff_s,timeout_s=settings.plan_timeout_s,join_timeout_s=join_timeout_s)
        self.controllers=Controllers(settings)
        self.rng=rng if rng is not None else random.Random()
        self.cursor=None; self.destination=None; self.identity=None
        self._epoch=0; self._request_key=None; self._last_time=None; self._arrived=False
        self._waypoint=None
        self.last_error=None

    def reset(self):
        self.planner.reset(); self.controllers.reset()
        self.cursor=None; self.destination=None; self.identity=None
        self._epoch+=1; self._request_key=None; self._last_time=None; self._arrived=False
        self._waypoint=None
        self.last_error=None

    def close(self):
        self.controllers.reset()
        self.planner.close()

    def request_stop(self):
        if hasattr(self.planner,'request_stop'): self.planner.request_stop()

    def _invalidate(self,app):
        app.input.cancel('navigation')
        self.reset()

    def _replan(self,app):
        app.input.cancel('navigation'); self.planner.reset(); self.controllers.reset()
        self.cursor=None; self._request_key=None; self._epoch+=1; self._last_time=None; self._waypoint=None

    def _context(self,app,snapshot,image):
        if (not snapshot.valid or snapshot.player is None or snapshot.metadata is None or image is None
                or image.key!=snapshot.metadata.key or image.generation!=snapshot.generation): return None
        packet=app.last_frame
        if packet is None: return None
        return snapshot.generation,image.key,image.generation,packet.source_generation,packet.geometry_id

    def tick(self,app,observations,snapshot):
        now=app._clock_ns(); snapshot=snapshot.at(now)
        image=app.telemetry.map_image()
        context=self._context(app,snapshot,image)
        if context is None or not snapshot.zones:
            if self.identity is not None or self._request_key is not None: self._invalidate(app)
            return
        if self.identity!=context or self.destination not in snapshot.zones:
            self._invalidate(app)
            self.identity=context
            self.destination=self.rng.choice(snapshot.zones)
        position=snapshot.player.position
        if self._arrived: return
        if self.cursor is not None:
            self.cursor=self.cursor.advance(position,self.settings.arrival_distance)
            if self.cursor.done:
                app.input.cancel('navigation'); self.controllers.reset(); self._arrived=True
                return
            if self.cursor.deviation(position)>self.settings.replan_deviation:
                self._replan(app)
        if self._request_key is None:
            self._request_key=(context,self.destination,self._epoch)
            self.planner.submit(PlanRequest(self._request_key,image.data,position,self.destination))
        result=self.planner.poll()
        if result is not None and result.key==self._request_key:
            self.last_error=result.error
            self.cursor=None if result.points is None else RouteCursor(result.points)
            self.controllers.reset(); self._last_time=None
        # Fetch again: a result must never be stamped with a newer session/map.
        current=app.telemetry.snapshot().at(app._clock_ns())
        if self._context(app,current,app.telemetry.map_image())!=context or self.destination not in current.zones:
            self._invalidate(app)
            return
        if self.cursor is None: return
        self.cursor=self.cursor.advance(current.player.position,self.settings.arrival_distance)
        if self.cursor.done:
            app.input.cancel('navigation'); self.controllers.reset(); self._arrived=True
            return
        if self.cursor.deviation(current.player.position)>self.settings.replan_deviation:
            self._replan(app)
            return
        target=self.cursor.target(self.settings.lookahead_distance,
                                  arrival_distance=self.settings.arrival_distance)
        if self._waypoint!=self.cursor.index:
            self.controllers.heading_pid.reset(); self._last_time=None
            self._waypoint=self.cursor.index
        x,y=current.player.position
        target_heading=math.degrees(math.atan2(target[0]-x,-(target[1]-y)))
        player=current.player
        heading=math.degrees(math.atan2(player.dx,-player.dy))
        dt=1/app.settings.runtime.tick_hz if self._last_time is None else (now-self._last_time)/1e9
        self._last_time=now
        output=self.controllers.heading(target_heading,heading,dt)
        app.policy.emit('navigation','axis','Z',output,min(.2,app.settings.input.intent_ttl_s))
