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

    def target(self, lookahead):
        if self.done: return None
        point=self.points[self.index]
        for index in range(self.index+1,len(self.points)):
            following=self.points[index]
            distance=math.dist(point,following)
            if distance>lookahead:
                ratio=lookahead/distance
                return tuple(a+(b-a)*ratio for a,b in zip(point,following))
            lookahead-=distance
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
