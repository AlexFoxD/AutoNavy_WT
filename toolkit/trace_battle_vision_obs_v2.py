"""Live functional vision-state trace for AutoNavy_WT v2 via OBS.

Put in <repo>/toolkit and run from repository root while already in battle:

    .\.venv\Scripts\python.exe .\toolkit\trace_battle_vision_obs_v2.py |
        Tee-Object .\logs\v2\battle-vision-v2.txt

Keep a manually selected enemy in view during the run.
No physical input is enabled. Project source files are not modified.
"""
from __future__ import annotations

from pathlib import Path
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
_last_report = 0.0
_last_enemy_count = None
_counts = {}
_pause_events = []


WATCH = (
    "aim",
    "lock",
    "fire",
    "ammo",
    "purchase_confirm",
    "_purchase",
    "buy",
    "autobuyparts",
    "crash_warning",
    "crashed",
)


def _fmt_obs(name, observation):
    if observation is None:
        return f"{name:<18} missing"

    available = bool(getattr(observation, "available", False))
    matched = bool(getattr(observation, "matched", False))
    score = getattr(observation, "score", None)
    center = getattr(observation, "frame_center", None)
    reason = getattr(observation, "reason", None)

    score_text = "-" if score is None else f"{float(score):.4f}"
    return (
        f"{name:<18} available={str(available):<5} "
        f"matched={str(matched):<5} "
        f"score={score_text:<8} "
        f"center={center!r} "
        f"reason={reason!r}"
    )


def _report_state(self, *, title="VISION_STATE"):
    app = self.app
    observations = getattr(app, "last_observations", None)
    snapshot = getattr(app, "last_snapshot", None)
    elapsed = time.monotonic() - _started

    print("\n" + "=" * 108, flush=True)
    print(f"{title} t={elapsed:.3f}s state={getattr(app, 'state', None)!r}", flush=True)

    if snapshot is None:
        print("snapshot=None", flush=True)
    else:
        enemies = tuple(getattr(snapshot, "enemies", ()) or ())
        print(
            f"telemetry valid={getattr(snapshot, 'valid', None)!r} "
            f"player={getattr(snapshot, 'player', None) is not None} "
            f"enemies={len(enemies)}",
            flush=True,
        )

    if observations is None:
        print("observations=None", flush=True)
    else:
        matches = getattr(observations, "matches", {})
        for name in WATCH:
            print(_fmt_obs(name, matches.get(name)), flush=True)

        degree = getattr(observations, "degree", None)
        print(f"degree={degree!r}", flush=True)

    print("=" * 108 + "\n", flush=True)


def _traced_tick(self, *args, **kwargs):
    global _last_report, _last_enemy_count

    now = time.monotonic()
    app = self.app
    snapshot = getattr(app, "last_snapshot", None)
    enemies = len(getattr(snapshot, "enemies", ()) or ()) if snapshot is not None else None

    should_report = (
        now - _last_report >= 0.75
        or enemies != _last_enemy_count
    )

    if should_report:
        _last_report = now
        _last_enemy_count = enemies
        _report_state(self)

    return _orig_tick(self, *args, **kwargs)


def _traced_emit(self, *args, **kwargs):
    owner = str(args[0]) if len(args) > 0 else str(kwargs.get("owner", "?"))
    kind = str(args[1]) if len(args) > 1 else str(kwargs.get("kind", "?"))
    control = str(args[2]) if len(args) > 2 else str(kwargs.get("control", "?"))

    key = (owner, kind, control)
    _counts[key] = _counts.get(key, 0) + 1

    if owner in {"search", "aim", "lock", "fire", "battle", "combat", "target"}:
        elapsed = time.monotonic() - _started
        print(
            f"INTENT t={elapsed:.3f}s key={key!r} "
            f"args={args!r} kwargs={kwargs!r}",
            flush=True,
        )

    return _orig_emit(self, *args, **kwargs)


def _traced_pause(self, *args, **kwargs):
    elapsed = time.monotonic() - _started
    reason = args[0] if args else kwargs.get("reason", "Manual pause")
    _pause_events.append((elapsed, reason))

    print(f"\nPAUSE t={elapsed:.3f}s reason={reason!r}", flush=True)
    _report_state(self, title="VISION_STATE_AT_PAUSE")

    return _orig_pause(self, *args, **kwargs)


def _summary():
    print("\n" + "=" * 108)
    print("VISION TRACE V2 SUMMARY")
    print("=" * 108)

    for key, count in sorted(_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{key!r:58} {count:6d}")

    if _pause_events:
        print("\nPAUSE EVENTS")
        for elapsed, reason in _pause_events:
            print(f"{elapsed:8.3f}s {reason!r}")
    else:
        print("\nPAUSE EVENTS: none")

    print("=" * 108)


def main():
    BattlePolicy.tick = _traced_tick
    BattlePolicy.emit = _traced_emit
    BattlePolicy.pause = _traced_pause

    try:
        return autonavy_main([
            "--dry-run",
            "--capture", "obs",
            "--config", "configs/battle-profile.toml",
            "--max-frames", "120",
        ])
    finally:
        BattlePolicy.tick = _orig_tick
        BattlePolicy.emit = _orig_emit
        BattlePolicy.pause = _orig_pause
        _summary()


if __name__ == "__main__":
    raise SystemExit(main())
