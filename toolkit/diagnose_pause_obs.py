"""One-shot functional diagnostic for unexpected AutoNavy pause with OBS.

Run from the repository root:
    .\.venv\Scripts\python.exe .\tools\diagnose_pause_obs.py

No project files are modified. AutoNavy is started with --dry-run.
"""
from __future__ import annotations

from autonavy.behavior import BattlePolicy
from autonavy.cli import main as autonavy_main

_original_pause = BattlePolicy.pause
_seen = 0


def _value(obj):
    return getattr(obj, "value", obj)


def _diagnostic_pause(self, *args, **kwargs):
    global _seen
    _seen += 1

    if args:
        reason = args[0]
    else:
        reason = kwargs.get("reason", "Manual pause")

    app = getattr(self, "app", None)
    state = _value(getattr(app, "state", None)) if app is not None else None

    snapshot = None
    telemetry_valid = None
    player = None
    enemies = None
    if app is not None:
        telemetry = getattr(app, "telemetry", None)
        if telemetry is not None:
            try:
                snapshot = telemetry.snapshot()
                telemetry_valid = getattr(snapshot, "valid", None)
                player = getattr(snapshot, "player", None) is not None
                enemies = len(getattr(snapshot, "enemies", ()) or ())
            except Exception as exc:
                print(f"PAUSE_DIAGNOSTIC telemetry_read_error={exc!r}", flush=True)

    observations = getattr(app, "last_observations", None) if app is not None else None
    matches = getattr(observations, "matches", {}) if observations is not None else {}

    matched = []
    scored = []
    try:
        items = matches.items()
    except Exception:
        items = ()

    for name, obs in items:
        available = bool(getattr(obs, "available", False))
        is_match = bool(getattr(obs, "matched", False))
        score = getattr(obs, "score", None)

        if available and is_match:
            matched.append((str(name), score))

        if available and isinstance(score, (int, float)):
            scored.append((float(score), str(name), is_match))

    scored.sort(reverse=True)

    print("\n" + "=" * 88, flush=True)
    print("PAUSE_DIAGNOSTIC", flush=True)
    print(f"event={_seen}", flush=True)
    print(f"reason={reason!r}", flush=True)
    print(f"state_before_pause={state!r}", flush=True)
    print(
        f"telemetry_valid={telemetry_valid!r} "
        f"player={player!r} enemies={enemies!r}",
        flush=True,
    )
    print(f"matched={matched!r}", flush=True)
    print(f"top_scores={scored[:12]!r}", flush=True)
    print("=" * 88 + "\n", flush=True)

    return _original_pause(self, *args, **kwargs)


def main():
    BattlePolicy.pause = _diagnostic_pause
    try:
        return autonavy_main([
            "--dry-run",
            "--capture", "obs",
            "--config", "configs/battle-profile.toml",
            "--max-frames", "40",
        ])
    finally:
        BattlePolicy.pause = _original_pause
        if _seen == 0:
            print("PAUSE_DIAGNOSTIC: no BattlePolicy.pause() call observed", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
