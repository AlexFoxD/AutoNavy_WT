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
