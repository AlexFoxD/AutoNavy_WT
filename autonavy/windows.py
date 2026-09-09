"""Lazy Windows client geometry; no device or GUI initialization on import."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

from autonavy.geometry import GeometrySnapshot


def _user32():
    api = ctypes.WinDLL('user32', use_last_error=True)
    signatures = {
        'SetThreadDpiAwarenessContext': ([ctypes.c_void_p], ctypes.c_void_p),
        'FindWindowW': ([wintypes.LPCWSTR, wintypes.LPCWSTR], wintypes.HWND),
        'IsWindow': ([wintypes.HWND], wintypes.BOOL),
        'IsWindowVisible': ([wintypes.HWND], wintypes.BOOL),
        'IsIconic': ([wintypes.HWND], wintypes.BOOL),
        'GetClientRect': ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
        'ClientToScreen': ([wintypes.HWND, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
        'GetDpiForWindow': ([wintypes.HWND], wintypes.UINT),
    }
    for name, (args, result) in signatures.items():
        method = getattr(api, name)
        method.argtypes, method.restype = args, result
    return api


class WindowsGeometry:
    def __init__(self, settings, *, api=None):
        self.settings = settings
        self.api = api

    def snapshot(self, frame_size) -> GeometrySnapshot:
        api = self.api if self.api is not None else _user32()
        # Per-thread awareness also works when a packaged host already set process DPI policy.
        previous = api.SetThreadDpiAwarenessContext(-4)
        if not previous:
            raise ValueError('Cannot establish per-monitor DPI awareness for game window')
        try:
            hwnd = api.FindWindowW(self.settings.window_class, self.settings.window_title or None)
            if not hwnd or not api.IsWindow(hwnd) or not api.IsWindowVisible(hwnd) or api.IsIconic(hwnd):
                raise ValueError('Game window is missing, hidden, or minimized')
            rect = wintypes.RECT()
            if not api.GetClientRect(hwnd, ctypes.byref(rect)):
                raise ValueError('Cannot obtain game window client rectangle')
            top_left, bottom_right = wintypes.POINT(rect.left, rect.top), wintypes.POINT(rect.right, rect.bottom)
            if not api.ClientToScreen(hwnd, ctypes.byref(top_left)) or not api.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
                raise ValueError('Cannot map game window client to desktop')
            return GeometrySnapshot((top_left.x, top_left.y, bottom_right.x, bottom_right.y),
                                    frame_size, (0, 0, *frame_size), dpi=int(api.GetDpiForWindow(hwnd)),
                                    profile_id=self.settings.profile_id, ui_scale=self.settings.ui_scale,
                                    window_handle=int(hwnd), profile_size=(self.settings.width, self.settings.height))
        finally:
            api.SetThreadDpiAwarenessContext(previous)
