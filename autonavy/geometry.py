"""Pure immutable mappings between frame, ROI, and desktop coordinates."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math


@dataclass(frozen=True)
class GeometrySnapshot:
    client_rect: tuple[int, int, int, int]
    frame_size: tuple[int, int]
    content_rect: tuple[int, int, int, int]
    dpi: int = 96
    profile_id: str = 'legacy-1280x720'
    ui_scale: float = 1.0
    window_handle: int = 0
    profile_size: tuple[int, int] = (1280, 720)
    source_id: str = 'desktop'

    def __post_init__(self):
        for name, count in (('client_rect', 4), ('frame_size', 2), ('content_rect', 4), ('profile_size', 2)):
            values = tuple(getattr(self, name))
            if len(values) != count or any(type(v) is not int for v in values):
                raise ValueError(f'{name} requires {count} integer coordinates')
            object.__setattr__(self, name, values)
        l, t, r, b = self.client_rect
        x, y, right, bottom = self.content_rect
        w, h = self.frame_size
        if not (l < r and t < b and 0 <= x < right <= w and 0 <= y < bottom <= h):
            raise ValueError('Client and content rectangles must be nonempty and content within frame')
        if self.dpi <= 0 or min(self.profile_size) <= 0 or not math.isfinite(self.ui_scale) or self.ui_scale <= 0 or not self.profile_id:
            raise ValueError('Invalid DPI or profile')

    @property
    def geometry_id(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:24]

    @property
    def recognition_supported(self) -> bool:
        l, t, r, b = self.client_rect
        a, top, c, d = self.content_rect
        return (self.profile_id == 'legacy-1280x720' and self.ui_scale == 1.0 and self.profile_size == (1280, 720) and (r-l, b-t) == (1280, 720) and (c-a, d-top) == (1280, 720))

    @property
    def content_center(self) -> tuple[float, float]:
        a, b, c, d = self.content_rect
        return (a+c)/2, (b+d)/2

    def profile_to_frame(self, point) -> tuple[float, float]:
        """Pure transform; scaling support does not imply calibrated recognition."""
        x, y = point
        w, h = self.profile_size
        if not (math.isfinite(x) and math.isfinite(y) and 0 <= x < w and 0 <= y < h):
            raise ValueError('Point is outside reference profile')
        a, b, c, d = self.content_rect
        return a+x*(c-a)/w, b+y*(d-b)/h

    def frame_to_profile(self, point) -> tuple[float, float]:
        x, y = point
        a, b, c, d = self.content_rect
        if not (math.isfinite(x) and math.isfinite(y) and a <= x < c and b <= y < d):
            raise ValueError('Frame point is outside game content')
        w, h = self.profile_size
        return (x-a)*w/(c-a), (y-b)*h/(d-b)

    def frame_to_desktop(self, point, *, _edge=False) -> tuple[float, float]:
        x, y = point
        a, b, c, d = self.content_rect
        if not (math.isfinite(x) and math.isfinite(y) and a <= x <= c and b <= y <= d) or (not _edge and (x == c or y == d)):
            raise ValueError('Frame point is outside game content')
        l, t, r, bottom = self.client_rect
        return l + (x-a)*(r-l)/(c-a), t + (y-b)*(bottom-t)/(d-b)

    def desktop_to_frame(self, point) -> tuple[float, float]:
        x, y = point
        l, t, r, b = self.client_rect
        if not (math.isfinite(x) and math.isfinite(y) and l <= x < r and t <= y < b):
            raise ValueError('Desktop point is outside client')
        a, top, c, d = self.content_rect
        return a+(x-l)*(c-a)/(r-l), top+(y-t)*(d-top)/(b-t)

    def roi_to_desktop(self, point, roi) -> tuple[float, float]:
        x, y = point
        l, t, r, b = roi
        if not (0 <= l < r <= self.frame_size[0] and 0 <= t < b <= self.frame_size[1]
                and 0 <= x < r-l and 0 <= y < b-t):
            raise ValueError('ROI or point is outside frame')
        return self.frame_to_desktop((l+x, t+y))

    def frame_box_to_desktop(self, box) -> tuple[float, float, float, float]:
        l, t, r, b = box
        if not (l < r and t < b):
            raise ValueError('Box must be nonempty')
        return (*self.frame_to_desktop((l, t)), *self.frame_to_desktop((r, b), _edge=True))

    def output_region(self, output_rect) -> tuple[int, int, int, int]:
        a, top, c, d = output_rect
        l, t, r, b = self.client_rect
        if not (a <= l < r <= c and top <= t < b <= d):
            raise ValueError('Game client is outside selected capture output')
        return l-a, t-top, r-a, b-top

    def diagnostic(self) -> dict:
        a, b, c, d = self.content_rect
        l, t, r, bottom = self.client_rect
        return dict(asdict(self), geometry_id=self.geometry_id, recognition_supported=self.recognition_supported,
                    effective_scale=((r-l)/(c-a), (bottom-t)/(d-b)),
                    proposed_center=self.frame_to_desktop(((a+c)/2, (b+d)/2)))


def source_geometry(settings, snapshot: GeometrySnapshot) -> GeometrySnapshot:
    """Apply manual source calibration identically in capture and live input guard."""
    if settings.capture.backend == 'obs':
        c = settings.capture
        return replace(snapshot, content_rect=settings.geometry.obs_content_rect,
                       source_id=f'obs:{c.device_index}:{c.obs_api}')
    return snapshot
