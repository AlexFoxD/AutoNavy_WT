"""Finite deterministic pixels; legacy arithmetic is extracted, never imported.

Source 45fc36c: toolkit/scn.py match_img, firesystem.py fire mask, and
 toolkit/deg_cal.py get_deg. Timed pairs have equal pixels/parameters and explicit
boundaries. The actual offline decision stage has no legacy speedup comparison.
"""

import argparse
from dataclasses import replace
import hashlib
from pathlib import Path
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from autonavy.app import Application
from autonavy.config import load_settings
from autonavy.geometry import GeometrySnapshot
from autonavy.models import FramePacket
from autonavy.telemetry import OfflineTelemetry
from autonavy.vision.context import FrameContext
from autonavy.vision.detectors import VisionPipeline, match_edges
from autonavy.vision.templates import TemplateRegistry
from scripts.benchmark_common import environment, timing_row, write_report

TOLERANCE = 6e-6


def fixture(settings, registry, seed):
    image = np.random.default_rng(seed).integers(0, 256, (720, 1280, 3), dtype=np.uint8)
    image[200:510, 370:910] = 0
    aim = registry.image("aim")  # IMREAD_UNCHANGED is essential for alpha-only cir.png.
    stencil = aim[:, :, 3] > 127
    image[300 : 300 + aim.shape[0], 540 : 540 + aim.shape[1]][stencil] = (0, 255, 0)
    image[545:615, 85:145] = 0
    cv2.fillPoly(
        image, [np.array([(110, 550), (120, 550), (115, 580)], np.int32)], (0, 255, 0)
    )
    geometry = GeometrySnapshot((0, 0, 1280, 720), (1280, 720), (0, 0, 1280, 720))
    return FramePacket(
        image, "BGR", 1, 1, time.monotonic_ns(), geometry.geometry_id, geometry=geometry
    )


def legacy_preprocess(image, template):
    return (
        cv2.cvtColor(cv2.Canny(image, 100, 200), cv2.COLOR_BGR2BGRA),
        cv2.cvtColor(cv2.Canny(template, 100, 200), cv2.COLOR_BGR2BGRA),
    )


def legacy_match(background, template):
    surface = cv2.matchTemplate(background, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(surface)
    return score, location


def legacy_fire_mask(image, settings):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv, np.array(settings.fire_hsv_lower), np.array(settings.fire_hsv_upper)
    )
    left, top, right, bottom = settings.fire_roi
    return mask[top:bottom, left:right]


def legacy_heading_mask(image, settings):
    left, top, right, bottom = settings.heading_roi
    hsv = cv2.cvtColor(image[top:bottom, left:right], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv, np.array(settings.heading_hsv_lower), np.array(settings.heading_hsv_upper)
    )
    kernel = np.ones((1, 1), np.uint8)
    return cv2.morphologyEx(
        cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel), cv2.MORPH_OPEN, kernel
    )


def correctness(packet, registry, settings):
    """Fail closed before collecting timings, comparing complete score surfaces."""
    v = settings.vision
    context = FrameContext(packet)
    legacy_mask = legacy_fire_mask(packet.image, v)
    new_mask = context.mask(v.fire_roi, v.fire_hsv_lower, v.fire_hsv_upper, 1)
    np.testing.assert_array_equal(legacy_mask, new_mask)
    np.testing.assert_array_equal(
        legacy_heading_mask(packet.image, v),
        context.mask(v.heading_roi, v.heading_hsv_lower, v.heading_hsv_upper, 1),
    )
    legacy_background = cv2.Canny(legacy_mask, v.canny_low, v.canny_high)
    new_background = context.edges(
        v.fire_roi, v, mask=(v.fire_hsv_lower, v.fire_hsv_upper, 1)
    )
    np.testing.assert_array_equal(legacy_background, new_background)
    raw = registry.image("aim")
    assert raw.shape[2] == 4, "Aim raw channels were lost"
    legacy_template = cv2.Canny(raw, v.canny_low, v.canny_high)
    edge = registry.edges("aim", settings=v)
    np.testing.assert_array_equal(legacy_template, edge)
    expanded = cv2.matchTemplate(
        cv2.cvtColor(legacy_background, cv2.COLOR_BGR2BGRA),
        cv2.cvtColor(legacy_template, cv2.COLOR_BGR2BGRA),
        cv2.TM_CCOEFF_NORMED,
    )
    single = cv2.matchTemplate(new_background, edge, cv2.TM_CCOEFF_NORMED)
    np.testing.assert_allclose(single, expanded, atol=TOLERANCE, rtol=0)
    assert cv2.minMaxLoc(single)[3] == cv2.minMaxLoc(expanded)[3] == (170, 100)
    old_bg, old_template = legacy_preprocess(packet.image, registry.image("start"))
    np.testing.assert_array_equal(context.edges((0, 0, 1280, 720), v), old_bg[:, :, 0])
    np.testing.assert_array_equal(
        registry.edges("start", settings=v), old_template[:, :, 0]
    )
    return dict(
        passed=True,
        aim_channels=raw.shape[2],
        score_tolerance=TOLERANCE,
        maximum_score_error=float(np.max(np.abs(single - expanded))),
        aim_location=[170, 100],
        mask_pixel_equality=True,
        preprocessing_pixel_equality=True,
    )


def run_benchmark(*, samples=20, warmups=3, seed=42, repetitions=3):
    for name, value, lower, upper in (
        ("samples", samples, 1, 10000),
        ("warmups", warmups, 0, 1000),
        ("repetitions", repetitions, 1, 20),
    ):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f"{name} must be an integer between {lower} and {upper}")
    settings = load_settings()
    registry = TemplateRegistry.from_settings(settings)
    packet = fixture(settings, registry, seed)
    gates = correctness(packet, registry, settings)
    v = settings.vision
    bg = FrameContext(packet).edges(
        v.fire_roi, v, mask=(v.fire_hsv_lower, v.fire_hsv_upper, 1)
    )
    template = registry.edges("aim", settings=v)
    expanded_bg, expanded_template = (
        cv2.cvtColor(a, cv2.COLOR_BGR2BGRA) for a in (bg, template)
    )
    groups = [
        (
            "preprocess",
            "full-frame color Canny + start template; cached static template in v2",
            {
                "legacy": lambda: legacy_preprocess(
                    packet.image, registry.image("start")
                ),
                "v2": lambda: (
                    FrameContext(packet).edges((0, 0, 1280, 720), v),
                    registry.edges("start", settings=v),
                ),
            },
        ),
        (
            "match",
            "prepared fire ROI/aim edges; legacy BGRA vs validated v2 single-channel match",
            {
                "legacy": lambda: legacy_match(expanded_bg, expanded_template),
                "v2": lambda: match_edges(bg, template, 0),
            },
        ),
        (
            "hsv_mask",
            "identical fire ROI output; legacy full-frame HSV/mask vs v2 crop first",
            {
                "legacy": lambda: legacy_fire_mask(packet.image, v),
                "v2": lambda: FrameContext(packet).mask(
                    v.fire_roi, v.fire_hsv_lower, v.fire_hsv_upper, 1
                ),
            },
        ),
        (
            "heading_mask",
            "identical 60x70 heading mask; legacy identity morphology vs bounded v2 context",
            {
                "legacy": lambda: legacy_heading_mask(packet.image, v),
                "v2": lambda: FrameContext(packet).mask(
                    v.heading_roi, v.heading_hsv_lower, v.heading_hsv_upper, 1
                ),
            },
        ),
        (
            "cold_registry",
            "all selected assets: file read/decode, owned copies and edge preparation; warm OS filesystem cache possible",
            {"v2": lambda: TemplateRegistry.from_settings(settings)},
        ),
    ]
    rows = []
    for repetition in range(1, repetitions + 1):
        for stage, scope, variants in groups:
            names = list(variants)
            for name in names:
                for _ in range(warmups):
                    variants[name]()
            values = {name: [] for name in names}
            for index in range(samples):
                # Alternate paired order to reduce systematic run-order bias.
                order = names if (index + repetition) % 2 else names[::-1]
                for name in order:
                    started = time.perf_counter_ns()
                    variants[name]()
                    values[name].append(time.perf_counter_ns() - started)
            for name in names:
                rows.append(
                    timing_row(
                        stage,
                        name,
                        values[name],
                        warmups=warmups,
                        repetition=repetition,
                        scope=scope,
                    )
                )
    # Fresh packet ownership/copy and receive timestamp are outside the timed tick.
    # Real vision selection, policy, guards, input owner and metrics execute inside.
    app = Application(
        settings,
        telemetry=OfflineTelemetry(),
        vision=VisionPipeline(settings, registry),
    )
    identity = 0
    try:
        for repetition in range(1, repetitions + 1):
            values = []
            for index in range(warmups + samples):
                identity += 1
                fresh = replace(
                    packet, publication_id=identity, received_at_ns=time.monotonic_ns()
                )
                started = time.perf_counter_ns()
                app.tick(fresh)
                elapsed = time.perf_counter_ns() - started
                assert (
                    app.last_observations.packet is fresh
                    and app.last_observations.recognition_supported
                )
                if index >= warmups:
                    values.append(elapsed)
            rows.append(
                timing_row(
                    "decision",
                    "v2",
                    values,
                    warmups=warmups,
                    repetition=repetition,
                    scope="actual Application.tick: supported-profile fresh pixels, vision + menu policy + dry input owner; no telemetry/native planner",
                )
            )
        decision = dict(
            frames_processed=app.frames_processed,
            recognition_supported=app.last_observations.recognition_supported,
            packet_copy_in_timing=False,
            native_planner_measured=False,
            state=app.state.value,
            metrics=app.metrics.snapshot(),
        )
    finally:
        app.close()
    comparisons = []
    for stage, _, variants in groups:
        if "legacy" not in variants:
            continue
        ratios = []
        for repetition in range(1, repetitions + 1):
            pair = {
                r["variant"]: r["p50_ns"]
                for r in rows
                if r["stage"] == stage and r["repetition"] == repetition
            }
            ratios.append(pair["v2"] / pair["legacy"])
        comparisons.append(
            dict(
                stage=stage,
                v2_over_legacy_median_ratios=ratios,
                repeated_regression_over_10_percent=sum(r > 1.1 for r in ratios) >= 2,
            )
        )
    return dict(
        schema_version=1,
        kind="pipeline",
        environment=environment(),
        provenance=dict(
            seed=seed,
            legacy_commit="45fc36c",
            legacy_sources=[
                "toolkit/scn.py:match_img",
                "firesystem.py:fire_control.lock_and_fire",
                "toolkit/deg_cal.py:get_deg",
            ],
            fixture="seeded uint8 noise, alpha-aim green stencil and heading triangle; synthetic only",
            frame_shape=list(packet.image.shape),
            frame_sha256=hashlib.sha256(packet.image.tobytes()).hexdigest(),
            assets_sha256={
                name: hashlib.sha256(registry.image(name).tobytes()).hexdigest()
                for name in registry.names
            },
        ),
        correctness=gates,
        decision=decision,
        comparisons=comparisons,
        timings=rows,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output", type=Path, default=Path("logs/v2/benchmarks/pipeline")
    )
    args = parser.parse_args(argv)
    report = run_benchmark(
        samples=args.samples,
        warmups=args.warmups,
        repetitions=args.repetitions,
        seed=args.seed,
    )
    for path in write_report(report, args.output):
        print(path)
    for result in report["comparisons"]:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
