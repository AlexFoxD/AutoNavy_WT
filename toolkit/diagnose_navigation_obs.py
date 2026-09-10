"""Read-only live navigation/map diagnostic for AutoNavy_WT v2.

Put this file in <repo>/toolkit and run while already in an active battle:

    .\.venv\Scripts\python.exe .\toolkit\diagnose_navigation_obs.py

No input is sent and no project source file is modified.
"""
from __future__ import annotations

from pathlib import Path
import sys
import inspect
import math

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import requests

from autonavy.navigation.native import prepare_map
from autonavy.telemetry import _metadata, _objects


BASE = "http://127.0.0.1:8111"
OUT = ROOT / "logs" / "v2"
OUT.mkdir(parents=True, exist_ok=True)


def _point(pos, shape):
    h, w = shape[:2]
    x = min(w - 1, max(0, int(float(pos[0]) * w)))
    y = min(h - 1, max(0, int(float(pos[1]) * h)))
    return x, y


def _intensity(data):
    a = np.asarray(data)
    if a.ndim == 2:
        return a
    if a.ndim == 3:
        return np.max(a, axis=2)
    raise RuntimeError(f"Unexpected prepared map shape: {a.shape!r}")


def _component_report(mask, player_pos, zones, label):
    mask8 = np.asarray(mask, dtype=np.uint8)
    count, labels = cv2.connectedComponents(mask8, connectivity=8)
    pp = _point(player_pos, mask8.shape)
    player_open = bool(mask8[pp[1], pp[0]])
    player_component = int(labels[pp[1], pp[0]]) if player_open else 0

    print(f"\n[{label}]")
    print(
        f"passable={int(mask8.sum())}/{mask8.size} "
        f"({100.0 * float(mask8.mean()):.2f}%) "
        f"components={max(0, count - 1)}"
    )
    print(
        f"player_grid={pp} passable={player_open} "
        f"component={player_component}"
    )

    reachable = 0
    for i, zone in enumerate(zones, 1):
        zp = _point(zone, mask8.shape)
        zone_open = bool(mask8[zp[1], zp[0]])
        zone_component = int(labels[zp[1], zp[0]]) if zone_open else 0
        same = (
            player_open
            and zone_open
            and player_component != 0
            and player_component == zone_component
        )
        reachable += int(same)
        print(
            f"zone[{i}]={zone} grid={zp} passable={zone_open} "
            f"component={zone_component} same_component={same} "
            f"distance_norm={math.dist(player_pos, zone):.6f}"
        )
    print(f"same_component_zones={reachable}/{len(zones)}")


def main():
    session = requests.Session()
    session.trust_env = False
    try:
        info_r = session.get(f"{BASE}/map_info.json", timeout=(0.5, 0.5))
        info_r.raise_for_status()
        info = info_r.json()

        obj_r = session.get(f"{BASE}/map_obj.json", timeout=(0.5, 0.5))
        obj_r.raise_for_status()
        objects = obj_r.json()

        image_r = session.get(
            f"{BASE}/map.img?gen=2",
            timeout=(0.5, 1.5),
            allow_redirects=False,
        )
        image_r.raise_for_status()
        image_bytes = image_r.content
    finally:
        session.close()

    metadata = _metadata(info, 1)
    player, enemies, zones = _objects(objects)

    print("=" * 86)
    print("AUTONAVY NAVIGATION DIAGNOSTIC")
    print("=" * 86)
    print(f"map_key={metadata.key}")
    print(f"player={player}")
    print(f"enemies={len(enemies)} zones={zones}")

    if player is None:
        raise RuntimeError("Player unavailable; run this inside an active battle")
    if not zones:
        raise RuntimeError("No capture zones returned by map_obj.json")

    image = cv2.imdecode(
        np.frombuffer(image_bytes, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    if image is None:
        raise RuntimeError("OpenCV could not decode /map.img?gen=2")

    print(f"map_image_shape={image.shape} dtype={image.dtype}")
    print(f"prepare_map_signature={inspect.signature(prepare_map)}")

    cv2.imwrite(str(OUT / "navigation-map-raw.png"), image)

    # Current v2 normally prepares a decoded OpenCV tactical map. Keep a bytes
    # fallback so the diagnostic stays useful if this helper's contract changes.
    try:
        prepared = prepare_map(image)
        prepare_input = "decoded BGR image"
    except Exception as first:
        try:
            prepared = prepare_map(image_bytes)
            prepare_input = "encoded image bytes"
        except Exception as second:
            print(f"prepare_map(image) failed: {first!r}")
            print(f"prepare_map(bytes) failed: {second!r}")
            raise

    prepared = np.asarray(prepared)
    print(
        f"prepare_input={prepare_input} "
        f"prepared_shape={prepared.shape} dtype={prepared.dtype} "
        f"min={prepared.min()} max={prepared.max()}"
    )

    # Preserve exactly what prepare_map returned where possible.
    if prepared.dtype == np.bool_:
        saved = prepared.astype(np.uint8) * 255
    else:
        saved = prepared
    cv2.imwrite(str(OUT / "navigation-map-prepared.png"), saved)

    intensity = _intensity(prepared)
    nonzero = intensity != 0
    zero = ~nonzero

    values, counts = np.unique(intensity, return_counts=True)
    order = np.argsort(counts)[::-1][:12]
    top = [(int(values[i]), int(counts[i])) for i in order]
    print(f"prepared_top_values={top}")

    pp = _point(player.position, intensity.shape)
    print(
        f"player_prepared_pixel={pp} "
        f"value={int(intensity[pp[1], pp[0]])}"
    )
    for i, zone in enumerate(zones, 1):
        zp = _point(zone, intensity.shape)
        print(
            f"zone[{i}]_prepared_pixel={zp} "
            f"value={int(intensity[zp[1], zp[0]])}"
        )

    # We report both polarities deliberately. If all live points only connect
    # under one polarity, that immediately reveals whether the planner's
    # passable/blocked interpretation or map preprocessing is the problem.
    _component_report(nonzero, player.position, zones, "NONZERO AS PASSABLE")
    _component_report(zero, player.position, zones, "ZERO AS PASSABLE")

    # Annotated prepared image for visual inspection.
    if prepared.ndim == 2:
        annotated = cv2.cvtColor(saved.astype(np.uint8), cv2.COLOR_GRAY2BGR)
    elif prepared.ndim == 3:
        annotated = saved.copy().astype(np.uint8)
    else:
        annotated = np.zeros((*intensity.shape, 3), dtype=np.uint8)

    px, py = _point(player.position, annotated.shape)
    cv2.circle(annotated, (px, py), 4, (255, 255, 255), -1)
    cv2.putText(
        annotated, "PLAYER", (px + 6, py),
        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1,
        cv2.LINE_AA,
    )
    for i, zone in enumerate(zones, 1):
        zx, zy = _point(zone, annotated.shape)
        cv2.circle(annotated, (zx, zy), 4, (127, 127, 127), -1)
        cv2.putText(
            annotated, f"Z{i}", (zx + 6, zy),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1,
            cv2.LINE_AA,
        )

    cv2.imwrite(str(OUT / "navigation-map-annotated.png"), annotated)

    print("\nSaved:")
    print(OUT / "navigation-map-raw.png")
    print(OUT / "navigation-map-prepared.png")
    print(OUT / "navigation-map-annotated.png")
    print("=" * 86)


if __name__ == "__main__":
    main()
