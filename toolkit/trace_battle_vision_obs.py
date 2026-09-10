"""Functional vision-state trace for AutoNavy_WT v2 via OBS.

Put in <repo>/toolkit and run from repository root while already in battle:

    .\.venv\Scripts\python.exe .\toolkit\trace_battle_vision_obs.py |
        Tee-Object .\logs\v2\battle-vision-state.txt

Keep a manually selected enemy in view during the run.
No physical input is enabled; project source files are not modified.
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
_last_print = 0.0
_last_signature = None
_emit_counts = {}
_pause_events = []


def _find_observations(args, kwargs):
    for value in list(args) + list(kwargs.values()):
        if hasattr(value, "matches"):
            return value
    return None


def _find_snapshot(args, kwargs):
    for value in list(args) + list(kwargs.values()):
        if hasattr(value, "enemies") and hasattr(value, "player") and hasattr(value, "valid"):
            return value
    return None


def _obs_row(name, obs):
    available = bool(getattr(obs, "available", False))
    matched = bool(getattr(obs, "matched", False))
    score = getattr(obs, "score", None)
    point = getattr(obs, "point", None)
    offset = getattr(obs, "offset", None)

    score_text = "-"
    if isinstance(score, (int, float)):
        score_text = f"{float(score):.4f}"

    extras = []
    if point is not None:
        extras.append(f"point={point!r}")
    if offset is not None:
        extras.append(f"offset={offset!r}")

    extra_text = (" " + " ".join(extras)) if extras else ""
    return (
        f"{name:<24} available={str(available):<5} "
        f"matched={str(matched):<5} score={score_text:<8}{extra_text}"
    )


def _dump_state(elapsed, observations, snapshot, *, title="VISION_STATE"):
    print("\n" + "=" * 100, flush=True)
    print(f"{title} t={elapsed:.3f}s", flush=True)

    if snapshot is not None:
        print(
            f"telemetry valid={getattr(snapshot, 'valid', None)!r} "
            f"player={getattr(snapshot, 'player', None) is not None} "
            f"enemies={len(getattr(snapshot, 'enemies', ()) or ())}",
            flush=True,
        )

    matches = getattr(observations, "matches", {}) if observations is not None else {}
    try:
        items = list(matches.items())
    except Exception:
        items = []

    if not items:
        print("No observation matches found", flush=True)
    else:
        # Print combat/purchase-related detectors first, then every other
        # available/matched detector so unknown logical names are still visible.
        priority_tokens = (
            "aim", "lock", "fire", "ammo", "degree", "crash", "purchase",
            "buy", "cart", "research", "confirm", "start", "base", "data",
        )

        priority = []
        rest = []
        for name, obs in items:
            lname = str(name).lower()
            row = (str(name), obs)
            if any(token in lname for token in priority_tokens):
                priority.append(row)
            elif bool(getattr(obs, "available", False)) or bool(getattr(obs, "matched", False)):
                rest.append(row)

        seen = set()
        for name, obs in priority + rest:
            if name in seen:
                continue
            seen.add(name)
            print(_obs_row(name, obs), flush=True)

    # Some observation models expose non-template fields outside .matches.
    for attr in ("degree", "heading", "fire", "aim", "lock", "ammo"):
        if observations is not None and hasattr(observations, attr):
            value = getattr(observations, attr)
            if not callable(value):
                print(f"field.{attr}={value!r}", flush=True)

    print("=" * 100 + "\n", flush=True)


def _signature(observations):
    if observations is None:
        return ()
    matches = getattr(observations, "matches", {})
    try:
        items = matches.items()
    except Exception:
        return ()
    result = []
    for name, obs in items:
        score = getattr(obs, "score", None)
        rounded = round(float(score), 3) if isinstance(score, (int, float)) else None
        result.append((
            str(name),
            bool(getattr(obs, "available", False)),
            bool(getattr(obs, "matched", False)),
            rounded,
        ))
    return tuple(result)


def _traced_tick(self, *args, **kwargs):
    global _last_print, _last_signature

    now = time.monotonic()
    elapsed = now - _started
    observations = _find_observations(args, kwargs)
    snapshot = _find_snapshot(args, kwargs)

    sig = _signature(observations)
    # Print once per second, and immediately if any matched/score state changes.
    if (
        observations is not None
        and (now - _last_print >= 1.0 or sig != _last_signature)
    ):
        _last_print = now
        _last_signature = sig
        _dump_state(elapsed, observations, snapshot)

    return _orig_tick(self, *args, **kwargs)


def _traced_emit(self, *args, **kwargs):
    elapsed = time.monotonic() - _started
    owner = str(args[0]) if len(args) > 0 else str(kwargs.get("owner", "?"))
    kind = str(args[1]) if len(args) > 1 else str(kwargs.get("kind", "?"))
    control = str(args[2]) if len(args) > 2 else str(kwargs.get("control", "?"))
    key = (owner, kind, control)
    _emit_counts[key] = _emit_counts.get(key, 0) + 1

    if owner in {"search", "aim", "lock", "fire", "battle", "combat", "target"}:
        print(
            f"INTENT t={elapsed:.3f}s key={key!r} args={args!r} kwargs={kwargs!r}",
            flush=True,
        )

    return _orig_emit(self, *args, **kwargs)


def _traced_pause(self, *args, **kwargs):
    elapsed = time.monotonic() - _started
    reason = args[0] if args else kwargs.get("reason", "Manual pause")
    _pause_events.append((elapsed, reason))
    print(f"\nPAUSE t={elapsed:.3f}s reason={reason!r}", flush=True)

    app = getattr(self, "app", None)
    observations = getattr(app, "last_observations", None) if app is not None else None

    snapshot = None
    if app is not None:
        telemetry = getattr(app, "telemetry", None)
        if telemetry is not None:
            try:
                snapshot = telemetry.snapshot()
            except Exception:
                pass

    if observations is not None:
        _dump_state(elapsed, observations, snapshot, title="VISION_STATE_AT_PAUSE")

    return _orig_pause(self, *args, **kwargs)


def _report():
    print("\n" + "=" * 100)
    print("VISION TRACE SUMMARY")
    print("=" * 100)

    if _emit_counts:
        for key, count in sorted(_emit_counts.items(), key=lambda item: (-item[1], item[0])):
            print(f"{key!r:55} {count:6d}")
    else:
        print("No intents observed")

    if _pause_events:
        print("\nPAUSE EVENTS")
        for elapsed, reason in _pause_events:
            print(f"{elapsed:8.3f}s {reason!r}")
    else:
        print("\nPAUSE EVENTS: none")

    print("=" * 100)


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
        _report()


if __name__ == "__main__":
    raise SystemExit(main())
