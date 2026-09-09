"""Non-actuating capture-only benchmark. Defaults to finite synthetic replay.

Live dxcam/obs selection is explicit; neither input nor telemetry is constructed.
Receive age excludes unknown source/render/camera buffering. Replay is unpaced
and cannot rank real backends. CPU/memory sampling covers the benchmark parent.
"""

import argparse
from dataclasses import asdict, replace
import math
import hashlib
from pathlib import Path
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autonavy.capture.base import CaptureTimeout
from autonavy.capture.factory import create_capture
from autonavy.config import load_settings, validate_settings, resource_root
from autonavy.diagnostics import exception_text
from scripts.benchmark_common import environment, timing_row, write_report


def parent_memory():
    """Read this process only, with platform-specific memory semantics disclosed."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    *[
                        (name, ctypes.c_size_t)
                        for name in (
                            "PeakWorkingSetSize",
                            "WorkingSetSize",
                            "QuotaPeakPagedPoolUsage",
                            "QuotaPagedPoolUsage",
                            "QuotaPeakNonPagedPoolUsage",
                            "QuotaNonPagedPoolUsage",
                            "PagefileUsage",
                            "PeakPagefileUsage",
                        )
                    ],
                ]

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = (
                wintypes.HANDLE,
                ctypes.POINTER(Counters),
                wintypes.DWORD,
            )
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(
                kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            return dict(bytes=counters.WorkingSetSize, kind="current_working_set")
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return dict(
            bytes=value if sys.platform == "darwin" else value * 1024,
            kind="peak_resident_set",
        )
    except (ImportError, OSError, AttributeError) as exc:
        return dict(bytes=None, kind="unavailable", reason=str(exc))


def run_benchmark(settings, *, duration_s=5.0, max_frames=100000):
    if not math.isfinite(duration_s) or not 0 < duration_s <= 86400:
        raise ValueError("duration_s must be finite and between zero and 86400 seconds")
    if type(max_frames) is not int or not 1 <= max_frames <= 1000000:
        raise ValueError("max_frames must be an integer between 1 and 1000000")
    settings = validate_settings(
        replace(
            settings,
            input=replace(settings.input, enable_input=False),
            diagnostics=replace(settings.diagnostics, preview=False, per_frame=False),
        )
    )
    capture = create_capture(settings)
    ages, reads = [], []
    delivered = idle = failures = gaps = 0
    previous = 0
    delivered_settings = None
    error = None
    start = time.perf_counter_ns()
    startup_ns = collection_ns = cleanup_ns = 0
    cpu_s = 0.0
    started_collection = None
    cpu_start = None
    source_diagnostic = None
    try:
        capture.start()
        startup_ns = time.perf_counter_ns() - start
        started_collection = time.perf_counter_ns()
        cpu_start = time.process_time()
        deadline = time.monotonic() + duration_s
        while delivered < max_frames:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            read_start = time.perf_counter_ns()
            try:
                packet = capture.read(timeout=min(0.05, remaining))
            except CaptureTimeout:
                idle += 1
                continue
            read_ns = time.perf_counter_ns() - read_start
            if packet is None:
                break
            consumed = time.monotonic_ns()
            reads.append(read_ns)
            ages.append(max(0, consumed - packet.received_at_ns))
            delivered += 1
            gaps += max(0, packet.publication_id - previous - 1)
            previous = packet.publication_id
            delivered_settings = dict(
                width=packet.image.shape[1],
                height=packet.image.shape[0],
                pixel_format=packet.pixel_format,
            )
            source_diagnostic = getattr(capture, "diagnostic", None)
    except Exception as exc:
        failures += 1
        error = exception_text(exc).decode("utf-8", errors="replace")
    finally:
        if started_collection is not None:
            collection_ns = time.perf_counter_ns() - started_collection
            cpu_s = time.process_time() - cpu_start
        else:
            startup_ns = time.perf_counter_ns() - start
        cleanup_start = time.perf_counter_ns()
        try:
            capture.close()
        except Exception as exc:
            failures += 1
            error = (error or "") + exception_text(exc).decode(
                "utf-8", errors="replace"
            )
        cleanup_ns = time.perf_counter_ns() - cleanup_start
    if source_diagnostic is None:
        source_diagnostic = getattr(capture, "diagnostic", None)
    diagnostic = source_diagnostic or {}
    backend_statistics = getattr(capture, "statistics", None)
    seconds = collection_ns / 1e9
    return dict(
        schema_version=1,
        kind="capture",
        environment=environment(),
        mode="synthetic_replay_capture_only"
        if settings.capture.backend == "replay"
        else "live_capture_only",
        backend=settings.capture.backend,
        status="failed" if failures else "ok",
        error=error,
        provenance=dict(
            fixture=str(settings.capture.fixture) if settings.capture.fixture else None,
            fixture_sha256=hashlib.sha256(
                (settings.capture.fixture / "manifest.json").read_bytes()
            ).hexdigest()
            if settings.capture.fixture
            else None,
            pacing="unpaced finite replay"
            if settings.capture.backend == "replay"
            else "configured native capture cadence",
        ),
        settings=dict(
            requested={
                key: str(value) if isinstance(value, Path) else value
                for key, value in asdict(settings.capture).items()
            },
            reported=diagnostic.get("reported"),
            delivered=delivered_settings,
        ),
        source_diagnostic=source_diagnostic,
        duration_budget_s=duration_s,
        frame_budget=max_frames,
        lifecycle_ns=dict(
            startup=startup_ns, collection=collection_ns, cleanup=cleanup_ns
        ),
        delivery=dict(
            frames=delivered,
            publication_rate_hz=delivered / seconds if seconds else None,
            publication_gaps=gaps,
            idle_reads=idle,
            failures=failures,
            gap_definition="observed skipped publication IDs, not confirmed source/render drops",
        ),
        backend_statistics=backend_statistics,
        source_render_latency_ns=None,
        source_presentation_rate_hz=None,
        intent_to_dispatch_ns=None,
        unavailable=dict(
            source_latency="no synchronized source/render timestamp; receive age is a lower bound",
            presentation_rate="publication IDs do not establish unique rendered frames",
            input_latency="capture-only run; no decisions or input owner",
            gpu_game="not measured",
            children="isolated capture/planner CPU and memory not sampled",
        ),
        resources=dict(
            scope="benchmark_parent_only",
            cpu_time_s=cpu_s,
            cpu_percent_of_one_core=100 * cpu_s / seconds if seconds else None,
            memory=parent_memory(),
            isolated_children=None,
        ),
        timings=[
            timing_row(
                "receive_age",
                "selected_backend",
                ages,
                scope="monotonic successful receive to benchmark consume; excludes unknown upstream buffering",
            ),
            timing_row(
                "capture_read",
                "selected_backend",
                reads,
                scope="successful capture.read call including publication wait/ownership copy; idle waits excluded",
            ),
        ],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", choices=("replay", "dxcam", "obs"), default="replay"
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--max-frames", type=int, default=100000)
    parser.add_argument(
        "--output", type=Path, default=Path("logs/v2/benchmarks/capture")
    )
    args = parser.parse_args(argv)
    capture = dict(backend=args.backend)
    if args.backend == "replay":
        capture["fixture"] = args.fixture or resource_root() / "tests/fixtures/smoke"
    elif args.fixture is not None:
        parser.error("--fixture requires --backend replay")
    settings = load_settings(
        args.config,
        overrides={
            "capture": capture,
            "input": {"enable_input": False},
            "diagnostics": {"preview": False, "per_frame": False},
        },
    )
    report = run_benchmark(
        settings, duration_s=args.duration, max_frames=args.max_frames
    )
    for path in write_report(report, args.output):
        print(path)
    print(report["delivery"])
    return 0 if report["status"] == "ok" else 3


if __name__ == "__main__":
    raise SystemExit(main())
