"""Functional dry-run trace of BattlePolicy intents through OBS.

Put in <repo>/toolkit and run from repository root while already in battle:

    .\.venv\Scripts\python.exe .\toolkit\trace_battle_intents_obs.py

No physical input is enabled. Project source files are not modified.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import math
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonavy.behavior import BattlePolicy
from autonavy.cli import main as autonavy_main


_original_emit = BattlePolicy.emit
_original_pause = BattlePolicy.pause

_started = time.monotonic()
_events = []
_counts = Counter()
_values = defaultdict(list)
_last_print = {}
_pause_events = []


def _safe(value):
    try:
        text = repr(value)
    except Exception:
        text = f"<{type(value).__name__}>"
    return text if len(text) <= 180 else text[:177] + "..."


def _key(args, kwargs):
    # Existing v2 emit calls use the first three positional arguments as
    # owner/action/control. Fall back gracefully if a future call differs.
    parts = []
    for i in range(min(3, len(args))):
        parts.append(str(args[i]))
    if not parts:
        parts.append(str(kwargs.get("owner", "?")))
        parts.append(str(kwargs.get("kind", "?")))
        parts.append(str(kwargs.get("control", "?")))
    return tuple(parts)


def _traced_emit(self, *args, **kwargs):
    now = time.monotonic()
    elapsed = now - _started
    key = _key(args, kwargs)

    _events.append((elapsed, key, args, kwargs))
    _counts[key] += 1

    value = args[3] if len(args) > 3 else kwargs.get("value")
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        _values[key].append(float(value))

    # Print the first occurrence immediately, then at most once per second per
    # logical intent. This keeps axis/aim updates readable.
    previous = _last_print.get(key)
    if previous is None or now - previous >= 1.0:
        _last_print[key] = now
        print(
            f"INTENT t={elapsed:7.3f}s "
            f"key={key!r} "
            f"args={_safe(args)} "
            f"kwargs={_safe(kwargs)}",
            flush=True,
        )

    return _original_emit(self, *args, **kwargs)


def _traced_pause(self, *args, **kwargs):
    elapsed = time.monotonic() - _started
    reason = args[0] if args else kwargs.get("reason", "Manual pause")
    _pause_events.append((elapsed, reason))
    print(
        f"PAUSE t={elapsed:.3f}s reason={reason!r}",
        flush=True,
    )
    return _original_pause(self, *args, **kwargs)


def _report():
    print("\n" + "=" * 96)
    print("BATTLE INTENT TRACE SUMMARY")
    print("=" * 96)

    if not _counts:
        print("No BattlePolicy.emit() calls were observed.")
    else:
        print(f"{'intent key':48} {'calls':>8} {'numeric min':>13} {'max':>13} {'last':>13}")
        print("-" * 96)
        for key, count in _counts.most_common():
            values = _values.get(key, ())
            if values:
                vmin = f"{min(values):.4f}"
                vmax = f"{max(values):.4f}"
                vlast = f"{values[-1]:.4f}"
            else:
                vmin = vmax = vlast = "-"
            print(f"{str(key):48} {count:8d} {vmin:>13} {vmax:>13} {vlast:>13}")

    print("\nFIRST EVENTS")
    for elapsed, key, args, kwargs in _events[:20]:
        print(
            f"{elapsed:7.3f}s {key!r} "
            f"args={_safe(args)} kwargs={_safe(kwargs)}"
        )

    if len(_events) > 20:
        print("\nLAST EVENTS")
        for elapsed, key, args, kwargs in _events[-20:]:
            print(
                f"{elapsed:7.3f}s {key!r} "
                f"args={_safe(args)} kwargs={_safe(kwargs)}"
            )

    if _pause_events:
        print("\nPAUSE EVENTS")
        for elapsed, reason in _pause_events:
            print(f"{elapsed:7.3f}s reason={reason!r}")
    else:
        print("\nPAUSE EVENTS: none")

    print("=" * 96)


def main():
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
        BattlePolicy.emit = _original_emit
        BattlePolicy.pause = _original_pause
        _report()


if __name__ == "__main__":
    raise SystemExit(main())
