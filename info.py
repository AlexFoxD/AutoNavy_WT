"""Legacy-shaped information view; caller supplies an owned telemetry source."""
import math


class info:
    def __init__(self, source):
        self.source = source
        self.player = None
        self.mapinfo = None
        self.enemy = []
        self.connected = False

    def update(self):
        snapshot = self.source.snapshot()
        self.connected = snapshot.valid
        self.player, self.mapinfo, self.enemy = None, None, []
        if not snapshot.valid:
            return
        player, metadata = snapshot.player, snapshot.metadata
        self.player = {'pos': list(player.position), 'dx': player.dx, 'dy': player.dy}
        self.mapinfo = {'scale': metadata.scale, 'step': metadata.grid_steps[0]}
        self.enemy = sorted(({'pos': list(e.position),
                              'dis': math.dist(e.position, player.position) * metadata.scale}
                             for e in snapshot.enemies), key=lambda e: e['dis'])
