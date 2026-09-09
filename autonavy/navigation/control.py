"""Independent pixel/degree PID states with explicit actuator signs."""
import math


def angular_error(target, current):
    return (target-current+180.0)%360.0-180.0


class PID:
    def __init__(self,kp,ki,kd,*,limit,integral_limit=100,max_dt_s=1,angular=False):
        self.kp,self.ki,self.kd=kp,ki,kd
        self.limit,self.integral_limit,self.max_dt_s=limit,integral_limit,max_dt_s
        self.angular=angular
        self.reset()

    def reset(self):
        self.integral=0.0
        self.previous=None

    def update(self,error,dt):
        if not math.isfinite(error) or not math.isfinite(dt) or not 0<dt<=self.max_dt_s:
            self.reset()
            return 0.0
        derivative=0.0
        if self.previous is not None:
            delta=angular_error(error,self.previous) if self.angular else error-self.previous
            derivative=delta/dt
            self.integral=max(-self.integral_limit,min(self.integral_limit,self.integral+error*dt))
        self.previous=error
        output=self.kp*error+self.ki*self.integral+self.kd*derivative
        return max(-self.limit,min(self.limit,output))


class Controllers:
    def __init__(self,settings):
        def make(prefix,limit,angular=False):
            return PID(*(getattr(settings,prefix+'_'+term) for term in ('kp','ki','kd')),
                limit=limit,integral_limit=settings.integral_limit,max_dt_s=settings.max_dt_s,angular=angular)
        self.aim_x=make('aim',settings.aim_limit_px)
        self.aim_y=make('aim',settings.aim_limit_px)
        self.search_pid=make('search',settings.search_limit,True)
        self.heading_pid=make('heading',settings.heading_limit,True)

    def reset(self):
        for controller in (self.aim_x,self.aim_y,self.search_pid,self.heading_pid): controller.reset()

    def pixel(self,dx,dy,dt):
        return self.aim_x.update(dx,dt),self.aim_y.update(dy,dt)

    def search(self,target,current,dt):
        # Active legacy fire search: PID(current), target setpoint -> +error.
        return self.search_pid.update(angular_error(target,current),dt)

    def heading(self,target,current,dt):
        # Legacy pilot: -PID(current), target setpoint; axis_qe adds no inversion.
        return -self.heading_pid.update(angular_error(target,current),dt)
