"""Trace the full production recovery sequence with a test config.

Usage from repo root:
    .\.venv\Scripts\python.exe .\toolkit\trace_recovery_obs_v2.py configs\recovery-test.toml |
        Tee-Object .\logs\v2\recovery-sequence-v2.txt

The script does not replace BattlePolicy._recover; it exercises the real
production recovery state machine. --dry-run keeps physical input disabled.
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
_orig_recover = BattlePolicy._recover
_orig_state = BattlePolicy._state

_started = time.monotonic()
_last_report = 0.0
_recovery_triggers = 0
_recovery_intents = []
_state_changes = []


def _identity_text(policy):
    try:
        current = policy._identity(
            policy.app.state.value in {"in_battle", "recovering"}
            or getattr(policy, "stage", None) in {"settle", "throttle"}
        )
    except Exception as exc:
        current = f"<error {type(exc).__name__}: {exc}>"
    return f"stored={getattr(policy, 'identity', None)!r} current={current!r}"


def _report(policy, title="RECOVERY_STATE"):
    app = policy.app
    snapshot = getattr(app, "last_snapshot", None)
    now_ns = app._clock_ns()
    next_action = getattr(policy, "next_action", 0)
    wait_s = max(0.0, (next_action - now_ns) / 1e9) if next_action else 0.0
    sequence = list(getattr(policy, "sequence", ()) or ())
    elapsed = time.monotonic() - _started

    print("\n" + "=" * 108, flush=True)
    print(
        f"{title} t={elapsed:.3f}s state={getattr(app, 'state', None)!r} "
        f"stage={getattr(policy, 'stage', None)!r} "
        f"sequence_owner={getattr(policy, 'sequence_owner', None)!r}",
        flush=True,
    )
    print(
        f"telemetry valid={getattr(snapshot, 'valid', None)!r} "
        f"generation={getattr(snapshot, 'generation', None)!r} "
        f"player={getattr(snapshot, 'player', None) is not None if snapshot is not None else False} "
        f"enemies={len(getattr(snapshot, 'enemies', ()) or ()) if snapshot is not None else None}",
        flush=True,
    )
    print("identity:", _identity_text(policy), flush=True)
    print(
        f"sequence_remaining={len(sequence)} "
        f"next_action_in_s={wait_s:.3f}",
        flush=True,
    )
    print("=" * 108 + "\n", flush=True)


def _traced_tick(self, *args, **kwargs):
    global _last_report
    now = time.monotonic()
    if now - _last_report >= 0.5:
        _last_report = now
        _report(self)
    return _orig_tick(self, *args, **kwargs)


def _traced_recover(self, *args, **kwargs):
    global _recovery_triggers
    _recovery_triggers += 1
    elapsed = time.monotonic() - _started
    print(f"\n*** RECOVERY_TRIGGER #{_recovery_triggers} t={elapsed:.3f}s ***", flush=True)
    result = _orig_recover(self, *args, **kwargs)
    _report(self, "AFTER_RECOVERY_TRIGGER")
    return result


def _traced_state(self, state, stage, timeout=None):
    old_state = getattr(self.app, "state", None)
    old_stage = getattr(self, "stage", None)
    result = _orig_state(self, state, stage, timeout)
    elapsed = time.monotonic() - _started

    if old_state != state or old_stage != stage:
        event = (elapsed, old_state, old_stage, state, stage)
        _state_changes.append(event)
        print(
            f"STATE t={elapsed:.3f}s "
            f"{old_state!r}/{old_stage!r} -> {state!r}/{stage!r}",
            flush=True,
        )
    return result


def _traced_emit(self, *args, **kwargs):
    owner = str(args[0]) if len(args) > 0 else str(kwargs.get("owner", "?"))
    action = str(args[1]) if len(args) > 1 else str(kwargs.get("action", "?"))
    resource = str(args[2]) if len(args) > 2 else str(kwargs.get("resource", "?"))
    value = args[3] if len(args) > 3 else kwargs.get("value", 1)
    hold_s = args[4] if len(args) > 4 else kwargs.get("hold_s", 0)

    if owner == "recovery":
        elapsed = time.monotonic() - _started
        event = (elapsed, action, resource, value, hold_s)
        _recovery_intents.append(event)
        print(
            f"RECOVERY_INTENT t={elapsed:.3f}s action={action!r} "
            f"resource={resource!r} value={value!r} hold_s={hold_s!r}",
            flush=True,
        )

    return _orig_emit(self, *args, **kwargs)


def _summary():
    print("\n" + "=" * 108)
    print("RECOVERY TRACE V2 SUMMARY")
    print("=" * 108)
    print(f"recovery_triggers={_recovery_triggers}")
    print(f"recovery_intents={len(_recovery_intents)}")
    for elapsed, action, resource, value, hold_s in _recovery_intents:
        print(
            f"  {elapsed:8.3f}s {action!r} {resource!r} "
            f"value={value!r} hold_s={hold_s!r}"
        )

    print("\nstate_changes:")
    for elapsed, old_state, old_stage, new_state, new_stage in _state_changes:
        print(
            f"  {elapsed:8.3f}s "
            f"{old_state!r}/{old_stage!r} -> {new_state!r}/{new_stage!r}"
        )
    print("=" * 108)


def main():
    config = sys.argv[1] if len(sys.argv) > 1 else r"configs\recovery-test.toml"

    BattlePolicy.tick = _traced_tick
    BattlePolicy.emit = _traced_emit
    BattlePolicy._recover = _traced_recover
    BattlePolicy._state = _traced_state

    try:
        return autonavy_main([
            "--dry-run",
            "--capture", "obs",
            "--config", config,
            "--max-frames", "300",
        ])
    finally:
        BattlePolicy.tick = _orig_tick
        BattlePolicy.emit = _orig_emit
        BattlePolicy._recover = _orig_recover
        BattlePolicy._state = _orig_state
        _summary()


if __name__ == "__main__":
    raise SystemExit(main())
