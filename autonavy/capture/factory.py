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
        raise RuntimeError('OBS capture is unavailable until the M7 adapter; no fallback was selected')
    raise ValueError(f'Unsupported capture backend: {c.backend}')
