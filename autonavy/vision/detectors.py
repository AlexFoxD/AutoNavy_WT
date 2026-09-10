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


def find_target_reticle(image, edge_map=None):
    """Find the current WT selected-enemy reticle in a BGR ROI.

    Use two Hough passes. The first preserves the conservative live detector.
    If it produces no trustworthy candidate, a second lower-accumulator pass
    recovers faint/partially occluded rings.

    Every candidate still needs red hostile-HUD context and a real circular
    edge signature, so the relaxed pass does not simply accept arbitrary circles.
    Returns (x, y, radius, confidence) in ROI-local coordinates, or None.
    """
    if image is None or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 64:
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    if edge_map is None:
        # Standalone helper fallback used by characterization/unit tests.
        # Runtime passes FrameContext-cached edges to preserve the
        # one-derivative-per-ROI-per-packet invariant.
        edge_map = cv2.Canny(gray, 80, 160)
    else:
        edge_map = np.asarray(edge_map)
        if edge_map.ndim != 2 or edge_map.shape != gray.shape or edge_map.dtype != np.uint8:
            raise ValueError('Reticle edge map must match ROI as single-channel uint8')

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red_low = cv2.inRange(hsv, (0, 60, 70), (15, 255, 255))
    red_high = cv2.inRange(hsv, (165, 60, 70), (180, 255, 255))
    red = cv2.bitwise_or(red_low, red_high)

    passes = (
        # Existing conservative detector.
        dict(param2=30, min_radius=16, max_radius=28,
             min_support=80, min_near=20, min_ring=.18),
        # Recovery pass for weaker/partially occluded current HUD rings.
        dict(param2=22, min_radius=12, max_radius=30,
             min_support=50, min_near=12, min_ring=.18),
    )

    for options in passes:
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=32,
            param1=100,
            param2=options['param2'],
            minRadius=options['min_radius'],
            maxRadius=options['max_radius'],
        )
        if circles is None:
            continue

        best = None
        for cx, cy, raw_radius in circles[0]:
            x = int(round(float(cx)))
            y = int(round(float(cy)))
            radius = int(round(float(raw_radius)))

            # Hostile UI support around the selected target.
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

            if support < options['min_support'] or near < options['min_near']:
                continue

            # Measure how much of the proposed circumference is backed by real
            # image edges. This is what rejects red text/ship geometry that only
            # happens to make HoughCircles return a nearby candidate.
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
            if ring_coverage < options['min_ring']:
                continue

            # Ranking favours a genuine circular edge first. Red context then
            # disambiguates the target ring from neutral circular HUD/ship detail.
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

        if best is not None:
            metric, x, y, radius = best
            confidence = min(1.0, metric / 1.8)
            return x, y, radius, confidence

    return None


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
        for name, threshold in (('crash_warning',v.collision_threshold),('crashed',.3)):
            if name not in selected: continue
            matches[name] = match_template(ctx,self.registry,name,collision_roi,threshold,settings=v,
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
