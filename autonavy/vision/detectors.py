"""Pure observations from a selected frame; timing and input belong to runtime policy."""
from dataclasses import dataclass, field
import math
import time
from types import MappingProxyType
from typing import Mapping

import cv2
import numpy as np

from autonavy.config import VisionSettings
from autonavy.models import FramePacket
from autonavy.vision.context import FrameContext
from autonavy.vision.templates import GAME_ASSETS, TemplateRegistry


@dataclass(frozen=True)
class MatchObservation:
    publication_id: int
    source_generation: int
    geometry_id: str
    available: bool = False
    matched: bool = False
    score: float | None = None
    frame_box: tuple[int,int,int,int] | None = None
    desktop_center: tuple[float,float] | None = None
    reason: str | None = None

    @property
    def frame_center(self):
        if self.frame_box is None:
            return None
        l,t,r,b = self.frame_box
        return (l+r)//2, (t+b)//2


@dataclass(frozen=True)
class DegreeObservation:
    publication_id: int
    source_generation: int
    geometry_id: str
    available: bool = False
    degrees: float | None = None
    reason: str | None = None


def identity(packet):
    return packet.publication_id, packet.source_generation, packet.geometry_id


def match_edges(background, template, threshold):
    """One matcher implementation shared by packet detectors and compatibility wrappers."""
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        return None, None, 'Threshold must be finite and between zero and one'
    if any(a.ndim != 2 or a.dtype != np.uint8 or a.size == 0 for a in (background,template)):
        return None, None, 'Matcher requires nonempty single-channel uint8 edges'
    if template.shape[0] > background.shape[0] or template.shape[1] > background.shape[1]:
        return None, None, 'Template is larger than ROI'
    if template.min() == template.max():
        return None, None, 'Template has degenerate constant edges'
    surface = cv2.matchTemplate(background, template, cv2.TM_CCOEFF_NORMED)
    if surface.size == 0 or not np.isfinite(surface).all():
        return None, None, 'Nonfinite or empty match score surface'
    _, score, _, location = cv2.minMaxLoc(surface)
    return float(score), location if score >= threshold else None, None


def match_template(context, registry, name, roi, threshold, *, settings=VisionSettings(), mask=None):
    p = context.packet
    # Required-asset errors remain explicit rather than becoming a false no-match.
    edge = registry.edges(name, profile_id=p.geometry.profile_id if p.geometry else 'legacy-1280x720', settings=settings)
    try:
        rect = context._rect(roi)
        background = context.edges(rect, settings, mask=mask)
    except ValueError as exc:
        return MatchObservation(*identity(p), reason=str(exc))
    score, location, reason = match_edges(background, edge, threshold)
    if reason:
        return MatchObservation(*identity(p), reason=reason)
    box = None
    desktop = None
    if location is not None:
        x,y = location[0]+rect[0], location[1]+rect[1]
        box = (x,y,x+edge.shape[1],y+edge.shape[0])
        if p.geometry is not None:
            try:
                desktop = p.geometry.frame_to_desktop(((box[0]+box[2])//2, (box[1]+box[3])//2))
            except ValueError:
                return MatchObservation(*identity(p), reason='Match is outside packet game content')
    return MatchObservation(*identity(p), True, location is not None, score, box, desktop)


def _match_precomputed_edges(context, registry, name, roi, threshold, background_edges, background_rect,
                             *, settings=VisionSettings()):
    """Match a template against a crop of an already-computed edge map.

    This is used only as a geometry fallback for battle markers.  It deliberately
    bypasses context.edges() for the small ROI, so no second Canny derivative is
    created for aim/lock after the masked attempt.
    """
    p = context.packet
    edge = registry.edges(
        name,
        profile_id=p.geometry.profile_id if p.geometry else 'legacy-1280x720',
        settings=settings,
    )
    try:
        rect = context._rect(roi)
        base = context._rect(background_rect)
    except ValueError as exc:
        return MatchObservation(*identity(p), reason=str(exc))

    left, top, right, bottom = rect
    base_left, base_top, base_right, base_bottom = base
    if left < base_left or top < base_top or right > base_right or bottom > base_bottom:
        return MatchObservation(*identity(p), reason='Fallback ROI is outside cached edge map')

    background = background_edges[
        top-base_top:bottom-base_top,
        left-base_left:right-base_left,
    ]
    score, location, reason = match_edges(background, edge, threshold)
    if reason:
        return MatchObservation(*identity(p), reason=reason)

    box = None
    desktop = None
    if location is not None:
        x, y = location[0] + left, location[1] + top
        box = (x, y, x + edge.shape[1], y + edge.shape[0])
        if p.geometry is not None:
            try:
                desktop = p.geometry.frame_to_desktop(
                    ((box[0]+box[2])//2, (box[1]+box[3])//2)
                )
            except ValueError:
                return MatchObservation(
                    *identity(p),
                    reason='Match is outside packet game content',
                )

    return MatchObservation(
        *identity(p),
        True,
        location is not None,
        score,
        box,
        desktop,
    )


def match_template_with_mask_fallback(context, registry, name, roi, threshold, *,
                                      settings=VisionSettings(), mask,
                                      fallback_edges, fallback_rect):
    """Prefer the legacy color-masked detector, then reuse cached plain edges.

    The acceptance threshold is unchanged.  Only the preprocessing representation
    changes on fallback.  Crucially, this still makes exactly one call through
    match_template() per logical detector and does not run Canny again for the
    aim/lock ROI.
    """
    masked = match_template(
        context, registry, name, roi, threshold, settings=settings, mask=mask
    )
    if masked.matched:
        return masked

    plain = _match_precomputed_edges(
        context,
        registry,
        name,
        roi,
        threshold,
        fallback_edges,
        fallback_rect,
        settings=settings,
    )
    if plain.matched:
        return plain

    if plain.score is None:
        return masked
    if masked.score is None or plain.score > masked.score:
        return plain
    return masked


def find_close_target_marker(image):
    """Find the current close-range naval target marker from hostile HUD bands.

    Current WT naval HUD has at least two selected-target presentations:
      * distant target: a circular marker;
      * close target: four corner brackets, with the hostile name/marker above
        and the selected red range readout below.

    The bracket strokes themselves are intentionally not used as the primary
    signal because their contrast depends strongly on sea/sky/ship background.
    The red HUD bands are much more stable.  Their horizontal centers are nearly
    co-linear and their vertical midpoint has a small, stable offset to the
    aiming point.

    Returns (x, y, radius, confidence) in ROI-local coordinates, or None.
    """
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        return None

    h, w = image.shape[:2]
    if h < 100 or w < 100:
        return None

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red_low = cv2.inRange(hsv, (0, 60, 70), (15, 255, 255))
    red_high = cv2.inRange(hsv, (165, 60, 70), (180, 255, 255))
    red = cv2.bitwise_or(red_low, red_high)

    # Collapse red HUD text into horizontal bands. Requiring at least three
    # pixels on a row rejects most isolated antialiasing/minimap noise.
    row_counts = np.count_nonzero(red, axis=1)
    bands = []
    start = None

    for y, count in enumerate(row_counts):
        if count >= 3 and start is None:
            start = y

        is_last = y == h - 1
        if start is not None and (count < 3 or is_last):
            end = y if count < 3 else y + 1
            ys, xs = np.nonzero(red[start:end])

            if xs.size:
                left = int(xs.min())
                right = int(xs.max()) + 1
                bands.append({
                    'y1': start,
                    'y2': end,
                    'yc': (start + end - 1) / 2.0,
                    'x1': left,
                    'x2': right,
                    'xc': float(xs.mean()),
                    'area': int(xs.size),
                    'width': right - left,
                    'height': end - start,
                })
            start = None

    # In the supplied live 1280x720 OBS frame:
    #   hostile name band center ~ y=259
    #   selected red range band ~ y=429
    #   actual aiming point       ~ y=360
    # The +16 correction maps their midpoint to the current close-range marker.
    strong = [
        band for band in bands
        if band['area'] >= 30
        and band['width'] >= 20
        and 4 <= band['height'] <= 24
    ]

    candidates = []
    for upper in strong:
        for lower in strong:
            gap = lower['yc'] - upper['yc']
            if not 110 <= gap <= 210:
                continue

            x_error = abs(lower['xc'] - upper['xc'])
            if x_error > 60:
                continue

            cx = (upper['xc'] + lower['xc']) / 2.0
            cy = (upper['yc'] + lower['yc']) / 2.0 + 16.0

            if not (20 <= cx < w - 20 and 20 <= cy < h - 20):
                continue

            # Prefer vertically paired HUD bands near each other in X and near
            # the active central battle region.  This prevents a remote minimap
            # icon from winning over the selected target.
            norm_distance = math.hypot(
                (cx - w / 2.0) / max(w, 1),
                (cy - h / 2.0) / max(h, 1),
            )
            score = (
                (1.0 - x_error / 60.0)
                + min(1.0, (upper['area'] + lower['area']) / 250.0)
                + max(0.0, 1.0 - norm_distance * 2.0)
            )
            candidates.append((score, cx, cy))

    if not candidates:
        return None

    score, cx, cy = max(candidates, key=lambda item: item[0])

    # Score is a ranking metric in roughly [0, 3]. Map it to observation
    # confidence without pretending it is a template-correlation probability.
    confidence = min(1.0, max(0.0, score / 3.0))
    return int(round(cx)), int(round(cy)), 12, confidence


def find_target_reticle(image, edge_map=None):
    """Find the selected WT naval target in either current HUD presentation.

    Detection order:
      1. close-range bracket HUD, inferred from paired hostile red bands;
      2. distant circular marker, using only the conservative Hough pass.

    The previous relaxed Hough fallback was intentionally removed: on close
    targets the circle is not rendered at all, so relaxed circle search can lock
    onto waves or unrelated circular HUD geometry.
    """
    if image is None or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 64:
        return None

    close_marker = find_close_target_marker(image)
    if close_marker is not None:
        return close_marker

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    if edge_map is None:
        # Standalone helper fallback used by characterization/unit tests.
        # Runtime passes FrameContext-cached edges.
        edge_map = cv2.Canny(gray, 80, 160)
    else:
        edge_map = np.asarray(edge_map)
        if edge_map.ndim != 2 or edge_map.shape != gray.shape or edge_map.dtype != np.uint8:
            raise ValueError('Reticle edge map must match ROI as single-channel uint8')

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red_low = cv2.inRange(hsv, (0, 60, 70), (15, 255, 255))
    red_high = cv2.inRange(hsv, (165, 60, 70), (180, 255, 255))
    red = cv2.bitwise_or(red_low, red_high)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=32,
        param1=100,
        param2=30,
        minRadius=16,
        maxRadius=28,
    )
    if circles is None:
        return None

    best = None
    for cx, cy, raw_radius in circles[0]:
        x = int(round(float(cx)))
        y = int(round(float(cy)))
        radius = int(round(float(raw_radius)))

        pad = max(50, radius * 3)
        left = max(0, x - pad)
        top = max(0, y - pad)
        right = min(image.shape[1], x + pad + 1)
        bottom = min(image.shape[0], y + pad + 1)
        support = int(np.count_nonzero(red[top:bottom, left:right]))

        near_pad = max(25, int(round(radius * 1.8)))
        left2 = max(0, x - near_pad)
        top2 = max(0, y - near_pad)
        right2 = min(image.shape[1], x + near_pad + 1)
        bottom2 = min(image.shape[0], y + near_pad + 1)
        near = int(np.count_nonzero(red[top2:bottom2, left2:right2]))

        if support < 80 or near < 20:
            continue

        ring_pad = radius + 3
        left3 = max(0, x - ring_pad)
        top3 = max(0, y - ring_pad)
        right3 = min(image.shape[1], x + ring_pad + 1)
        bottom3 = min(image.shape[0], y + ring_pad + 1)

        edge_patch = edge_map[top3:bottom3, left3:right3]
        ring_mask = np.zeros(edge_patch.shape, dtype=np.uint8)
        cv2.circle(
            ring_mask,
            (x-left3, y-top3),
            radius,
            255,
            4,
            lineType=cv2.LINE_8,
        )

        ring_pixels = int(np.count_nonzero(ring_mask))
        if ring_pixels == 0:
            continue

        ring_coverage = (
            int(np.count_nonzero(cv2.bitwise_and(edge_patch, ring_mask)))
            / ring_pixels
        )
        if ring_coverage < .18:
            continue

        radius_fit = max(0.0, 1.0 - abs(radius - 21) / 12.0)
        metric = (
            ring_coverage * 2.0
            + min(1.0, near / 250.0) * .7
            + min(1.0, support / 700.0) * .3
            + radius_fit * .25
        )
        candidate = (metric, x, y, radius)
        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is None:
        return None

    metric, x, y, radius = best
    confidence = min(1.0, metric / 1.8)
    return x, y, radius, confidence



def detect_target_reticle(context, roi, *, fallback_edges=None, fallback_rect=None):
    """Return a MatchObservation for the current selected hostile reticle.

    Runtime should pass cached plain edges plus their frame rect.  The helper can
    still operate without them for isolated/legacy callers.
    """
    packet = context.packet
    try:
        rect = context._rect(roi)
        image = context.roi(rect)
    except ValueError as exc:
        return MatchObservation(*identity(packet), reason=str(exc))

    edge_roi = None
    if fallback_edges is not None and fallback_rect is not None:
        try:
            base = context._rect(fallback_rect)
        except ValueError as exc:
            return MatchObservation(*identity(packet), reason=str(exc))

        left, top, right, bottom = rect
        base_left, base_top, base_right, base_bottom = base
        if left < base_left or top < base_top or right > base_right or bottom > base_bottom:
            return MatchObservation(
                *identity(packet),
                reason='Reticle ROI is outside cached edge map',
            )

        edge_roi = fallback_edges[
            top-base_top:bottom-base_top,
            left-base_left:right-base_left,
        ]

    try:
        found = find_target_reticle(image, edge_map=edge_roi)
    except ValueError as exc:
        return MatchObservation(*identity(packet), reason=str(exc))

    if found is None:
        return MatchObservation(*identity(packet), True, False, 0.0)

    x, y, radius, confidence = found
    cx = x + rect[0]
    cy = y + rect[1]
    pad = radius + 2
    box = (cx-pad, cy-pad, cx+pad+1, cy+pad+1)

    desktop = None
    if packet.geometry is not None:
        try:
            desktop = packet.geometry.frame_to_desktop((cx, cy))
        except ValueError:
            return MatchObservation(
                *identity(packet),
                reason='Reticle center is outside packet game content',
            )

    return MatchObservation(
        *identity(packet),
        True,
        True,
        confidence,
        box,
        desktop,
    )



def find_shallow_water_warning(image):
    """Find the current WT naval shallow-water warning in a 1280x720 BGR frame.

    Current naval HUD renders a wide orange warning text band near the top-center
    together with an orange shallow-water indicator below it.  The historical
    crash1.png template is localized text and no longer matches current English
    HUD builds.

    Returns (box, confidence) in frame coordinates, or None.
    """
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        return None

    h, w = image.shape[:2]
    if w < 640 or h < 360:
        return None

    # Characterized from the current 1280x720 OBS profile. Expressed as ratios
    # so the helper remains sane for equivalent scaled frames.
    tx1 = int(round(w * 0.333))
    tx2 = int(round(w * 0.667))
    ty1 = int(round(h * 0.097))
    ty2 = int(round(h * 0.264))

    text_roi = image[ty1:ty2, tx1:tx2]
    hsv = cv2.cvtColor(text_roi, cv2.COLOR_BGR2HSV)

    # Current warning is gold/orange: live pixels cluster near H=20..22.
    orange = cv2.inRange(
        hsv,
        np.array((15, 100, 110), dtype=np.uint8),
        np.array((32, 255, 255), dtype=np.uint8),
    )

    # Join anti-aliased glyphs into one horizontal warning band.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    joined = cv2.morphologyEx(orange, cv2.MORPH_CLOSE, kernel)

    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        joined, 8
    )

    best = None
    for index in range(1, count):
        x, y, bw, bh, area = (int(v) for v in stats[index])

        # Live warning is about 339x28 px at 1280x720. Keep broad margins for
        # localization/font antialiasing while requiring a genuinely wide HUD
        # text line.
        min_width = int(round(text_roi.shape[1] * 0.50))
        max_height = int(round(text_roi.shape[0] * 0.45))
        if bw < min_width or not 12 <= bh <= max_height or area < 1000:
            continue

        gx1, gy1 = tx1 + x, ty1 + y
        gx2, gy2 = gx1 + bw, gy1 + bh
        cx = (gx1 + gx2) // 2

        # The shallow-water hazard icon/range appears directly below the warning.
        # Requiring this orange context prevents unrelated orange notifications
        # from triggering recovery.
        icon_half_w = max(30, int(round(w * 0.047)))
        ix1 = max(0, cx - icon_half_w)
        ix2 = min(w, cx + icon_half_w)
        iy1 = int(round(h * 0.235))
        iy2 = int(round(h * 0.365))

        icon_roi = image[iy1:iy2, ix1:ix2]
        icon_hsv = cv2.cvtColor(icon_roi, cv2.COLOR_BGR2HSV)
        icon_orange = cv2.inRange(
            icon_hsv,
            np.array((15, 100, 110), dtype=np.uint8),
            np.array((32, 255, 255), dtype=np.uint8),
        )
        icon_pixels = int(np.count_nonzero(icon_orange))
        if icon_pixels < 80:
            continue

        width_score = min(1.0, bw / max(1.0, text_roi.shape[1] * 0.75))
        area_score = min(1.0, area / 4000.0)
        icon_score = min(1.0, icon_pixels / 300.0)
        confidence = min(
            1.0,
            0.45 * width_score + 0.35 * area_score + 0.20 * icon_score,
        )

        candidate = (confidence, (gx1, gy1, gx2, gy2))
        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is None:
        return None

    confidence, box = best
    return box, confidence


def detect_shallow_water_warning(context, roi):
    """Return a MatchObservation for the current shallow-water HUD warning."""
    packet = context.packet
    try:
        rect = context._rect(roi)
        image = context.roi(rect)
    except ValueError as exc:
        return MatchObservation(*identity(packet), reason=str(exc))

    found = find_shallow_water_warning(image)
    if found is None:
        return MatchObservation(*identity(packet), True, False, 0.0)

    local_box, confidence = found
    l, t, r, b = local_box
    box = (
        l + rect[0],
        t + rect[1],
        r + rect[0],
        b + rect[1],
    )

    desktop = None
    if packet.geometry is not None:
        center = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
        try:
            desktop = packet.geometry.frame_to_desktop(center)
        except ValueError:
            return MatchObservation(
                *identity(packet),
                reason='Shallow-water warning is outside packet game content',
            )

    return MatchObservation(
        *identity(packet),
        True,
        True,
        confidence,
        box,
        desktop,
    )


def angle_from_mask(mask):
    """Preserve the legacy triangle/line estimator without modifying source pixels."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, contours, 'No heading contours'
    largest = max(contours, key=cv2.contourArea)
    perimeter = cv2.arcLength(largest, True)
    center = (mask.shape[1]//2, mask.shape[0]//2)
    for count in (3,2):
        for i in range(1,10):
            approx = cv2.approxPolyDP(largest, perimeter*(1-i/10), True)
            if len(approx) != count:
                continue
            points = [tuple(map(int, v[0])) for v in approx]
            vertex = min(points, key=lambda p: (p[0]-center[0])**2+(p[1]-center[1])**2)
            points.remove(vertex)
            if count == 3:
                target = ((points[0][0]+points[1][0])//2, (points[0][1]+points[1][1])//2)
                origin = (center[0], vertex[1])
            else:
                target = ((points[0][0]+vertex[0])//2, (points[0][1]+vertex[1])//2)
                origin = (center[0],center[1]+10)
            dx,dy = target[0]-origin[0],target[1]-origin[1]
            if dx == 0 and dy == 0:
                continue
            degrees = (math.degrees(math.atan2(dy,dx))+90+180)%360-180
            return degrees, contours, None
    return None, contours, 'No valid heading direction'


def detect_degree(context, *, settings=VisionSettings(), roi=None, debug_image=None):
    p = context.packet
    try:
        # Explicit frame ROI also permits geometry-free synthetic characterization.
        rect = roi if roi is not None else (context.profile_roi(settings.heading_roi)
                if p.geometry is not None else settings.heading_roi)
        mask = context.mask(rect, settings.heading_hsv_lower, settings.heading_hsv_upper, settings.morphology_size)
    except ValueError as exc:
        return DegreeObservation(*identity(p), reason=str(exc))
    degrees, contours, reason = angle_from_mask(mask)
    if debug_image is not None:
        if np.shares_memory(debug_image, p.image) or debug_image.shape != p.image.shape:
            raise ValueError('Debug image must be an independent full-frame copy')
        cv2.drawContours(debug_image, contours, -1, (0,0,255), 1, offset=(rect[0],rect[1]))
    return DegreeObservation(*identity(p), degrees is not None, degrees, reason)


@dataclass(frozen=True, eq=False)
class VisionObservations:
    packet: FramePacket
    matches: Mapping[str, MatchObservation]
    degree: DegreeObservation
    recognition_supported: bool
    reason: str | None = None
    debug_image: np.ndarray | None = field(default=None, repr=False)


class VisionPipeline:
    def __init__(self, settings, registry=None, *, clock=None):
        self.settings = settings
        self.registry = registry if registry is not None else TemplateRegistry.from_settings(settings)
        self._clock = time.monotonic if clock is None else clock
        self._next_preview_at = None
        self._ammo_registry = None
        self._ammo_identity = None
        self._ammo_error = 'Battle ammo baseline is not initialized'

    def begin_battle(self, packet):
        """M5 calls this once on battle initialization, using its selected packet."""
        self._ammo_registry = None
        self._ammo_identity = None
        try:
            ctx = FrameContext(packet)
            roi = ctx.profile_roi(self.settings.vision.ammo_roi)
            registry = TemplateRegistry()
            registry.register('ammo', ctx.roi(roi))
            registry.edges('ammo', settings=self.settings.vision)
        except ValueError as exc:
            self._ammo_error = f'Ammo baseline unavailable: {exc}'
            return
        self._ammo_registry = registry
        self._ammo_identity = packet.source_generation, packet.geometry_id

    def observe(self, packet, *, selection=None):
        ctx = FrameContext(packet)
        v = self.settings.vision
        if self._ammo_identity is not None and self._ammo_identity != (packet.source_generation,packet.geometry_id):
            self._ammo_registry = None
            self._ammo_identity = None
            self._ammo_error = 'Ammo baseline invalidated by generation or geometry change'
        thresholds = {name:v.template_threshold for name in GAME_ASSETS if name not in ('lock','fire')}
        thresholds.update(start=v.start_threshold, join_game=v.join_threshold, join=v.join_threshold,
                          confirm=v.confirm_threshold, confirm1=v.confirm_threshold, confirm2=v.confirm_threshold,
                          research=v.research_threshold, research1=.6, purchase_confirm=.6, data=.7, wtlogo=.6)
        variants = {'confirm1_queue':'confirm1', 'confirm2_queue':'confirm2', 'start_battle_end':'start'}
        names = (*thresholds, *variants, 'aim','lock','fire','crash_warning','crashed','ammo')
        selected = set(names) | {'degree'} if selection is None else set(selection)
        configured = self.settings.geometry
        supported = (packet.geometry is not None and packet.geometry.recognition_supported
                     and packet.geometry.profile_id == configured.profile_id
                     and packet.geometry.profile_size == (configured.width,configured.height)
                     and packet.geometry.ui_scale == configured.ui_scale)
        if not supported:
            reason = 'Missing packet geometry' if packet.geometry is None else 'Unsupported recognition profile or content scaling'
            matches = {name:MatchObservation(*identity(packet), reason=reason) for name in names}
            return VisionObservations(packet, MappingProxyType(matches), DegreeObservation(*identity(packet),reason=reason), False, reason)
        full = ctx.profile_roi((0,0,self.settings.geometry.width,self.settings.geometry.height))
        matches = {name:MatchObservation(*identity(packet),reason='Detector not selected for current state') for name in names}
        matches.update({name:match_template(ctx,self.registry,name,full,threshold,settings=v)
                        for name,threshold in thresholds.items() if name in selected})
        # Threshold variants reuse preprocessing; scores are never retained across packets.
        for name, template in variants.items():
            if name not in selected: continue
            matches[name] = match_template(ctx,self.registry,template,full,.8 if name == 'start_battle_end' else .6,settings=v)
        # Full-frame plain edges are already cached by the selected full-frame
        # UI/battle templates. Reusing them here preserves the one-Canny-per-ROI
        # runtime invariant even when the color-masked aim/lock detector fails.
        fallback_edges = ctx.edges(full,v) if 'aim' in selected or 'lock' in selected else None
        if 'aim' in selected:
            matches['aim'] = match_template_with_mask_fallback(
                ctx,self.registry,'aim',ctx.profile_roi(v.fire_roi),v.aim_threshold,
                settings=v,mask=(v.fire_hsv_lower,v.fire_hsv_upper,1),
                fallback_edges=fallback_edges,fallback_rect=full)
            if not matches['aim'].matched:
                # Current naval HUD target ring frequently sits above the old
                # fire_roi top boundary and no longer matches cir.png exactly.
                # Search a broader central battle area for the hostile reticle.
                l,t,r,b = v.fire_roi
                reticle_roi = ctx.profile_roi((
                    max(0,l-150),
                    max(0,t-130),
                    min(self.settings.geometry.width,r+150),
                    min(self.settings.geometry.height,b+10),
                ))
                reticle = detect_target_reticle(
                    ctx,
                    reticle_roi,
                    fallback_edges=fallback_edges,
                    fallback_rect=full,
                )
                if reticle.matched:
                    matches['aim'] = reticle
        if 'lock' in selected:
            matches['lock'] = match_template_with_mask_fallback(
                ctx,self.registry,'lock',ctx.profile_roi((890,380,960,420)),v.aim_threshold,
                settings=v,mask=((0,0,0),(180,255,46),1),
                fallback_edges=fallback_edges,fallback_rect=full)
        if 'fire' in selected:
            matches['fire'] = match_template(ctx,self.registry,'fire',full,v.template_threshold,settings=v)
        collision_roi = ctx.profile_roi((self.settings.geometry.width//3,0,self.settings.geometry.width//3*2,self.settings.geometry.height))
        if 'crash_warning' in selected:
            modern_warning = detect_shallow_water_warning(ctx, full)
            if modern_warning.matched:
                matches['crash_warning'] = modern_warning
            else:
                # Legacy localized-template fallback.
                matches['crash_warning'] = match_template(
                    ctx,self.registry,'crash_warning',collision_roi,
                    v.collision_threshold,settings=v,
                    mask=((0,43,46),(10,255,255),1))
        if 'crashed' in selected:
            matches['crashed'] = match_template(
                ctx,self.registry,'crashed',collision_roi,.3,settings=v,
                mask=((0,43,46),(10,255,255),1))
        if 'ammo' in selected and self._ammo_registry is not None and self._ammo_identity == (packet.source_generation,packet.geometry_id):
            matches['ammo'] = match_template(ctx,self._ammo_registry,'ammo',ctx.profile_roi(v.ammo_roi),.9,settings=v)
        else:
            matches['ammo'] = MatchObservation(*identity(packet),reason=self._ammo_error if self._ammo_registry is None else 'Ammo baseline belongs to another generation or geometry')
        debug = None
        if self.settings.diagnostics.preview:
            now = self._clock()
            if self._next_preview_at is None or now >= self._next_preview_at:
                debug = ctx.debug_image()
                # Schedule from this observation; delayed ticks never accumulate previews.
                self._next_preview_at = now + 1 / self.settings.diagnostics.preview_fps
        degree = (detect_degree(ctx,settings=v,debug_image=debug) if 'degree' in selected else
                  DegreeObservation(*identity(packet),reason='Detector not selected for current state'))
        if debug is not None:
            for observation in matches.values():
                if observation.matched:
                    l,t,r,b = observation.frame_box
                    cv2.rectangle(debug,(l,t),(r-1,b-1),(0,255,255),1)
        return VisionObservations(packet,MappingProxyType(matches),degree,True,debug_image=debug)
