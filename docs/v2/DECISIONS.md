# Implementation decisions

- The supplied architectural design and explicit end-to-end approval satisfy design and execution-choice gates. No design reopening is needed.
- Host native task creation/handoff does not provide an appropriate current-task worktree operation. Use the authorized sibling Git worktree.
- Use the installed Superpowers file-based invocation and subagent-driven implementation with one production writer at a time and read-only task reviews. Persistent user-requested records supersede disposable skill ledger conventions where retention matters.
- Use Python 3.11 in project-local .venv and preserve NumPy/OpenCV/SciPy and DXcam compatibility pins. No global package changes.
- Package `autonavy/` supplies `python -m autonavy`; retain root `autonavy.py` as the packaged launcher shim because inspected build/PowerShell scripts target it.
- Native-only bounded probe is authorized offline verification. No game, vJoy or system-wide hotkeys are used during agent-driven tests.
- Synthetic fixture evidence is not a real-battle recording or recognition calibration.
