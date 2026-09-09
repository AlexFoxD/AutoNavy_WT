# AutoNavy_WT v2

Experimental Windows automation for War Thunder naval battles: template recognition, local game telemetry, navigation and coordinated keyboard/mouse/vJoy input. V2 uses bounded capture and planning workers, validated configuration and a finite offline replay mode. It is not a universal or production-validated game bot.

**Game automation may violate War Thunder rules and lead to account bans, lost game data or other sanctions.** This project is for education and technical experiments. Authors and contributors accept no responsibility for direct or indirect damage. Review the game's rules and applicable law; do not run it if you cannot accept these risks. Modernization provides no protection from sanctions.

## Start safely

Windows runtime/build compatibility is **CPython 3.11 x64**, NumPy **1.26.0**, OpenCV **4.8.0.74** and the unchanged `toolkit/way_search.cp311-win_amd64.pyd`. Do not rename the extension. A complete standalone ZIP includes Python; source installation needs Python 3.11 x64. No driver is installed automatically.

From the source root in Windows PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -Mode Core
.venv/Scripts/python.exe -m autonavy --help
.venv/Scripts/python.exe -m autonavy --check-config --config configs/default.toml
.venv/Scripts/python.exe -m autonavy --dry-run --capture replay --fixture fixtures/smoke --max-frames 3
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 -CheckOnly
```

Core installation is sufficient for configuration, replay and tests. `-Mode Dev` adds pinned pytest/Ruff; `-Mode Runtime` installs the preserved Windows runtime requirements; `-Mode Build` also installs pinned compiler support packages. Install writes only the local `.venv` and project pip cache and refuses to delete an incompatible existing environment. A C++ compiler and any live drivers require separate manual preparation.

Double-clicking `ЗАПУСТИТЬ.bat`, running it with `-CheckOnly`, or running `scripts/run.ps1` without arguments validates configuration and exits. Wrappers never auto-install, repair, launch a game or offer driver configuration. Explicit CLI arguments pass through unchanged, including paths containing spaces. Process-scoped `-ExecutionPolicy Bypass` does not change persistent execution policy.

For a built ZIP, extract the entire archive, then run from its root:

```powershell
./AutoNavy_WT.exe --check-config --config configs/default.toml
./AutoNavy_WT.exe --dry-run --capture replay --fixture fixtures/smoke --max-frames 3
./AutoNavy_WT.exe --offline-smoke
```

The fixture has three generated color frames, no screenshots, and always finishes. `--offline-smoke` is a separate diagnostic: it checks packaged files, transfers generated pixels through the production capture child and runs the real bundled pathfinder on a generated image in its planner child. It does not open a camera, vJoy, global hooks or telemetry. It rejects all other runtime flags and requires the Windows native ABI. Source equivalent: `.venv/Scripts/python.exe -m autonavy --offline-smoke`.

For any source or packaged executable, relative resource/config/fixture paths resolve from the distribution root, independently of the caller's directory. Use an absolute executable path when calling from another directory. Settings precedence is built-in defaults, explicit TOML, then CLI overrides. Unknown keys and incompatible options fail before devices open. Keep personal config outside template directories; default `configs/default.toml` is an example. Configuration alone cannot enable physical input.

## Manual capture and live input

These commands are **manual acceptance only**; they have not been validated against a live game, DXcam desktop, OBS or physical input during modernization. First install `-Mode Runtime`, prepare the game/capture profile and inspect the chosen config. Stop dry-run capture with **Ctrl+C**.

```powershell
.venv/Scripts/python.exe -m autonavy --dry-run --capture dxcam --config configs/default.toml
.venv/Scripts/python.exe -m autonavy --dry-run --capture obs --config configs/default.toml
```

DXcam remains **0.0.5**. `capture.device_index` and `output_index` select its adapter/output. The implementation supports translated windows and negative desktop origins when the configured DXGI output contains the client rectangle. Multiple monitors do not remove calibration requirements. No DXcam-versus-OBS speed ranking has been measured; the [upgrade assessment](docs/v2/evidence/DXcam-upgrade-assessment.md) explains retention.

For OBS, manually start Virtual Camera and select its OpenCV `capture.device_index` (numeric camera indices may change). `capture.obs_api` is `auto`, `dshow` or `msmf`. An index alone cannot prove that a device is OBS. The operator must verify the source identity and composition. Set `geometry.obs_content_rect` to the exact game-content rectangle within the delivered frame. Black bars, cropping, overlays, scene changes, scaled content and other windows invalidate matching or input mapping. OpenCV reports negotiated dimensions/FPS; receive time cannot prove when OBS rendered the original frame. No OBS scene or device is configured automatically.

The bundled templates target **Simplified Chinese War Thunder UI**, native game content **1280×720**, game UI scale **100%**, Windows **DPI 96** and the `legacy-1280x720` profile. English program documentation does not add English or Russian game-UI support. Keep template pixels/names unchanged. Different languages, dimensions, scaling or themes require separate manual template calibration. Geometry translation works; arbitrary image scaling is not a calibrated recognition profile.

The live target uses `DagorWClass` and must be foreground before actuation. Keep default bindings for Esc, Enter, arrows, W, S, Shift, X, Space and mouse actions. vJoy device 1 must expose X/Y/Z/RY and at least eight buttons; bind its Z axis to steering. Install/configure a compatible vJoy 2.1.9.1 driver manually; the included SDK DLL is not a driver. Live telemetry uses only `http://127.0.0.1:8111` (`map_obj.json`, `map_info.json`, `map.img`).

After manual dry-run validation, these explicitly enable real input and **can click menus, join a queue and automate battle**:

```powershell
.venv/Scripts/python.exe -m autonavy --capture dxcam --config configs/default.toml --enable-input
.venv/Scripts/python.exe -m autonavy --capture obs --config configs/default.toml --enable-input
```

**F8 stops; F9 pauses/resumes only in explicit live-input mode**, where global hotkeys are registered. Dry-run/replay do not register them. Focus loss, pause, stop or stale context invalidates queued intentions and releases owned input; resuming requires fresh observations. Replays reject `--enable-input`. Hardware behavior, cleanup and game mappings still require manual acceptance.

Optional full hardware diagnosis remains separate:

```powershell
.venv/Scripts/python.exe -m autonavy --preflight --status-file logs/manual-preflight.json
```

This command imports/enumerates hardware adapters, queries vJoy capabilities, checks the game window/resources and local telemetry. It does not acquire vJoy ownership, actuate, install drivers or change settings. It is not a headless readiness command. Some retained legacy diagnostic messages remain localized. Static source/build readiness is `.venv/Scripts/python.exe scripts/check_environment.py --mode core` (or `runtime`/`build`); those modes inspect pinned metadata and resources without hardware imports.

## Logs, tests and measurements

Normal completion, finite replay and deliberate Ctrl+C return **0**; invalid CLI/config returns **2**; startup/runtime failures return **3**. Wrappers preserve child codes. Full legacy preflight has its own result summary/status JSON. Runtime logs rotate under `logs/v2/autonavy.log` (2 MB, three backups by default); launcher process logs are under `logs/launcher-*.log`. Delete old launcher logs manually when appropriate. Runtime metrics/history are bounded, recurring faults throttled, preview and per-frame output off by default. No screenshots or typed text are recorded automatically. Explicit preview frequency is configured separately with `diagnostics.preview_fps`.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -Mode Dev
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe scripts/benchmark_pipeline.py --samples 20 --warmups 3 --repetitions 3 --seed 42 --output logs/v2/pipeline
```

Headless Linux: create a Python 3.11 venv, install `requirements-dev.txt`, run `python -m pytest tests -q`. Only real Windows PowerShell/registry/DLL/native-ABI checks skip there; fake Windows adapters still run. CI definitions cover Linux/Windows core tests and an explicit Windows packaging workflow; authoring these workflows does not mean CI executed.

[Executed benchmarks](docs/v2/BENCHMARKS.md) show localized preprocessing/matching gains on deterministic pixels. Real offline menu decisions took **376–394 ms** median and battle decisions **167–170 ms** median. Both exceed the configured 30 Hz target. These are not whole-project speedups or measured game-render-to-input latency. Synthetic replay timings cannot rank live backends; parent-only CPU/memory excludes isolated children.

## Build and migration

With existing Visual Studio C++ Build Tools, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -Mode Build
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1
```

Build uses the local `.venv`, installed MSVC and project `.output/nuitka-cache`; it does not install compilers/packages or download optional tools. Nuitka **4.2.1** uses its bundled PE dependency scanner (`--experimental=force-dependencies-pefile`) to avoid external Dependency Walker. Missing prerequisites fail clearly. Build output is `.output/AutoNavy_WT-win64.zip` and `.output/AutoNavy_WT-release-stage`. Output cleanup validates bounded paths and rejects redirected directories. The package includes runtime modules, exact native extension, default config, templates, the small synthetic fixture and `pyvjoy/utils/x64/vJoyInterface.dll`; tests/venvs/logs/compiler intermediates are excluded. `-SkipCompile` only assembles an existing distribution and never proves compilation succeeded. No release is published automatically.

See [migration and rollback](docs/v2/MIGRATION.md) and [verification records](docs/v2/VERIFICATION.md) for executed build/test evidence and remaining acceptance checks. V2 production code is original implementation; csgobot was an architectural reference, not copied source/models/dependencies. Preserve third-party notices and external protocol literals. New development prose, identifiers, comments and messages use English.
