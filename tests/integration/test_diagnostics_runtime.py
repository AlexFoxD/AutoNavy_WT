"""Diagnostics integrated into real tick/input/capture boundaries; fake display only."""

from dataclasses import replace
import logging
from types import SimpleNamespace
import numpy as np
from autonavy.app import Application
from autonavy.config import Settings
from autonavy.geometry import GeometrySnapshot
from autonavy.models import FramePacket
from autonavy.telemetry import OfflineTelemetry
from autonavy.vision.detectors import VisionPipeline


def packet(serial=1):
    geometry = GeometrySnapshot((0, 0, 1280, 720), (1280, 720), (0, 0, 1280, 720))
    import time

    return FramePacket(
        np.zeros((720, 1280, 3), np.uint8),
        "BGR",
        serial,
        1,
        time.monotonic_ns(),
        geometry.geometry_id,
        geometry=geometry,
    )


def test_real_tick_metrics_preview_uses_already_throttled_image_and_logs_planner(
    caplog,
):
    s = Settings()
    s = replace(s, diagnostics=replace(s.diagnostics, preview=True, metrics_samples=2))
    shown = []
    display = SimpleNamespace(show=shown.append, close=lambda: shown.append("closed"))
    now = [0.0]
    vision = VisionPipeline(s, clock=lambda: now[0])
    app = Application(s, telemetry=OfflineTelemetry(), vision=vision, display=display)
    app.policy.navigation.last_error = "native planner sentinel"
    with caplog.at_level(logging.WARNING):
        app.tick(packet(1))
        debug = app.last_observations.debug_image
        app.tick(packet(2))
        app.tick()
    assert shown == [debug]
    assert sum("native planner sentinel" in r.message for r in caplog.records) == 1
    report = app.metrics.snapshot()
    assert report["samples"]["decision_ns"]["count"] == 2
    assert report["samples"]["idle_tick_ns"]["count"] == 1
    assert report["samples"]["vision_ns"]["count"] == 2
    assert report["samples"]["receive_age_ns"]["count"] == 2
    app.close()
    assert shown[-1] == "closed"


def test_disabled_preview_never_uses_injected_display():
    display = SimpleNamespace(
        show=lambda image: (_ for _ in ()).throw(AssertionError("display")),
        close=lambda: None,
    )
    app = Application(
        Settings(),
        telemetry=OfflineTelemetry(),
        vision=VisionPipeline(Settings()),
        display=display,
    )
    app.tick(packet())
    assert not app.settings.diagnostics.per_frame
    app.close()


def test_actual_dispatch_reports_intent_creation_to_dispatch_without_values():
    from autonavy.metrics import Metrics
    from autonavy.input.controller import InputController, InputIntent, RecordingBackend

    metrics = Metrics()
    clock = [100]
    controller = InputController(
        RecordingBackend(),
        guard=lambda intent: True,
        clock_ns=lambda: clock[0],
        metrics=metrics,
    )
    controller.start()
    controller.set_mode("ui")
    controller.submit(
        InputIntent(
            "ui",
            "move",
            "pointer",
            (3, 4),
            100,
            1000,
            controller.generation("ui"),
            requires_telemetry=False,
        )
    )
    clock[0] = 150
    controller.tick()
    report = metrics.snapshot()
    assert report["samples"]["intent_to_dispatch_ns"]["p50"] == 50
    assert report["counters"]["input_dispatches"] == 1
    assert "pointer" not in str(report)
    controller.close()


def test_capture_statistics_count_real_delivery_gaps_and_idle():
    from tests.integration.test_capture_runtime import make_capture
    from autonavy.capture.base import CaptureTimeout
    import time

    capture = make_capture()
    try:
        capture.start()
        first = capture.read()
        time.sleep(0.06)
        second = capture.read()
        stats = capture.statistics
        assert stats["delivered"] == 2
        assert stats["publication_gaps"] == second.publication_id - 2
        assert (
            stats["publication_gaps"]
            >= second.publication_id - first.publication_id - 1
        )
        stats["delivered"] = 99
        assert capture.statistics["delivered"] == 2
    finally:
        capture.close()
    idle = make_capture(4)
    try:
        idle.start()
        try:
            idle.read(timeout=0.02)
        except CaptureTimeout:
            pass
        assert idle.statistics["idle_reads"] == 1 and idle.statistics["failures"] == 0
    finally:
        idle.close()


def test_capture_child_error_payload_contains_bounded_traceback():
    from autonavy.capture.process import _Shared, _write_error
    import multiprocessing

    shared = _Shared(multiprocessing.get_context("spawn"), 1)
    try:
        raise RuntimeError("source sentinel")
    except RuntimeError as exc:
        _write_error(shared, exc)
    message = bytes(shared.error_text[: shared.error_size.value]).decode()
    assert "Traceback" in message and "source sentinel" in message
    assert shared.error_size.value <= 4096


def test_check_config_is_inert_and_replay_cli_writes_bounded_runtime_summary(tmp_path):
    from autonavy.cli import main

    config = tmp_path / "diagnostics.toml"
    logs = tmp_path / "output"
    config.write_text('[paths]\nlogs = "' + logs.as_posix() + '"\n')
    assert main(["--check-config", "--config", str(config)]) == 0
    assert not logs.exists()
    assert (
        main(
            [
                "--config",
                str(config),
                "--capture",
                "replay",
                "--fixture",
                "tests/fixtures/smoke",
                "--max-frames",
                "2",
            ]
        )
        == 0
    )
    text = (logs / "autonavy.log").read_text(encoding="utf-8")
    assert "runtime_metrics=" in text and "decision_ns" in text
    assert "resolved_settings=" in text and "source_render_latency=unknown" in text
    assert "frame=1 generation=" not in text
    assert not list(logs.glob("*.png"))


def test_explicit_per_frame_logging_connects_publication_and_tick_timing(caplog):
    settings = Settings()
    settings = replace(
        settings, diagnostics=replace(settings.diagnostics, per_frame=True)
    )
    app = Application(
        settings, telemetry=OfflineTelemetry(), vision=VisionPipeline(settings)
    )
    with caplog.at_level(logging.INFO):
        app.tick(packet())
    frame_logs = [
        r.message
        for r in caplog.records
        if "frame=1 generation=1 backend=" in r.message
    ]
    assert len(frame_logs) == 1 and "tick_ns=" in frame_logs[0]
    assert "receive_age_ns=" in frame_logs[0]
    app.close()
