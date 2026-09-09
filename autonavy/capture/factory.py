"""Explicit backend selection. No fallback or acquisition during construction."""
from autonavy.capture.base import Capture


def create_capture(settings) -> Capture:
    c = settings.capture
    if c.backend == 'replay':
        from autonavy.capture.replay import ReplayCapture
        return ReplayCapture(c.fixture, max_frames=c.max_frames)
    if c.backend == 'dxcam':
        from autonavy.capture.process import ProcessCapture
        return ProcessCapture(settings)
    if c.backend == 'obs':
        from autonavy.capture.obs import OBSSource
        from autonavy.capture.process import ProcessCapture
        return ProcessCapture(settings, source_factory=OBSSource)
    raise ValueError(f'Unsupported capture backend: {c.backend}')
