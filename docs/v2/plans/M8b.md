# M8b Tooling and Packaging Implementation Plan

> **For agentic workers:** Use the installed subagent-driven-development implementer workflow inline; coordinator arranges independent review. No additional writers.

**Goal:** Offline-safe wrappers and a real, device-free verified Windows standalone distribution.
**Architecture:** Thin PowerShell wrappers forward argv to the existing CLI. Static readiness inspects dependency metadata/resources; full hardware preflight stays explicit. Nuitka includes dynamic runtime modules and an offline child/resource diagnostic.
**Tech Stack:** Windows PowerShell 5.1, CPython 3.11 x64, Nuitka 4.2.1, pytest 8.3.5, Ruff 0.11.13.
**Spec:** docs/v2/SPEC.md BUILD-01, CLI-01, CFG-01, HANDOFF and both task-8 briefs.

## Global constraints
- Work only in AutoNavy_WT-v2 on feature/v2-modernization; preserve M8a and all resource/native bytes.
- Preserve CPython3.11 x64, NumPy1.26.0/OpenCV4.8.0.74/DXcam0.0.5 pins and pyvjoy utils/x64 DLL layout.
- No hardware/input/hooks/game/network telemetry, global installs, push or release. Compiler runs use local venv/caches.
- New prose and program output English. Existing third-party notices and game resource names unchanged.

## 1. Offline launchers (A32/A37)
Files: scripts/{launcher,run,install}.ps1, scripts/check_environment.py, tests/test_launcher.py, tests/test_check_environment.py.
- [x] RED: isolated source checkout with fake checker/installer trapping unsafe calls; CheckOnly must call entrypoint --check-config and return0. Forward --config with spaced Unicode path, empty argument, quotes/backslash, flags and exit17 exactly. Tighten policy test to exit0 before restoring unfiltered regression.
- [x] Implement explicit install modes Core/Dev/Runtime; no automatic repair/deletion. Launcher defaults to --check-config and explains live capture opt-in. Explicit arguments are passed as argv without cwd changes; all child codes retained. Native argv quoting handles Windows PowerShell empty strings and quotes.
- [x] GREEN: `.venv/Scripts/python.exe -m pytest tests/test_launcher.py tests/test_check_environment.py -q`.

## 2. Dependencies and actual packaging (A36/A37)
Files: requirements-{core,dev,build}.txt, .github/workflows/*.yml, scripts/build.ps1, autonavy.py, autonavy/__main__.py, autonavy/cli.py, autonavy/packaging_smoke.py, fixtures/smoke/manifest.json, tests/test_build_release.py, tests/integration/test_packaging_smoke.py.
- [x] RED: metadata-only core/build readiness under import guards, Linux core readiness; ZIP requires configs/default.toml, fixture and exact native filename; explicit --offline-smoke rejects live options and exercises real capture/planner spawned owners.
- [x] Implement static pinned readiness, bounded validated output deletion and no implicit pip/compiler download. Include autonavy dynamic package, runtime preflight, DXcam/pyvjoy and toolkit native module; stage assets/config/fixture/docs and preserved DLL layout. freeze_support at executable entrypoints.
- [x] GREEN focused tests; create ignored .output/core-venv from pinned dev/core using local pip cache and execute full headless suite.
- [x] Actual compile `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1`, capture full log. Fix observed compiler/runtime causes. Execute compiled --check-config, finite --capture replay --fixture fixtures/smoke --max-frames 3, --offline-smoke from unrelated cwd. This diagnostic validates real native planner but only synthetic capture and never loads native input SDK.
- [x] Author core Linux/Windows3.11 CI with narrow platform guards; Windows build workflow validates offline executable and never releases. Authored CI is NOT RUN.

## 3. Operation documentation, self-review and report
Files: README.md, docs/v2/MIGRATION.md, .superpowers/sdd/PLAN/task-8b-report.md.
- [x] Document source/core/runtime/build installation, safe config/replay/packaged commands, explicit manual live DXcam/OBS/preflight, Simplified Chinese native1280x720/UI100%/DPI96 calibration, translated/negative-origin support, OBS index/trust/composition, F8/F9 live only, dry-run Ctrl+C, input may queue, logs, compatibility retirements and untouched-checkout rollback.
- [x] Disclose M8a menu376–394ms/battle167–170ms, no30Hz or source-latency claim; all actual hardware/manual gates remain NOT RUN.
- [x] Read diff and requirement coverage, focused Ruff/diff check, final full unfiltered regression once after production self-review. Scoped commits only owned files. Exact commands/logs/SHAs and remaining limits in report; coordinator owns shared status/evidence/review files.

## Execution result

Code commits c7aabc5 and 818bd5a; final unfiltered463passed, core-only454passed plus final26focused. Actual final Nuitka/MSVC compiled ZIP and frozen capture/native-planner smoke passed from unrelated cwd. All compiled Python hashes match818bd5a. Failed attempts and verification safety incident retained in evidence/m8b and the worker report. Independent review is coordinator-owned and pending; live acceptance/CI remain unexecuted.
