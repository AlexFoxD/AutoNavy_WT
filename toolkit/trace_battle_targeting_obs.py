"""Dry-run targeting trace for AutoNavy_WT v2 through OBS.

Put in <repo>/toolkit and run from repo root while already in active battle:

    .\.venv\Scripts\python.exe .\toolkit\trace_battle_targeting_obs.py |
        Tee-Object .\logs\v2\targeting-trace.txt

No physical input is enabled and project files are not modified.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import math
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonavy.behavior import BattlePolicy
from autonavy.cli import main as autonavy_main


_orig_tick = BattlePolicy.tick
_orig_emit = BattlePolicy.emit
_orig_pause = BattlePolicy.pause

_started = time.monotonic()
_last_enemy_count = object()
_last_snapshot_print = 0.0
_counts = Counter()
_events = []
_pause_events = []


def _find_snapshot(args, kwargs, self):
    candidates = list(args) + list(kwargs.values())

    app = getattr(self, "app", None)
    if app is not None:
        telemetry = getattr(app, "telemetry", None)
        if telemetry is not None:
            try:
                candidates.append(telemetry.snapshot())
            except Exception:
                pass

    for value in candidates:
        if hasattr(value, "enemies") and hasattr(value, "player") and hasattr(value, "valid"):
            return value
    return None


def _traced_tick(self, *args, **kwargs):
    global _last_enemy_count, _last_snapshot_print

    now = time.monotonic()
    elapsed = now - _started
    snapshot = _find_snapshot(args, kwargs, self)

    if snapshot is not None:
        enemies = tuple(getattr(snapshot, "enemies", ()) or ())
        enemy_count = len(enemies)
        player = getattr(snapshot, "player", None)
        valid = bool(getattr(snapshot, "valid", False))

        changed = enemy_count != _last_enemy_count
        periodic = now - _last_snapshot_print >= 1.0
        if changed or periodic:
            _last_enemy_count = enemy_count
            _last_snapshot_print = now

            nearest = None
            if player is not None and enemies:
                px, py = player.position
                nearest_obj = min(
                    enemies,
                    key=lambda e: (e.position[0] - px) ** 2 + (e.position[1] - py) ** 2,
                )
                ex, ey = nearest_obj.position
                nearest = {
                    "position": nearest_obj.position,
                    "distance_norm": math.hypot(ex - px, ey - py),
                }

            print(
                f"SNAPSHOT t={elapsed:7.3f}s valid={valid} "
                f"player={player is not None} enemies={enemy_count} "
                f"nearest={nearest!r}",
                flush=True,
            )

    return _orig_tick(self, *args, **kwargs)


def _traced_emit(self, *args, **kwargs):
    elapsed = time.monotonic() - _started

    owner = str(args[0]) if len(args) > 0 else str(kwargs.get("owner", "?"))
    kind = str(args[1]) if len(args) > 1 else str(kwargs.get("kind", "?"))
    control = str(args[2]) if len(args) > 2 else str(kwargs.get("control", "?"))
    key = (owner, kind, control)
    _counts[key] += 1

    # Keep all combat/search events, and only sample navigation.
    interesting = owner in {"search", "battle", "aim", "lock", "fire", "combat", "target"}
    if interesting or (_counts[key] <= 2 and owner != "navigation"):
        event = (elapsed, key, args, kwargs)
        _events.append(event)
        print(
            f"INTENT   t={elapsed:7.3f}s key={key!r} "
            f"args={args!r} kwargs={kwargs!r}",
            flush=True,
        )

    return _orig_emit(self, *args, **kwargs)


def _traced_pause(self, *args, **kwargs):
    elapsed = time.monotonic() - _started
    reason = args[0] if args else kwargs.get("reason", "Manual pause")
    _pause_events.append((elapsed, reason))
    print(f"PAUSE    t={elapsed:7.3f}s reason={reason!r}", flush=True)
    return _orig_pause(self, *args, **kwargs)


def _report():
    print("\n" + "=" * 92)
    print("TARGETING TRACE SUMMARY")
    print("=" * 92)
    for key, count in _counts.most_common():
        print(f"{key!r:54} {count:6d}")
    if _pause_events:
        print("\nPAUSE EVENTS")
        for elapsed, reason in _pause_events:
            print(f"{elapsed:7.3f}s {reason!r}")
    else:
        print("\nPAUSE EVENTS: none")
    print("=" * 92)


def main():
    BattlePolicy.tick = _traced_tick
    BattlePolicy.emit = _traced_emit
    BattlePolicy.pause = _traced_pause

    try:
        return autonavy_main([
            "--dry-run",
            "--capture", "obs",
            "--config", "configs/battle-profile.toml",
            "--max-frames", "180",
        ])
    finally:
        BattlePolicy.tick = _orig_tick
        BattlePolicy.emit = _orig_emit
        BattlePolicy.pause = _orig_pause
        _report()


if __name__ == "__main__":
    raise SystemExit(main())
