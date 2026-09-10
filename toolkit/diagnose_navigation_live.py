"""Read-only live navigation diagnostic for AutoNavy_WT v2.

Run from the repository root while inside an active battle:

    .\.venv\Scripts\python.exe .\tools\diagnose_navigation_live.py

It reads War Thunder localhost telemetry and tactical map only. No input is sent.
"""
from __future__ import annotations

from pathlib import Path
import math

import cv2
import numpy as np
import requests

from autonavy.navigation.native import NativePathfinder, prepare_map
from autonavy.telemetry import _metadata, _objects


BASE = "http://127.0.0.1:8111"
OUT_DIR = Path("logs/v2")


def grid_point(position, image_shape, grid_shape):
    h, w = image_shape[:2]
    gh, gw = grid_shape[:2]
    x = min(w - 1, int(position[0] * w))
    y = min(h - 1, int(position[1] * h))
    return min(gw - 1, int(x * gw / w)), min(gh - 1, int(y * gh / h))


def main() -> int:
    session = requests.Session()
    session.trust_env = False
    try:
        info = session.get(f"{BASE}/map_info.json", timeout=(0.5, 0.5)).json()
        objects = session.get(f"{BASE}/map_obj.json", timeout=(0.5, 0.5)).json()
        response = session.get(
            f"{BASE}/map.img?gen=2",
            timeout=(0.5, 1.0),
            allow_redirects=False,
        )
        response.raise_for_status()
        image_bytes = response.content
    finally:
        session.close()

    metadata = _metadata(info, 1)
    player, enemies, zones = _objects(objects)
    if player is None:
        raise RuntimeError("Player is unavailable")
    if not zones:
        raise RuntimeError("No candidate capture zones")

    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("Failed to decode map.img")

    grid = prepare_map(image)
    blocked = np.all(grid == 0, axis=2)
    origin = grid_point(player.position, image.shape, grid.shape)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT_DIR / "navigation-map-live.png"), image)
    cv2.imwrite(str(OUT_DIR / "navigation-grid-live.png"), grid)

    print("NAVIGATION LIVE DIAGNOSTIC")
    print(f"metadata_key={metadata.key}")
    print(f"image_shape={image.shape} grid_shape={grid.shape}")
    print(
        f"blocked_cells={int(blocked.sum())}/{blocked.size} "
        f"({100.0 * blocked.mean():.2f}%)"
    )
    print(
        f"player={player.position} origin_grid={origin} "
        f"origin_blocked={bool(blocked[origin[1], origin[0]])}"
    )
    print(f"enemies={len(enemies)} candidate_zones={len(zones)}")

    pathfinder = NativePathfinder()
    any_route = False

    for index, zone in enumerate(zones, 1):
        goal = grid_point(zone, image.shape, grid.shape)
        goal_blocked = bool(blocked[goal[1], goal[0]])

        if blocked[origin[1], origin[0]] or goal_blocked:
            route = None
            reason = (
                "origin blocked" if blocked[origin[1], origin[0]]
                else "goal blocked"
            )
        else:
            route = pathfinder.find(grid, origin, goal)
            reason = "reachable" if route is not None else "disconnected"

        if route is not None:
            any_route = True

        distance = math.dist(player.position, zone)
        print(
            f"zone[{index}]={zone} distance={distance:.6f} "
            f"goal_grid={goal} goal_blocked={goal_blocked} "
            f"route_points={None if route is None else len(route)} "
            f"status={reason}"
        )

    print(f"ANY_REACHABLE_ZONE={any_route}")
    print(f"saved={OUT_DIR / 'navigation-map-live.png'}")
    print(f"saved={OUT_DIR / 'navigation-grid-live.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
