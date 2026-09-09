"""Shared finite benchmark summaries and explicit local artifact output."""

import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import subprocess
import sys

from autonavy.config import resource_root
from autonavy.metrics import summarize


def environment():
    import cv2

    root = resource_root()

    def git(*args):
        try:
            return subprocess.check_output(
                ["git", "-C", str(root), *args],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            return None

    dependencies = {}
    for package in ("numpy", "opencv-python", "Pillow", "dxcam"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = None
    files = [*root.glob("scripts/benchmark_*.py"), *root.glob("autonavy/**/*.py")]
    return dict(
        utc=datetime.now(timezone.utc).isoformat(),
        python=sys.version,
        platform=platform.platform(),
        machine=platform.machine(),
        processor=platform.processor(),
        dependencies=dependencies,
        opencv_threads=cv2.getNumThreads(),
        git_commit=git("rev-parse", "HEAD"),
        git_dirty=git("status", "--porcelain"),
        code_sha256={
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
    )


def timing_row(stage, variant, values, *, warmups=0, repetition=1, scope=""):
    stats = summarize(values)
    total = sum(values)
    return dict(
        stage=stage,
        variant=variant,
        repetition=repetition,
        n=len(values),
        warmups=warmups,
        p50_ns=stats["p50"],
        p95_ns=stats["p95"],
        mean_ns=stats["mean"],
        throughput_per_s=len(values) * 1e9 / total if total else None,
        scope=scope,
        samples_ns=list(values),
    )


def write_report(report, output):
    """Write JSON detail plus a timing CSV, refusing protected source/resources."""
    root = resource_root()
    base = Path(output).resolve()
    if base.suffix in {".json", ".csv"}:
        base = base.with_suffix("")
    paths = (base.with_suffix(".json"), base.with_suffix(".csv"))
    for path in paths:
        if path == root / "path.json" or path.is_relative_to(root / "src"):
            raise ValueError(
                "Benchmark output must not overwrite source assets or path.json"
            )
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    columns = (
        "stage",
        "variant",
        "repetition",
        "n",
        "warmups",
        "p50_ns",
        "p95_ns",
        "mean_ns",
        "throughput_per_s",
        "scope",
    )
    with paths[1].open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["timings"])
    return paths
