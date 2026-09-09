"""Read-only map compatibility helpers; no implicit HTTP or asset overwrites."""
import math


def download_map(*, source):
    """Return cached encoded image bytes, or None. This no longer writes a file."""
    image = source.map_image()
    return None if image is None else image.data


def get_point(onlyplayer=False, *, source):
    snapshot = source.snapshot()
    if not snapshot.valid:
        return ([], None) if onlyplayer else ([], [], [])
    player = snapshot.player
    if onlyplayer:
        return list(player.position), math.degrees(math.atan2(player.dx, -player.dy)) % 360
    return ([list(player.position) + [player.dx, player.dy]],
            [list(p) for p in snapshot.zones], [list(e.position) for e in snapshot.enemies])
