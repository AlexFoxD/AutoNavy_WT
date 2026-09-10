"""Lazy JPS protocol adapter. Run encoded-map planning only in its owned child."""
import importlib
import math
import platform
import struct
import sys

MAX_ROUTE_POINTS=65_536


def _load_native():
    if sys.platform!='win32' or sys.version_info[:2]!=(3,11) or struct.calcsize('P')!=8 or platform.python_implementation()!='CPython':
        raise RuntimeError('Native navigation requires Windows x64 CPython 3.11')
    return importlib.import_module('toolkit.way_search')


class NativePathfinder:
    def __init__(self,module_loader=None):
        self._loader=module_loader or _load_native
        self._module=None

    def find(self,processed,origin,goal):
        import numpy as np
        if processed.ndim!=3 or processed.shape[2]!=3: raise ValueError('Expected BGR grid')
        height,width=processed.shape[:2]
        if not 0<height*width<=MAX_ROUTE_POINTS: raise ValueError('Grid exceeds native capacity')
        def point(value):
            if not isinstance(value,(tuple,list)) or len(value)!=2 or any(type(v) is not int for v in value):
                raise ValueError('Native points must be integer pairs')
            x,y=value
            if not (0<=x<width and 0<=y<height): raise ValueError('Native point outside grid')
            return x,y
        origin,goal=point(origin),point(goal)
        blocked=np.all(processed==0,axis=2)
        if blocked[origin[1],origin[0]] or blocked[goal[1],goal[0]]: return None
        if origin==goal: return (origin,)
        if self._module is None: self._module=self._loader()
        m=self._module; grid=m.MapGrid(height,width)
        for y,x in np.argwhere(blocked): grid.set_grid(int(x),int(y),'obstacle')
        grid.set_grid(*origin,'origin'); grid.set_grid(*goal,'goal')
        result=m.Jps(m.Point(*origin),m.Point(*goal),grid).Process()
        if not isinstance(result,tuple) or len(result)!=3: raise ValueError('Malformed native result')
        if result==(None,None,None): return None
        if not all(isinstance(component,list) for component in result): raise ValueError('Malformed native components')
        interior=result[1]
        if not isinstance(interior,list) or len(interior)>height*width-2: raise ValueError('Malformed native path')
        route=(origin,)+tuple(point(p) for p in reversed(interior))+(goal,)
        for a,b in zip(route,route[1:]):
            if max(abs(a[0]-b[0]),abs(a[1]-b[1]))!=1: raise ValueError('Native path is not contiguous')
            if blocked[b[1],b[0]]: raise ValueError('Native path enters obstacle')
        return route


def prepare_map(image):
    """Preserve legacy water mask, quarter resize and 128-row obstacle dilation."""
    import cv2
    import numpy as np
    if image is None or image.ndim!=3 or image.shape[2]!=3 or min(image.shape[:2])<4:
        raise ValueError('Invalid tactical image')
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    mask=cv2.bitwise_not(cv2.inRange(hsv,(70,23,27),(134,255,255)))
    masked=cv2.bitwise_and(image,image,mask=mask)
    _,binary=cv2.threshold(masked,0,255,cv2.THRESH_BINARY_INV)
    binary=cv2.resize(binary,(0,0),fx=.25,fy=.25)
    binary=cv2.bitwise_not(binary)
    scale=128/binary.shape[0]
    width=round(binary.shape[1]*scale)
    if not 0<width*128<=MAX_ROUTE_POINTS: raise ValueError('Tactical aspect ratio exceeds grid capacity')
    binary=cv2.resize(binary,(width,128),interpolation=cv2.INTER_NEAREST)
    return cv2.bitwise_not(cv2.dilate(binary,np.ones((5,5),np.uint8)))


def _normalize_route_grid(grid,origin,goal):
    """Normalize live map polarity while preserving NativePathfinder's zero=blocked contract.

    War Thunder tactical-map rendering is not completely stable across map
    generations/modes.  Legacy prepare_map() can therefore produce a grid where
    the navigable water class is zero instead of non-zero.

    The ship origin is known to be navigable, and a capture-zone destination is
    expected to be on the same navigable class for a usable route.  We only
    reverse the binary interpretation when *both* points are all-zero.  If only
    one endpoint is zero, the request remains unreachable rather than guessing
    and potentially routing through terrain.
    """
    import numpy as np
    if grid.ndim!=3 or grid.shape[2]!=3: raise ValueError('Expected BGR grid')
    height,width=grid.shape[:2]
    ox,oy=origin; gx,gy=goal
    if not (0<=ox<width and 0<=oy<height and 0<=gx<width and 0<=gy<height):
        raise ValueError('Route endpoint outside grid')

    zero=np.all(grid==0,axis=2)
    origin_zero=bool(zero[oy,ox])
    goal_zero=bool(zero[gy,gx])

    if origin_zero!=goal_zero:
        return None

    # NativePathfinder's stable public contract is zero=blocked/non-zero=free.
    # Keep that contract untouched and normalize only the live planning grid.
    passable=zero if origin_zero else ~zero
    normalized=np.zeros_like(grid,dtype=np.uint8)
    normalized[passable]=255
    return normalized


def plan_encoded(data,origin,destination,adapter=None):
    import cv2
    import numpy as np
    from autonavy.telemetry import MAX_IMAGE_BYTES,MAX_IMAGE_PIXELS
    if not isinstance(data,bytes) or not 0<len(data)<=MAX_IMAGE_BYTES: raise ValueError('Invalid encoded tactical image')
    image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
    if image is None or image.shape[0]*image.shape[1]>MAX_IMAGE_PIXELS: raise ValueError('Invalid decoded tactical image')
    grid=prepare_map(image)
    h,w=image.shape[:2]; gh,gw=grid.shape[:2]
    def pixel(position):
        if len(position)!=2 or any(not math.isfinite(v) or not 0<=v<=1 for v in position):
            raise ValueError('Position must be normalized')
        # War Thunder map_obj coordinates use the same top-left normalized
        # x/y orientation as map.img.
        x,y=min(w-1,int(position[0]*w)),min(h-1,int(position[1]*h))
        return min(gw-1,int(x*gw/w)),min(gh-1,int(y*gh/h))

    start=pixel(origin); goal=pixel(destination)
    normalized=_normalize_route_grid(grid,start,goal)
    if normalized is None: return None

    route=(adapter or NativePathfinder()).find(normalized,start,goal)
    return None if route is None else tuple((x/gw,y/gh) for x,y in route)
