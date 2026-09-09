"""Finite offline installation diagnostic using the real capture/planner owners.

No camera, telemetry, input adapter or SDK is constructed. The native route
extension receives only a generated image in its supervised child.
"""
from dataclasses import replace
from pathlib import Path
import time


class SyntheticSource:
    """Explicit synthetic source for the production spawned capture transport."""

    def __init__(self, settings):
        self.settings = settings

    def start(self):
        pass

    def read(self):
        import numpy as np
        from autonavy.capture.base import CaptureSample
        from autonavy.geometry import GeometrySnapshot
        c = self.settings.capture
        image = np.full((c.height, c.width, 3), 37, dtype=np.uint8)
        geometry = GeometrySnapshot((0, 0, c.width, c.height), (c.width, c.height),
                                    (0, 0, c.width, c.height), source_id='offline-synthetic')
        return CaptureSample(image, geometry, time.monotonic_ns(), {'synthetic': True})

    def close(self):
        pass


def run() -> dict:
    import cv2
    import numpy as np
    from autonavy.config import load_settings, resource_root
    from autonavy.capture.process import ProcessCapture
    from autonavy.navigation.planner import NativeJob, PlanRequest
    root = resource_root()
    required = ('configs/default.toml', 'fixtures/smoke/manifest.json', 'src/cir.png',
                'toolkit/way_search.cp311-win_amd64.pyd')
    for name in required:
        if not (root / name).is_file():
            raise RuntimeError(f'Missing packaged resource: {name}')
    # Compiled packages must preserve the SDK's package-relative native DLL layout.
    import sys
    if getattr(sys, 'frozen', False) or '__compiled__' in globals():
        if not (root / 'pyvjoy/utils/x64/vJoyInterface.dll').is_file():
            raise RuntimeError('Missing packaged pyvjoy SDK DLL')
    settings = load_settings(root / 'configs/default.toml')
    settings = replace(settings, capture=replace(settings.capture, startup_timeout_s=15, frame_timeout_s=5))
    capture = ProcessCapture(settings, source_factory=SyntheticSource)
    try:
        capture.start()
        packet = capture.read()
        if packet is None or not np.all(packet.image == 37):
            raise RuntimeError('Synthetic capture transport corrupted pixels')
        publication = packet.publication_id
        capture.stop()
        capture_exit = capture.process.exitcode
        if capture_exit != 0:
            raise RuntimeError(f'Capture child failed: {capture_exit}')
    finally:
        capture.close()
    # Water-color tactical image follows the actual production preprocessing/JPS.
    encoded_ok, encoded = cv2.imencode('.png', np.full((128, 128, 3), (255, 100, 0), np.uint8))
    if not encoded_ok:
        raise RuntimeError('Could not encode synthetic tactical image')
    job = NativeJob(PlanRequest(('offline-smoke',), encoded.tobytes(), (.1, .1), (.8, .8)))
    try:
        deadline = time.monotonic() + 15
        result = job.poll()
        while result is None and time.monotonic() < deadline:
            time.sleep(.01)
            result = job.poll()
        if result is None or result.error or not result.points:
            raise RuntimeError(f'Native planner smoke failed: {result}')
        planner_exit = job.process.exitcode
        points = len(result.points)
    finally:
        job.close()
    return dict(resources=len(required), resource_root=str(Path(root)),
                capture_publication=publication, capture_child_exit=capture_exit,
                planner_child_exit=planner_exit, route_points=points, hardware_opened=False)
