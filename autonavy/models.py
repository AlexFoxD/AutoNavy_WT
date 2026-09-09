"""Owned frame identity and runtime states shared by the v2 pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class RuntimeState(str, Enum):
    STOPPED = 'stopped'
    STARTING = 'starting'
    WAITING = 'waiting'
    QUEUEING = 'queueing'
    IN_BATTLE = 'in_battle'
    RECOVERING = 'recovering'
    PAUSED = 'paused'
    ERROR = 'error'
    STOPPING = 'stopping'


@dataclass(frozen=True, eq=False)
class FramePacket:
    """One owned publication; receive time is not a game render timestamp."""
    image: np.ndarray = field(repr=False)
    pixel_format: str
    publication_id: int
    source_generation: int
    received_at_ns: int
    geometry_id: str
    source_timestamp: float | None = None
    source_clock: str | None = None
    source_sequence: int | None = None

    def __post_init__(self):
        import numpy as np
        channels = {'BGR': 3, 'BGRA': 4}.get(self.pixel_format)
        if not isinstance(self.image, np.ndarray) or self.image.dtype != np.uint8 or self.image.ndim != 3 or channels != self.image.shape[2] or min(self.image.shape[:2]) <= 0:
            raise ValueError('Frame must be a nonempty uint8 image matching BGR/BGRA metadata')
        if any(type(value) is not int or value < 0 for value in (self.publication_id, self.source_generation, self.received_at_ns)):
            raise ValueError('Frame identifiers and receive timestamp must be nonnegative integers')
        if not isinstance(self.geometry_id, str) or not self.geometry_id.strip():
            raise ValueError('Frame geometry identity is required')
        if (self.source_timestamp is None) != (self.source_clock is None):
            raise ValueError('Source timestamp requires its clock domain and vice versa')
        if self.source_timestamp is not None and (not math.isfinite(self.source_timestamp) or not self.source_clock.strip()):
            raise ValueError('Source timestamp must be finite and clock domain nonempty')
        if self.source_sequence is not None and (type(self.source_sequence) is not int or self.source_sequence < 0):
            raise ValueError('Source sequence must be a nonnegative integer')
        owned = self.image.copy(order='C')
        owned.flags.writeable = False
        object.__setattr__(self, 'image', owned)
