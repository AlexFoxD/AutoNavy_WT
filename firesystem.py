"""Packet-in compatibility facade; coordinated runtime policy owns all physical input."""
from autonavy.vision.detectors import VisionPipeline


class fire_control:
    """Retain battle baseline/recognition entrypoints without legacy capture or OS events."""
    def __init__(self, settings, packet=None, *, pipeline=None):
        self.vision = pipeline if pipeline is not None else VisionPipeline(settings)
        if packet is not None:
            self.vision.begin_battle(packet)

    def begin_battle(self, packet):
        self.vision.begin_battle(packet)

    def lock_and_fire(self, packet):
        """Return aim/lock/ammo/degree observations for M5's scheduled fire policy."""
        return self.vision.observe(packet)
