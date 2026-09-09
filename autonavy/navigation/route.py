"""Immutable forward-only route progress in normalized x-right/y-down units."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RouteCursor:
    points: tuple[tuple[float, float], ...]
    index: int = 0

    def __post_init__(self):
        points=tuple(tuple(p) for p in self.points)
        if any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in points):
            raise ValueError('Route points must be finite pairs')
        if not 0 <= self.index <= len(points): raise ValueError('Invalid route cursor')
        object.__setattr__(self,'points',points)

    @property
    def done(self): return self.index == len(self.points)

    def advance(self, position, arrival):
        index=self.index
        # Only contiguous reached points count. A later crossing is irrelevant.
        while index<len(self.points) and math.dist(position,self.points[index])<=arrival:
            index+=1
        if index==self.index: return self
        # The immutable points were validated on construction. Advancing creates
        # only a cursor, without copying/revalidating the entire route each tick.
        cursor=object.__new__(RouteCursor)
        object.__setattr__(cursor,'points',self.points)
        object.__setattr__(cursor,'index',index)
        return cursor

    def target(self, lookahead, *, arrival_distance=None):
        """Look ahead on the current straight section, never beyond its turn.

        Runtime callers provide the arrival radius: the target then stays within
        half that radius of the next required point. Reaching the target must
        advance the cursor even after an off-route approach; the margin avoids
        stranding on floating-point equality at the arrival boundary. The original
        target(lookahead) call remains supported with the geometric turn cap.
        """
        if self.done: return None
        point=self.points[self.index]
        if self.index==0: return point
        if arrival_distance is not None:
            lookahead=min(lookahead,arrival_distance/2)
        previous=self.points[self.index-1]
        for index in range(self.index+1,len(self.points)):
            following=self.points[index]
            ax,ay=point[0]-previous[0],point[1]-previous[1]
            bx,by=following[0]-point[0],following[1]-point[1]
            # Stop at the required corner/reversal instead of asking the boat to
            # follow a target that the forward-only cursor cannot consume.
            if ax*bx+ay*by<=0 or not math.isclose(ax*by-ay*bx,0,abs_tol=1e-12):
                return point
            distance=math.dist(point,following)
            if distance>lookahead:
                ratio=lookahead/distance
                return tuple(a+(b-a)*ratio for a,b in zip(point,following))
            lookahead-=distance
            previous=point
            point=following
        return point

    def deviation(self, position):
        """Distance to the current segment, never a later crossing/branch."""
        if self.done: return 0.0
        b=self.points[self.index]
        a=self.points[max(0,self.index-1)]
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=dx*dx+dy*dy
        ratio=0 if not length else max(0,min(1,((position[0]-a[0])*dx+(position[1]-a[1])*dy)/length))
        return math.dist(position,(a[0]+ratio*dx,a[1]+ratio*dy))
