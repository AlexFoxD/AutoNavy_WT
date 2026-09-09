"""Import-safe pure route compatibility helpers; runtime planning owns isolation."""
from pathlib import Path
from autonavy.navigation.route import RouteCursor

PATH_FILE=Path(__file__).resolve().parents[1]/'path.json'  # Preserved resource lookup only.


def get_next_point(path,point,*,arrival_distance=0,lookahead_distance=0):
    """One pure lookup; ongoing callers should retain their RouteCursor.

    Pass a RouteCursor to preserve progress across intersections. A legacy point
    sequence starts at index zero and is never mutated or globally reordered.
    """
    if path is None: return None
    cursor=path if isinstance(path,RouteCursor) else RouteCursor(path)
    return cursor.advance(point,arrival_distance).target(lookahead_distance)


def process_img(img):
    from autonavy.navigation.native import prepare_map
    return prepare_map(img)


def pathfinding(original_img,show_img=False,start_point=None,end_point=None,human=False):
    """Synchronous explicit grid-endpoint helper for offline compatibility only.

    The battle runtime uses PlanningService instead. No map downloads, previews,
    route-file writes or device side effects are performed here.
    """
    if start_point is None or end_point is None: raise ValueError('Explicit start and end endpoints are required')
    if show_img or human: raise ValueError('Interactive path selection is retired; provide explicit endpoints')
    from autonavy.navigation.native import NativePathfinder
    return NativePathfinder().find(process_img(original_img),start_point,end_point)


if __name__=='__main__':
    from autonavy.cli import main
    raise SystemExit(main())
