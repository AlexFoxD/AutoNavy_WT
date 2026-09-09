"""Bounded diagnostic primitives; no timing performance assertions."""

from dataclasses import replace
import logging
import math
import pytest
from autonavy.config import Settings, load_settings, ConfigurationError


def test_metrics_retention_cardinality_finite_samples_and_detached_snapshot():
    from autonavy.metrics import Metrics

    m = Metrics(max_samples=2, max_series=2)
    for value in (1, 2, 3):
        m.observe("vision_ns", value)
    m.increment("delivered", 3)
    report = m.snapshot()
    assert report["samples"]["vision_ns"] == dict(
        count=3, retained=2, p50=2.5, p95=2.95, mean=2.5
    )
    assert report["counters"]["delivered"] == 3
    report["counters"]["delivered"] = 99
    assert m.snapshot()["counters"]["delivered"] == 3
    with pytest.raises(ValueError):
        m.observe("extra", 1)
    for value in (math.nan, math.inf, -1):
        with pytest.raises(ValueError):
            m.observe("vision_ns", value)
    for value in (0, -1, True):
        with pytest.raises(ValueError):
            Metrics(max_samples=value)


def test_throttle_is_bounded_and_uses_monotonic_intervals():
    from autonavy.diagnostics import FaultThrottle

    now = [0.0]
    throttle = FaultThrottle(5, clock=lambda: now[0], max_keys=2)
    assert throttle.allow("planner")
    assert not throttle.allow("planner")
    now[0] = 5
    assert throttle.allow("planner")
    for name in ("capture", "preview", "other"):
        throttle.allow(name)
    assert throttle.key_count == 2


def test_runtime_logging_rotates_and_closes_owned_handlers_with_traceback(tmp_path):
    from autonavy.diagnostics import runtime_logging

    s = Settings()
    s = replace(
        s,
        paths=replace(s.paths, logs=tmp_path),
        diagnostics=replace(s.diagnostics, log_max_bytes=400, log_backups=2),
    )
    root = logging.getLogger("autonavy")
    before = tuple(root.handlers)
    with runtime_logging(s):
        logger = logging.getLogger("autonavy.test")
        for _ in range(20):
            logger.info("bounded event context=%s", "x" * 80)
        try:
            raise RuntimeError("diagnostic sentinel")
        except RuntimeError:
            logger.exception("operation failed")
    assert tuple(root.handlers) == before
    files = list(tmp_path.glob("autonavy.log*"))
    assert 1 <= len(files) <= 3
    content = "".join(p.read_text(encoding="utf-8") for p in files)
    assert (
        "Traceback" in content
        and "diagnostic sentinel" in content
        and "autonavy.test" in content
    )


@pytest.mark.parametrize("value", [0, -1, 100001])
def test_metrics_bound_is_validated(value):
    with pytest.raises(ConfigurationError):
        load_settings(overrides={"diagnostics": {"metrics_samples": value}})


def test_default_metrics_bound_and_truncated_traceback():
    from autonavy.diagnostics import exception_text

    assert load_settings().diagnostics.metrics_samples == 512
    assert (
        load_settings(
            overrides={"diagnostics": {"metrics_samples": 2}}
        ).diagnostics.metrics_samples
        == 2
    )
    try:
        raise RuntimeError("x" * 6000 + "final sentinel")
    except RuntimeError as exc:
        encoded = exception_text(exc)
    assert len(encoded) == 4096 and encoded.startswith(b"[traceback truncated]")
    assert b"final sentinel" in encoded


def test_native_planner_preserves_bounded_traceback(monkeypatch):
    import multiprocessing
    from autonavy.navigation import native
    from autonavy.navigation.planner import _native_worker, PlanRequest

    def broken(*args):
        raise RuntimeError("planner traceback sentinel")

    monkeypatch.setattr(native, "plan_encoded", broken)
    ctx = multiprocessing.get_context("spawn")
    count, error = ctx.RawValue("i", 0), ctx.RawArray("c", 4096)
    _native_worker(PlanRequest(("test",), b"", (0, 0), (1, 1)), [], count, error)
    assert count.value == -2
    assert b"Traceback" in error.value and b"planner traceback sentinel" in error.value


def test_long_exception_preserves_type_tail_and_device_context():
    from autonavy.diagnostics import exception_text

    try:
        raise RuntimeError("x" * 6000 + " final reason")
    except RuntimeError as exc:
        data = exception_text(exc, 511, context="backend=obs device=2")
    assert len(data) <= 511
    assert b"RuntimeError:" in data and b"final reason" in data
    assert b"backend=obs device=2" in data and b"truncated" in data


def test_telemetry_fault_has_bounded_traceback_and_keeps_existing_throttle(caplog):
    from autonavy.telemetry import TelemetryService

    service = TelemetryService(Settings().telemetry)
    with caplog.at_level(logging.WARNING):
        for _ in range(2):
            try:
                raise ValueError("telemetry diagnostic sentinel")
            except ValueError as exc:
                service._fault("metadata", exc)
    messages = [
        r.message
        for r in caplog.records
        if "telemetry diagnostic sentinel" in r.message
    ]
    assert len(messages) == 1
    assert "Traceback" in messages[0] and "metadata" in messages[0]
