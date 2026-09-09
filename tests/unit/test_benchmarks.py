"""Finite offline measurement contracts. No live devices or speed assertions."""

import json
import math
import pytest
from autonavy.config import load_settings


def test_pipeline_correctness_schema_counts_and_fresh_decision_work(tmp_path):
    from scripts.benchmark_pipeline import run_benchmark
    from scripts.benchmark_common import write_report

    report = run_benchmark(samples=1, warmups=0, seed=42, repetitions=1)
    assert report["schema_version"] == 1 and report["kind"] == "pipeline"
    assert report["correctness"]["passed"]
    assert report["correctness"]["aim_channels"] == 4
    assert report["correctness"]["score_tolerance"] == 6e-6
    assert report["decision"]["frames_processed"] == 1
    assert report["decision"]["recognition_supported"]
    assert report["decision"]["packet_copy_in_timing"] is False
    assert {
        "cold_registry",
        "preprocess",
        "match",
        "hsv_mask",
        "heading_mask",
        "decision",
    } <= {r["stage"] for r in report["timings"]}
    for row in report["timings"]:
        assert row["n"] == 1 and row["warmups"] == 0
        assert all(
            math.isfinite(row[key]) and row[key] >= 0
            for key in ("p50_ns", "p95_ns", "mean_ns", "throughput_per_s")
        )
    paths = write_report(report, tmp_path / "result")
    assert json.loads(paths[0].read_text())["correctness"]["passed"]
    assert "p95_ns" in paths[1].read_text()
    assert "opencv-python" in report["environment"]["dependencies"]


@pytest.mark.parametrize(
    "kwargs", [{"samples": 0}, {"warmups": -1}, {"repetitions": 0}, {"samples": 100001}]
)
def test_pipeline_rejects_unbounded_or_empty_requests(kwargs):
    from scripts.benchmark_pipeline import run_benchmark

    with pytest.raises(ValueError):
        run_benchmark(**kwargs)


def test_capture_finite_replay_delivery_schema_and_unknown_latency(tmp_path):
    from scripts.benchmark_capture import run_benchmark
    from scripts.benchmark_common import write_report

    s = load_settings(
        overrides={"capture": {"backend": "replay", "fixture": "tests/fixtures/smoke"}}
    )
    report = run_benchmark(s, duration_s=0.5, max_frames=2)
    assert (
        report["kind"] == "capture"
        and report["mode"] == "synthetic_replay_capture_only"
    )
    assert report["delivery"]["frames"] == 2
    assert report["delivery"]["failures"] == 0
    assert report["delivery"]["publication_gaps"] == 0
    assert report["source_render_latency_ns"] is None
    assert report["source_presentation_rate_hz"] is None
    assert report["intent_to_dispatch_ns"] is None
    assert report["resources"]["scope"] == "benchmark_parent_only"
    assert report["resources"]["isolated_children"] is None
    assert report["settings"]["requested"]["fps"] == 60
    assert report["settings"]["delivered"]["width"] == 1280
    assert report["timings"][0]["n"] == 2
    assert write_report(report, tmp_path / "capture")[0].exists()


def test_capture_factory_selection_is_real_and_never_constructs_input(monkeypatch):
    from scripts import benchmark_capture
    from autonavy.capture.base import CaptureTimeout
    from autonavy.input.controller import InputController

    calls = []

    class Idle:
        diagnostic = {"requested": {"backend": "obs"}, "reported": {"fps": 59}}
        statistics = dict(delivered=0, publication_gaps=0, idle_reads=1, failures=0)

        def start(self):
            calls.append("start")

        def read(self, timeout):
            if len(calls) == 1:
                calls.append("idle")
                raise CaptureTimeout("ordinary idle")
            return None

        def close(self):
            calls.append("close")

    def factory(settings):
        assert settings.capture.backend == "obs" and not settings.input.enable_input
        assert not settings.diagnostics.preview
        return Idle()

    monkeypatch.setattr(benchmark_capture, "create_capture", factory)
    monkeypatch.setattr(
        InputController,
        "__init__",
        lambda *a, **k: pytest.fail("Input must not be constructed"),
    )
    report = benchmark_capture.run_benchmark(
        load_settings(overrides={"capture": {"backend": "obs"}}),
        duration_s=0.5,
        max_frames=2,
    )
    assert calls == ["start", "idle", "close"]
    assert report["delivery"]["idle_reads"] == 1 and report["delivery"]["failures"] == 0
    assert report["settings"]["reported"]["fps"] == 59


def test_correctness_failure_prevents_timed_benchmark_work(monkeypatch):
    from scripts import benchmark_pipeline

    calls = []

    def fail_gate(*args):
        calls.append("correctness")
        raise ValueError("pixel gate failed")

    monkeypatch.setattr(benchmark_pipeline, "correctness", fail_gate)
    monkeypatch.setattr(
        benchmark_pipeline,
        "legacy_match",
        lambda *args: pytest.fail("timing before correctness"),
    )
    with pytest.raises(ValueError, match="pixel gate failed"):
        benchmark_pipeline.run_benchmark(samples=1, warmups=0, repetitions=1)
    assert calls == ["correctness"]


def test_report_rejects_asset_and_route_outputs():
    from autonavy.config import resource_root
    from scripts.benchmark_common import write_report

    for path in (resource_root() / "src" / "protected", resource_root() / "path.json"):
        with pytest.raises(ValueError, match="overwrite"):
            write_report({"timings": []}, path)


def test_environment_discloses_monotonic_clock_resolution():
    from scripts.benchmark_common import environment

    clocks = environment()["clocks"]
    assert clocks["monotonic"]["resolution_s"] > 0
    assert clocks["perf_counter"]["resolution_s"] > 0


def test_battle_benchmark_runs_real_vision_policy_and_recording_input_without_native(
    monkeypatch,
):
    from scripts.benchmark_pipeline import run_benchmark
    from autonavy.navigation.planner import PlanningService

    monkeypatch.setattr(
        PlanningService,
        "submit",
        lambda *args: pytest.fail("Native planning not part of pixel benchmark"),
    )
    report = run_benchmark(samples=1, warmups=0, repetitions=1)
    battle = report["battle_decision"]
    assert battle["frames_processed"] == 1 and battle["state"] == "in_battle"
    assert battle["recognition_supported"] and battle["valid_injected_telemetry"]
    assert battle["metrics"]["counters"]["input_dispatches"] >= 1
    assert battle["native_planner_measured"] is False
    assert battle["detectors"] != report["decision"]["detectors"]
    assert any(row["stage"] == "decision_battle" for row in report["timings"])
