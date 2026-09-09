"""Original repository assets in generated frames; never game recordings."""
from dataclasses import replace
from pathlib import Path
import importlib.util
import math

import cv2
import numpy as np
import pytest

from autonavy.config import load_settings, VisionSettings
from autonavy.geometry import GeometrySnapshot
from autonavy.models import FramePacket

ROOT = Path(__file__).resolve().parents[2]


def api():
    assert (ROOT / 'autonavy/vision/context.py').is_file(), 'packet-bound vision is not implemented'
    from autonavy.vision.context import FrameContext
    from autonavy.vision.templates import TemplateRegistry, TemplateError
    from autonavy.vision.detectors import match_template, detect_degree, VisionPipeline
    return FrameContext, TemplateRegistry, TemplateError, match_template, detect_degree, VisionPipeline


def packet(image=None, geometry=None, sequence=7):
    if image is None:
        image = np.zeros((720, 1280, 3), np.uint8)
    return FramePacket(image, 'BGRA' if image.shape[2] == 4 else 'BGR', sequence, 2, 123,
                       geometry.geometry_id if geometry else 'synthetic', geometry=geometry)


def geometry():
    return GeometrySnapshot((-1300, 80, -20, 800), (1280, 720), (0, 0, 1280, 720))


def asset(name):
    return cv2.imread(str(ROOT / name), cv2.IMREAD_COLOR)


@pytest.mark.parametrize('name', ['src/game_image/start.png', 'src/cir.png', 'src/crash_warning.png', 'src/game_image/lock.png'])
def test_repository_asset_single_channel_characterization(name):
    template = cv2.imread(str(ROOT/name), cv2.IMREAD_UNCHANGED) if name == 'src/cir.png' else asset(name)
    bg = np.zeros((300, 420, template.shape[2]), np.uint8)
    h, w = template.shape[:2]
    bg[81:81+h, 97:97+w] = template
    a, b = cv2.Canny(bg, 100, 200), cv2.Canny(template, 100, 200)
    single = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)
    expanded = cv2.matchTemplate(cv2.cvtColor(a, cv2.COLOR_GRAY2BGRA),
                                cv2.cvtColor(b, cv2.COLOR_GRAY2BGRA), cv2.TM_CCOEFF_NORMED)
    assert cv2.minMaxLoc(single)[3] == cv2.minMaxLoc(expanded)[3] == (97, 81)
    np.testing.assert_allclose(single, expanded, atol=6e-6)


def test_context_roi_hsv_cache_parameters_and_packet_lifetime(monkeypatch):
    Context, *_ = api()
    image = np.random.default_rng(6).integers(0, 256, (720, 1280, 4), dtype=np.uint8)
    ctx = Context(packet(image), max_entries=8)
    roi = (370, 200, 910, 510)
    expected = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2HSV)[200:510, 370:910]
    calls = []
    original = cv2.cvtColor
    def convert(image, code):
        calls.append(image.shape)
        return original(image, code)
    monkeypatch.setattr(cv2, 'cvtColor', convert)
    hsv = ctx.hsv(roi)
    assert ctx.hsv(roi) is hsv
    np.testing.assert_array_equal(hsv, expected)
    assert all(s[:2] == (310, 540) for s in calls)
    assert not hsv.flags.writeable
    first = ctx.mask(roi, (33,109,149), (137,255,255), 1)
    assert ctx.mask(roi, (33,109,149), (137,255,255), 1) is first
    assert ctx.mask(roi, (34,109,149), (137,255,255), 1) is not first
    assert ctx.mask(roi, (33,109,149), (137,255,255), 3) is not first
    for n in range(20):
        ctx.hsv((n, 0, n+20, 20))
    assert ctx.cache_size <= 8
    assert Context(packet(image, sequence=8)).hsv(roi) is not hsv


def test_context_maps_profile_roi_to_letterbox_without_desktop_crop():
    Context, *_ = api()
    g = GeometrySnapshot((-1920, -50, -640, 670), (1400, 800), (60, 40, 1340, 760))
    ctx = Context(packet(np.zeros((800,1400,3), np.uint8), g))
    assert ctx.profile_roi((370,200,910,510)) == (430,240,970,550)
    scaled = GeometrySnapshot((0,0,1280,720), (640,360), (0,0,640,360))
    with pytest.raises(ValueError, match='scal'):
        Context(packet(np.zeros((360,640,3), np.uint8), scaled)).profile_roi((85,545,145,615))
    for roi in ((0,0,0,5), (-1,0,5,5), (0,0,1401,5), (0.5,0,5,5)):
        with pytest.raises(ValueError):
            ctx.hsv(roi)


def test_registry_owns_templates_and_caches_versions_and_color_input(monkeypatch):
    Context, Registry, _, match, *_ = api()
    template = asset('src/game_image/start.png')
    registry = Registry()
    registry.register('start', template)
    original = cv2.Canny
    calls = []
    def canny(image, low, high):
        calls.append(image.shape)
        return original(image, low, high)
    monkeypatch.setattr(cv2, 'Canny', canny)
    edge = registry.edges('start')
    assert registry.edges('start') is edge
    assert calls == [template.shape]
    assert edge.ndim == 2 and not edge.flags.writeable
    template[:] = 0
    assert registry.edges('start') is edge
    assert registry.edges('start', profile_id='other') is not edge
    assert registry.edges('start', settings=replace(VisionSettings(), preprocess_version=2)) is not edge
    assert registry.edges('start', settings=replace(VisionSettings(), canny_low=90)) is not edge
    registry.register('start', asset('src/game_image/start.png'), version=2)
    assert registry.edges('start') is not edge
    assert registry.cache_size <= 64


@pytest.mark.parametrize('bad', [None, np.zeros((0,4,3),np.uint8), np.zeros((5,5,3),np.uint8), np.full((5,5,3),255,np.uint8), np.ones((5,5,2),np.uint8), np.full((5,5),np.nan)])
def test_invalid_template_is_named_failure(bad):
    _, Registry, Error, *_ = api()
    with pytest.raises(Error, match='broken'):
        registry = Registry()
        registry.register('broken', bad)
        registry.edges('broken')


def test_match_positive_negative_oversize_nonfinite_and_coordinates(monkeypatch):
    Context, Registry, _, match, *_ = api()
    template = asset('src/game_image/start.png')
    image = np.zeros((720,1280,3),np.uint8)
    image[250:278,400:502] = template
    registry = Registry()
    registry.register('start', template)
    ctx = Context(packet(image, geometry()))
    result = match(ctx, registry, 'start', (370,200,910,510), .9)
    assert result.available and result.matched and result.score > .9
    legacy_edges = cv2.Canny(image[200:510,370:910],100,200)
    legacy_template = cv2.Canny(template,100,200)
    legacy_score = cv2.minMaxLoc(cv2.matchTemplate(cv2.cvtColor(legacy_edges,cv2.COLOR_GRAY2BGRA),
                       cv2.cvtColor(legacy_template,cv2.COLOR_GRAY2BGRA),cv2.TM_CCOEFF_NORMED))[1]
    assert result.score == pytest.approx(legacy_score,abs=6e-6)
    assert result.frame_box == (400,250,502,278)
    assert result.frame_center == (451,264)
    assert result.desktop_center == (-849,344)
    assert (result.publication_id, result.source_generation, result.geometry_id) == (7,2,geometry().geometry_id)
    missing = match(Context(packet()), registry, 'start', (370,200,910,510), .9)
    assert missing.available and not missing.matched and math.isfinite(missing.score)
    tiny = match(ctx, registry, 'start', (0,0,2,2), .9)
    assert not tiny.available and not tiny.matched and 'larger' in tiny.reason
    for value in (np.nan, np.inf, -np.inf):
        monkeypatch.setattr(cv2, 'matchTemplate', lambda *a: np.full((3,3), value, np.float32))
        invalid = match(ctx, registry, 'start', (370,200,910,510), .9)
        assert not invalid.available and not invalid.matched and invalid.score is None


def test_degree_no_contours_same_packet_and_debug_immutability():
    Context, _, _, _, degree, _ = api()
    blank = degree(Context(packet()))
    assert not blank.available and blank.degrees is None and 'contour' in blank.reason
    image = np.zeros((720,1280,3),np.uint8)
    cv2.fillPoly(image, [np.array([(110,550),(120,550),(115,580)],np.int32)], (0,255,0))
    p = packet(image, geometry())
    ctx = Context(p)
    before = p.image.copy()
    plain = degree(ctx)
    debug = ctx.debug_image()
    drawn = degree(ctx, debug_image=debug)
    assert plain == drawn
    assert plain.available and plain.degrees == pytest.approx(0,abs=5)
    assert plain.publication_id == 7 and plain.geometry_id == p.geometry_id
    assert not np.array_equal(debug, before)
    np.testing.assert_array_equal(p.image, before)


def test_pipeline_real_lock_fallback_fire_collision_and_ammo():
    Context, Registry, _, _, _, Pipeline = api()
    settings = load_settings()
    registry = Registry.from_settings(settings)
    image = np.zeros((720,1280,3),np.uint8)
    lock = asset('src/game_image/lock.png')
    image[385:403,897:953] = lock
    p = packet(image, geometry())
    pipeline = Pipeline(settings, registry)
    observations = pipeline.observe(p)
    assert observations.matches['lock'].matched
    assert observations.matches['lock'].frame_box == (897,385,953,403)
    assert not observations.matches['aim'].matched
    assert observations.packet is p
    assert observations.debug_image is None
    assert observations.recognition_supported
    assert not pipeline.observe(packet(image)).recognition_supported
    pipeline.begin_battle(p)
    assert not pipeline.observe(p).matches['ammo'].available  # Constant baseline is explicitly unavailable.
    image[660:690,480:520] = np.random.default_rng(9).integers(0,256,(30,40,3),dtype=np.uint8)
    p2 = packet(image, geometry(),8)
    pipeline.begin_battle(p2)
    assert pipeline.observe(p2).matches['ammo'].matched
    p3 = packet(image, geometry(),9)
    object.__setattr__(p3, 'source_generation', 3)
    assert not pipeline.observe(p3).matches['ammo'].available
    preview = Pipeline(replace(settings, diagnostics=replace(settings.diagnostics, preview=True)), registry).observe(p)
    assert dict(preview.matches) == dict(observations.matches)
    assert preview.degree == observations.degree and preview.debug_image is not None


def test_legacy_matching_wrappers_and_explicit_degree_input():
    api()
    from toolkit import scn, deg_cal
    template = asset('src/game_image/start.png')
    image = np.zeros((100,200,3),np.uint8)
    image[20:48,40:142] = template
    assert scn.match_img(image,template,.9)[0] == (91,34)
    assert scn.match_img_ltrb(image,template,.9)[0] == ((40,20),(142,48))
    assert scn.match_img(template,image,.9)[0] == -1
    assert deg_cal.get_deg(packet()) is None
    with pytest.raises(TypeError):
        deg_cal.get_deg()


def test_fire_roi_boundary_matches_legacy_mask_then_crop_not_full_frame_canny(monkeypatch):
    Context, Registry, _, match, *_ = api()
    image = np.random.default_rng(29).integers(0,256,(720,1280,3),dtype=np.uint8)
    v = VisionSettings()
    mask = cv2.inRange(cv2.cvtColor(image,cv2.COLOR_BGR2HSV),np.array(v.fire_hsv_lower),np.array(v.fire_hsv_upper))
    expected = cv2.Canny(mask[200:510,370:910],100,200)
    wrong = cv2.Canny(mask,100,200)[200:510,370:910]
    assert not np.array_equal(expected,wrong)  # Neighborhood boundary difference is real.
    ctx = Context(packet(image))
    args = (v.fire_hsv_lower,v.fire_hsv_upper,1)
    actual = ctx.edges(v.fire_roi,v,mask=args)
    np.testing.assert_array_equal(actual,expected)
    assert ctx.edges(v.fire_roi,v,mask=args) is actual
    assert ctx.edges(v.fire_roi,replace(v,canny_high=210),mask=args) is not actual
    assert ctx.edges(v.fire_roi,replace(v,preprocess_version=2),mask=args) is not actual


@pytest.mark.parametrize('name,xy,color', [('aim',(540,300),(0,255,0)),('crash_warning',(480,90),(0,0,255)),('crashed',(540,140),(0,0,255))])
def test_real_marker_compositions_are_recognized_and_negative_frame_is_not(name,xy,color):
    *_, Pipeline = api()
    settings = load_settings()
    pipeline = Pipeline(settings)
    image = np.zeros((720,1280,3),np.uint8)
    source = cv2.imread(str(ROOT/('src/cir.png' if name == 'aim' else f'src/{name}.png')),cv2.IMREAD_UNCHANGED)
    stencil = source[:,:,3] > 127 if source.ndim == 3 else source > 127
    x,y = xy
    image[y:y+stencil.shape[0],x:x+stencil.shape[1]][stencil] = color
    found = pipeline.observe(packet(image,geometry())).matches[name]
    assert found.available and found.matched
    assert found.frame_box == (x,y,x+stencil.shape[1],y+stencil.shape[0])
    absent = pipeline.observe(packet(geometry=geometry())).matches[name]
    assert absent.available and not absent.matched


def test_runtime_derivatives_are_single_channel_once_per_roi_per_packet(monkeypatch):
    Context, Registry, _, _, _, Pipeline = api()
    settings = load_settings()
    registry = Registry.from_settings(settings)
    calls = []
    shapes = []
    canny, matcher = cv2.Canny, cv2.matchTemplate
    def traced_canny(image,*args):
        calls.append(image.shape)
        return canny(image,*args)
    def traced_match(image,template,*args):
        shapes.append((image.ndim,template.ndim,image.dtype,template.dtype))
        return matcher(image,template,*args)
    monkeypatch.setattr(cv2,'Canny',traced_canny)
    monkeypatch.setattr(cv2,'matchTemplate',traced_match)
    pipeline = Pipeline(settings,registry)
    p = packet(geometry=geometry())
    pipeline.observe(p)
    assert calls == [(720,1280,3),(310,540),(40,70),(720,426)]
    assert all(a == b == 2 and c == d == np.uint8 for a,b,c,d in shapes)
    pipeline.observe(packet(geometry=geometry(),sequence=8))
    assert len(calls) == 8  # Per-packet work repeats; static templates do not.


def test_ammo_baseline_is_invalidated_permanently_on_generation_or_geometry_change():
    *_, Pipeline = api()
    pipeline = Pipeline(load_settings())
    image = np.zeros((720,1280,3),np.uint8)
    image[660:690,480:520] = np.random.default_rng(5).integers(0,256,(30,40,3),dtype=np.uint8)
    initial = packet(image,geometry())
    pipeline.begin_battle(initial)
    assert pipeline.observe(initial).matches['ammo'].matched
    moved = GeometrySnapshot((0,0,1280,720),(1280,720),(0,0,1280,720))
    assert not pipeline.observe(packet(image,moved)).matches['ammo'].available
    assert not pipeline.observe(initial).matches['ammo'].available


def test_pipeline_rejects_geometry_for_a_different_configured_profile():
    *_, Pipeline = api()
    settings = load_settings(overrides={'geometry':{'profile_id':'other-profile'}})
    observed = Pipeline(settings).observe(packet(geometry=geometry()))
    assert not observed.recognition_supported
    assert all(not match.available for match in observed.matches.values())


def test_degree_invalid_direction_debug_alias_and_explicit_roi():
    Context, _, _, _, degree, _ = api()
    image = np.zeros((720,1280,3),np.uint8)
    image[580,115] = (0,255,0)
    ctx = Context(packet(image,geometry()))
    observed = degree(ctx)
    assert not observed.available and observed.degrees is None and 'direction' in observed.reason
    with pytest.raises(ValueError,match='copy'):
        degree(ctx,debug_image=ctx.packet.image)
    from toolkit.deg_cal import get_deg
    assert get_deg(image[545:615,85:145]) is None
