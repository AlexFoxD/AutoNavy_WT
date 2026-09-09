"""Literal mappings catch desktop-offset, scale, and stale-geometry bugs."""
import importlib.util
from dataclasses import replace

import numpy as np
import pytest


def geometry_type():
    assert importlib.util.find_spec('autonavy.geometry'), 'packet geometry mapping is missing'
    from autonavy.geometry import GeometrySnapshot
    return GeometrySnapshot


def test_negative_origin_roi_and_boxes_have_literal_desktop_coordinates():
    geometry = geometry_type()((-1500, 100, -220, 820), (1280, 720), (0, 0, 1280, 720))
    assert geometry.roi_to_desktop((10, 20), (370, 200, 910, 510)) == (-1120, 320)
    assert geometry.frame_box_to_desktop((370, 200, 390, 220)) == (-1130, 300, -1110, 320)
    assert geometry.desktop_to_frame((-1120, 320)) == (380, 220)
    assert geometry.output_region((-1920, 0, 0, 1080)) == (420, 100, 1700, 820)
    assert geometry.recognition_supported
    assert replace(geometry, client_rect=(-1400, 100, -120, 820)).geometry_id != geometry.geometry_id


def test_letterbox_mapping_does_not_claim_scaled_profile_is_recognized():
    geometry = geometry_type()((100, 200, 1380, 920), (1920, 1080), (320, 180, 1600, 900))
    assert geometry.frame_to_desktop((330, 200)) == (110, 220)
    assert not geometry.recognition_supported
    assert geometry.diagnostic()['client_rect'] == (100, 200, 1380, 920)
    for point in ((0, 0), (1600, 900), (float('nan'), 300)):
        with pytest.raises(ValueError):
            geometry.frame_to_desktop(point)
    with pytest.raises(ValueError):
        geometry.output_region((0, 0, 1280, 720))


def test_packet_rejects_new_geometry_for_old_pixels_and_retains_snapshot():
    geometry = geometry_type()((10, 20, 13, 22), (3, 2), (0, 0, 3, 2))
    from autonavy.models import FramePacket
    pixels = np.zeros((2, 3, 3), dtype=np.uint8)
    packet = FramePacket(pixels, 'BGR', 1, 1, 10, geometry.geometry_id, geometry=geometry)
    assert packet.geometry is geometry
    with pytest.raises(ValueError):
        FramePacket(pixels, 'BGR', 1, 1, 10, 'old', geometry=geometry)
    with pytest.raises(ValueError):
        FramePacket(np.zeros((3, 3, 3), dtype=np.uint8), 'BGR', 1, 1, 10, geometry.geometry_id, geometry=geometry)


class WindowAPI:
    def __init__(self):
        self.minimized = False
        self.contexts = []
    def SetThreadDpiAwarenessContext(self, context):
        self.contexts.append(context)
        return 123
    def FindWindowW(self, cls, title):
        assert cls == 'DagorWClass' and title is None
        return 99
    def IsWindow(self, hwnd): return True
    def IsWindowVisible(self, hwnd): return True
    def IsIconic(self, hwnd): return self.minimized
    def GetClientRect(self, hwnd, rect):
        rect._obj.left, rect._obj.top, rect._obj.right, rect._obj.bottom = 0, 0, 1280, 720
        return True
    def ClientToScreen(self, hwnd, point):
        point._obj.x -= 1500
        point._obj.y += 100
        return True
    def GetDpiForWindow(self, hwnd): return 96


def test_windows_uses_client_bounds_under_dpi_context_and_rejects_minimized():
    geometry_type()
    from autonavy.windows import WindowsGeometry
    from autonavy.config import GeometrySettings
    api = WindowAPI()
    adapter = WindowsGeometry(GeometrySettings(), api=api)
    geometry = adapter.snapshot((1280, 720))
    assert geometry.client_rect == (-1500, 100, -220, 820)
    assert geometry.window_handle == 99
    assert api.contexts == [-4, 123]
    api.minimized = True
    with pytest.raises(ValueError, match='window'):
        adapter.snapshot((1280, 720))
    assert api.contexts[-1] == 123
