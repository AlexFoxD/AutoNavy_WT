"""Capture lifecycle: None means finite EOF or explicit cancellation."""
from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING
from autonavy.models import FramePacket

if TYPE_CHECKING:
    import numpy as np
    from autonavy.geometry import GeometrySnapshot


@dataclass(frozen=True)
class CaptureSample:
    """Child-local native pixels plus the original successful receive time."""
    image: 'np.ndarray'
    geometry: 'GeometrySnapshot'
    received_at_ns: int
    diagnostic: dict | None = None


class CaptureError(RuntimeError):
    """Capture failed; callers must not reuse stale data as a new frame."""


class CaptureTimeout(CaptureError):
    """No frame or startup within the configured supervision deadline."""


class Capture(Protocol):
    def start(self) -> None: ...
    def read(self, timeout: float | None = None) -> FramePacket | None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
