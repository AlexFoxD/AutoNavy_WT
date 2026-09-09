"""Cancellable non-spending menu and battle decisions using current runtime data."""
from dataclasses import dataclass
import math
import random
from autonavy.input.controller import InputIntent
from autonavy.models import RuntimeState

PURCHASE = frozenset({'buy','_purchase','purchase_confirm','autobuyparts'})
END = frozenset({'back','base','start_battle_end','cart','data'})
MENU = frozenset({'start','join','join_game','confirm','confirm1','confirm2','confirm1_queue',
    'confirm2_queue','improvement','improvement_','crew_cancel','rtlg_no','research','research1','wtlogo'})
BATTLE = frozenset({'aim','lock','fire','ammo','degree','crash_warning','crashed'})


@dataclass(frozen=True)
class Step:
    action: str | None = None
    resource: str = ''
    value: object = 1
    hold_s: float = 0
    wait_s: float = 0


class BattlePolicy:
    """M6 may supply navigation.tick(app, observations, snapshot) and reset()."""
    def __init__(self, app, *, rng=None, navigation=None):
        self.app = app
        self.rng = rng if rng is not None else random.Random()
        self.navigation = navigation
        self.stage = 'hangar'
        self.deadline = None
        self.next_action = 0
        self.sequence = []
        self.sequence_owner = None
        self.sequence_done = None
        self.identity = None
        self.zoom = False
        self.fire_due = None
        self.pause_reason = None

    @property
    def detectors(self):
        common = PURCHASE | END
        if self.app.state in (RuntimeState.IN_BATTLE,RuntimeState.RECOVERING): return common | BATTLE
        if self.app.state == RuntimeState.PAUSED: return common
        return common | MENU

    def _matched(self, name):
        observations = self.app.last_observations
        observation = observations.matches.get(name) if observations else None
        return observation if observation and observation.available and observation.matched else None

    def _intent(self, owner, action, resource, value=1, hold_s=0):
        a = self.app; p = a.last_frame; now = a._clock_ns()
        return InputIntent(owner,action,resource,value,now,now+int(a.settings.input.intent_ttl_s*1e9),
            a.input.generation(owner),int(hold_s*1e9),100 if owner=='recovery' else 50 if owner=='ui' else 10,
            p.source_generation if p else None,p.geometry_id if p else None,
            a.last_snapshot.generation,owner!='ui')

    def emit(self, owner, action, resource, value=1, hold_s=0):
        return self.app.input.submit(self._intent(owner,action,resource,value,hold_s))

    def _tap(self, owner, key):
        return self.emit(owner,'key',key,hold_s=self.app.settings.input.press_duration_s)

    def _click(self, name):
        match = self._matched(name)
        if match is None or match.desktop_center is None: return False
        self.emit('ui','position','pointer',match.desktop_center)
        return self.emit('ui','mouse','left',hold_s=self.app.settings.input.click_duration_s)

    def _reset(self):
        self.app.input.cancel()
        self.sequence=[]; self.sequence_owner=None; self.sequence_done=None
        self.fire_due=None; self.zoom=False; self.identity=None
        if self.navigation is not None: self.navigation.reset()

    def _state(self, state, stage, timeout=None):
        self.app._transition(state)
        self.stage=stage
        self.deadline=None if timeout is None else self.app._clock_ns()+int(timeout*1e9)
        mode = ('recovery' if state==RuntimeState.RECOVERING else 'battle' if state==RuntimeState.IN_BATTLE
                or stage in {'settle','throttle'} else 'paused' if state==RuntimeState.PAUSED else 'ui')
        self.app.input.set_mode(mode)

    def _sequence(self, owner, steps, done):
        self.sequence=list(steps); self.sequence_owner=owner; self.sequence_done=done
        self.next_action=self.app._clock_ns()

    def _tick_sequence(self, now):
        if now < self.next_action: return
        if not self.sequence:
            done=self.sequence_done; self.sequence_done=None
            if done: done()
            return
        step=self.sequence.pop(0)
        if step.action:
            self.emit(self.sequence_owner,step.action,step.resource,step.value,step.hold_s)
        self.next_action=now+int((step.hold_s+step.wait_s)*1e9)

    def pause(self, reason='Manual pause'):
        self._reset(); self.pause_reason=reason
        self._state(RuntimeState.PAUSED,'paused')

    def toggle_pause(self):
        if self.app.state != RuntimeState.PAUSED: self.pause(); return
        if any(self._matched(name) for name in PURCHASE): return
        self.pause_reason=None; self._reset()
        self._state(RuntimeState.WAITING,'hangar',self.app.settings.runtime.menu_timeout_s)

    def _battle_ready(self):
        self.app.vision.begin_battle(self.app.last_frame)
        self._state(RuntimeState.IN_BATTLE,'battle')
        self.identity=self._identity(True)

    def _identity(self, battle):
        p=self.app.last_frame
        return (p.source_generation,p.geometry_id,self.app.last_snapshot.generation if battle else None)

    def _recover(self):
        self._reset(); self._state(RuntimeState.RECOVERING,'recovery')
        self.identity=self._identity(True)
        r=self.app.settings.runtime; press=self.app.settings.input.press_duration_s
        # Historical config names are retained for compatibility: settle=S hold,
        # reverse=stationary wait, turn=W hold, forward=final stationary wait.
        steps=[Step('key','s',hold_s=r.recovery_settle_s,wait_s=r.recovery_reverse_s),
               Step('key','w',hold_s=r.recovery_turn_s)]
        steps += [Step('key','s',hold_s=press,wait_s=press) for _ in range(3)]
        steps += [Step(wait_s=r.recovery_forward_s)]
        self._sequence('recovery',steps,lambda:self._state(RuntimeState.IN_BATTLE,'battle'))
        self._tick_sequence(self.app._clock_ns())

    def _end(self, name):
        self._reset(); self._state(RuntimeState.WAITING,'return',self.app.settings.runtime.menu_timeout_s)
        if name=='back': self._click('back'); self.stage='hangar'
        elif name=='base': self.stage='hangar'
        else:
            press=self.app.settings.input.press_duration_s
            keys=['esc','down','up']+['down']*6+['enter','left','enter']
            steps=[Step('key',key,hold_s=press,wait_s=.5 if n==0 else .1) for n,key in enumerate(keys)]
            steps.append(Step(wait_s=2))
            self._sequence('ui',steps,lambda:setattr(self,'stage','hangar'))

    def tick(self, new_frame=False):
        a=self.app; now=a._clock_ns(); r=a.settings.runtime
        if a.state==RuntimeState.STOPPED: self._state(RuntimeState.WAITING,'hangar',r.menu_timeout_s)
        if self.deadline is not None and now>=self.deadline and self.stage in {'hangar','queue','player'}:
            raise RuntimeError(f'Runtime {self.stage} deadline exceeded')
        if a.last_frame is None: return
        battle=a.state in (RuntimeState.IN_BATTLE,RuntimeState.RECOVERING) or self.stage in {'settle','throttle'}
        if not a._input_guard(self._intent('ui','key','x')):
            self._reset()
            if battle: self._state(RuntimeState.QUEUEING,'player',r.player_timeout_s)
            elif self.stage not in {'hangar','paused'}:
                self._state(RuntimeState.WAITING,'hangar',r.menu_timeout_s)
            return
        if any(self._matched(name) for name in PURCHASE) or (self._matched('start_battle_end') and self._matched('cart')):
            if a.state!=RuntimeState.PAUSED: self.pause('Purchase dialog requires manual handling')
            return
        if a.state==RuntimeState.PAUSED: return
        if battle:
            for name in ('back','base','data'):
                if self._matched(name): self._end(name); return
            if not a._input_guard(self._intent('navigation','key','x')):
                self._reset(); self._state(RuntimeState.QUEUEING,'player',r.player_timeout_s); return
        current=self._identity(battle)
        if self.identity is not None and current != self.identity:
            self._reset()
            if battle: self._state(RuntimeState.QUEUEING,'player',r.player_timeout_s)
            else: self._state(RuntimeState.WAITING,'hangar',r.menu_timeout_s)
            return
        self.identity=current
        if self.sequence_done is not None:
            self._tick_sequence(now); return
        if a.state==RuntimeState.RECOVERING: return
        if self.stage=='spawn':
            if now>=self.deadline:
                self._tap('ui','enter'); self._state(RuntimeState.QUEUEING,'player',r.player_timeout_s)
            return
        if self.stage=='player':
            if a.last_snapshot.valid:
                self._state(RuntimeState.QUEUEING,'settle',r.battle_settle_s)
                self.identity=self._identity(True)
            elif new_frame:
                for name in ('confirm1_queue','confirm2_queue'):
                    if self._click(name): break
            return
        if self.stage=='settle':
            if now>=self.deadline:
                self.stage='throttle'; press=a.settings.input.press_duration_s
                self._sequence('navigation',[Step('key','s',hold_s=press,wait_s=press) for _ in range(3)],self._battle_ready)
                self._tick_sequence(now)
            return
        if a.state==RuntimeState.IN_BATTLE:
            if new_frame and (self._matched('crash_warning') or self._matched('crashed')): self._recover(); return
            if self.navigation is not None: self.navigation.tick(a,a.last_observations,a.last_snapshot)
            self._fight(now,new_frame); return
        if not new_frame: return
        if self._matched('join_game') or self._matched('join') or a.last_snapshot.valid:
            self._state(RuntimeState.QUEUEING,'spawn',r.spawn_delay_s); return
        if now<self.next_action: return
        if self._matched('start'):
            match=self._matched('start')
            self.emit('ui','position','pointer',match.desktop_center)
            self._tap('ui','enter')
            self._state(RuntimeState.QUEUEING,'queue',r.queue_timeout_s)
            self.next_action=now+1_000_000_000; return
        names=('confirm1_queue','confirm2_queue') if self.stage=='queue' else (
            'confirm','confirm1','confirm2','improvement','improvement_','crew_cancel','rtlg_no')
        handled=any(self._click(name) for name in names)
        if not handled and self._matched('research'): handled=self._click('research1')
        if not handled and (self.stage=='hangar' or self._matched('wtlogo')): self._tap('ui','esc')
        self.next_action=now+200_000_000

    def set_zoom(self, level):
        """Preserve Shift and right-click zoom levels through owned short holds."""
        if level not in (0,1,2): raise ValueError('Zoom level must be 0, 1, or 2')
        previous=int(self.zoom)
        if (previous>0) != (level>0): self._tap('search','shift')
        if (previous==2) != (level==2):
            self.emit('search','mouse','right',hold_s=self.app.settings.input.click_duration_s)
        self.zoom=level

    def _fight(self, now, new_frame):
        a=self.app; aim=self._matched('aim'); ammo=self._matched('ammo')
        if self.fire_due is not None:
            if not aim or not ammo: self.fire_due=None; return
            if now>=self.fire_due:
                self.emit('fire','mouse','left',hold_s=a.settings.input.click_duration_s)
                self.fire_due=None; self.next_action=now+int(a.settings.input.click_duration_s*1e9)
            return
        if not new_frame or now<self.next_action: return
        if aim and aim.frame_center:
            x,y=aim.frame_center; w,h=a.last_frame.geometry.frame_size
            dx,dy=x-w//2,y-h//2
            if abs(dx)<=2 and abs(dy)<=2:
                if ammo:
                    self.emit('fire','move','pointer',(self.rng.randint(-10,10),self.rng.randint(0,10)))
                    self.fire_due=now+500_000_000
            else:
                c=a.settings.control
                clamp=lambda x:max(-c.aim_limit_px,min(c.aim_limit_px,x*c.aim_kp))
                self.emit('aim','move','pointer',(round(clamp(dx)),round(clamp(dy))))
            return
        if self._matched('lock'): return  # Lock indicator has no calibrated target center.
        self.set_zoom(1)
        snapshot=a.last_snapshot; player=snapshot.player
        if snapshot.enemies:
            target=min(snapshot.enemies,key=lambda e:(e.position[0]-player.position[0])**2+(e.position[1]-player.position[1])**2)
            target_deg=math.degrees(math.atan2(target.position[0]-player.position[0],-(target.position[1]-player.position[1])))
            hull=math.degrees(math.atan2(player.dx,-player.dy))
            degree=a.last_observations.degree
            current=hull+(degree.degrees if degree.available else 0)
            error=(target_deg-current+180)%360-180
            if abs(error)<30: self._tap('search','x')
            c=a.settings.control
            # Legacy PID(target setpoint, current measurement) yields +target-current.
            output=max(-c.search_limit,min(c.search_limit,error*c.search_kp))
            self.emit('search','move','pointer',(round(output),0))
        else: self._tap('search','x')
        self.next_action=now+100_000_000
