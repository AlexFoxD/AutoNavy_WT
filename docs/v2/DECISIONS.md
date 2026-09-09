# Implementation decisions

- The supplied architectural design and explicit end-to-end approval satisfy design and execution-choice gates. No design reopening is needed.
- Host native task creation/handoff does not provide an appropriate current-task worktree operation. Use the authorized sibling Git worktree.
- Use the installed Superpowers file-based invocation and subagent-driven implementation with one production writer at a time and read-only task reviews. Persistent user-requested records supersede disposable skill ledger conventions where retention matters.
- Use Python 3.11 in project-local .venv and preserve NumPy/OpenCV/SciPy and DXcam compatibility pins. No global package changes.
- Package `autonavy/` supplies `python -m autonavy`; retain root `autonavy.py` as the packaged launcher shim because inspected build/PowerShell scripts target it.
- Native-only bounded probe is authorized offline verification. No game, vJoy or system-wide hotkeys are used during agent-driven tests.
- Synthetic fixture evidence is not a real-battle recording or recognition calibration.

## Capture lifecycle evidence and dependency decision

Inspected installed DXcam 0.0.5 source at `.venv/Lib/site-packages/dxcam/dxcam.py`: `get_latest_frame` waits indefinitely on a private event; `stop` joins its daemon worker for up to ten seconds then clears shared storage/events; `_on_output_change` retries COM recreation in an unbounded loop without a stop check. `Duplicator.update_frame` uses AcquireNextFrame timeout zero, but that does not bound the reconstruction path. Consequently a stop event alone cannot prove clean native shutdown. Use narrow supervised process isolation for live capture only, with a bounded latest-frame transport and controlled termination after input cleanup. Normal application decisions/telemetry/input remain in one process with managed workers. Fake hanging-source tests must establish application waits wake and capture process is reclaimed.

Current DXcam documentation was reviewed on 2026-09-09 at https://github.com/ra1nty/DXcam. It documents newer lifecycle/zero-copy/timestamp capabilities and a changed implementation. Retain 0.0.5 for this delivery: upgrading is optional and no representative same-machine hardware regression evidence supports an update. Do not call newer APIs on the pinned adapter or infer zero-copy ownership guarantees.

OpenCV property documentation at https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html was reviewed: property availability/effect depends on the backend. OBS must validate actual frame shape/dimensions; setting properties is a request, not proof. A camera read cannot be assumed interruptible by a Python Event.

Requests primary documentation at https://requests.readthedocs.io/en/latest/user/advanced/ was reviewed: reuse a Session, configure connect/read timeouts, and avoid claiming they form a hard total request deadline.

Donor references reviewed on 2026-09-09: https://raw.githubusercontent.com/Priler/csgobot/main/grabbers/obs_vc_grabber.py and base.py. Their architectural boundary is relevant; their RGB conversion and desktop-offset cropping are not adopted. No donor implementation, models or dependencies will be copied. The donor LICENSE says GPLv3 while pyproject metadata differs; retain independent implementation and all existing project notices.

Capture contract clarification: explicit artificial repeats retain the last successful receive timestamp and source metadata; only a genuinely acquired sample receives a new receive time. A publication counter is not presentation FPS. Per-call capture wait timeouts are healthy no-publication outcomes, distinct from source errors; callers can use a short tick-period timeout so scheduling is never forced to wait an entire configured frame timeout. Native hangs are reclaimed on stop; stale-data guards must inhibit input independently.

M3 characterization decision: keep each template's original decoded channels (`IMREAD_UNCHANGED`) for raw color-input Canny. The preserved aim asset src/cir.png carries its shape in alpha, so converting it to three-channel color before Canny loses the signal. The optimization removes channel expansion after Canny, not source channels before it. Initial real-asset normalized score comparisons observed <=4.77e-6 numeric differences with identical locations; tests use6e-6 tolerance. This establishes synthetic math behavior, not live recognition accuracy. Final tests are recorded in M3 evidence when available.

M4 identity/freshness decision: protocol has no reliable server session ID, so telemetry exposes a locally inferred generation keyed by map bounds/grid steps and observed recovery/receive-time gaps. This cancels dependent battle work conservatively; two identical-map sessions with no observed interruption cannot be distinguished. Metadata/image refresh and object requests are not an atomic server snapshot. Exact conditions and per-component TTL semantics are recorded in evidence/M4.md. Menu actions must not depend on absent Player data; battle actions must consume current service validity immediately before dispatch.

M4 request shutdown: one daemon worker owns Session creation/use/close and serial bounded-body requests. Stop interrupts backoff; close joins with a configured budget and reports any still-running worker. A late returning operation drops its result and the worker closes Session itself. Requests inactivity/connect timeout tuples are not total deadlines; no cross-thread Session.close or fabricated forced socket interruption. M5 releases input before these waits. Map images remain bounded encoded in-memory bytes; Pillow (existing pin11.1.0) verifies/decodes within pixel/body limits, OpenCV consumers decode explicitly later.
