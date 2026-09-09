# V2 migration and rollback

V2 development is isolated at `C:\Develop\game\WT\AutoNavy_WT-v2` on `feature/v2-modernization`; the preserved original checkout is `C:\Develop\game\WT\AutoNavy_WT` on `master`. No push, merge, release or original-checkout modification is part of this delivery. Game automation risks and sanctions remain unchanged.

## Startup and dependency changes

The package CLI is authoritative. `autonavy.py`, `python -m autonavy`, `start_prog.py`, `main.py` and `pilot.py` delegate to it; freeze support runs before CLI parsing. `ЗАПУСТИТЬ.bat` and `scripts/run.ps1` without arguments now check configuration and exit. `-CheckOnly` is offline config validation. Automatic environment repair, hardware preflight, vJoy install/configuration prompts and implicit legacy `--run` startup have been retired. Missing/incompatible environments require an explicit local installation; nothing is deleted automatically. Legacy manifestless `AutoNavy_WT.dist` and `start_prog.dist` discovery is retired: these directories cannot preempt v2 source, and a root containing only such artifacts is refused without execution. Packaged startup requires manifest schema version1 and launcher version2.0.0; legacy, missing or unsupported versions fail before any child process, including the compatibility `--run` flag. This is a CLI compatibility check, not executable authentication.

`requirements-core.txt` contains pinned headless runtime dependencies; `requirements-dev.txt` adds pytest/Ruff. Windows `requirements.txt` retains every original version, including unused legacy SciPy/Matplotlib/simple-pid for source compatibility; core and standalone production code do not need them. `requirements-build.txt` adds Nuitka4.2.1/ordered-set4.1.0/zstandard0.23.0. CPython3.11x64, NumPy1.26.0/OpenCV4.8.0.74, DXcam0.0.5 and the exact native binary ABI are unchanged. No DXcam upgrade or live speed ranking was justified.

## Safe commands

Run from the source root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -Mode Core
.venv/Scripts/python.exe -m autonavy --check-config --config configs/default.toml
.venv/Scripts/python.exe -m autonavy --dry-run --capture replay --fixture fixtures/smoke --max-frames 3
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 --dry-run --capture replay --fixture fixtures/smoke --max-frames 3
```

Install `-Mode Dev` for tests, `-Mode Runtime` for manually prepared Windows live capture/input, or `-Mode Build` for local compiler prerequisites. Install only changes the local environment/cache. Build requires existing MSVC and uses the pinned Nuitka bundled PE dependency parser; no automatic helper/compiler downloads or publication. `scripts/build.ps1 -SkipCompile` is ZIP assembly, not compiler verification.

After extracting the entire ZIP, use these from any working directory (substitute its absolute path):

```powershell
& 'C:\path with spaces\AutoNavy_WT.exe' --check-config --config configs/default.toml
& 'C:\path with spaces\AutoNavy_WT.exe' --dry-run --capture replay --fixture fixtures/smoke --max-frames 3
& 'C:\path with spaces\AutoNavy_WT.exe' --offline-smoke
```

Relative config/resource/fixture paths use the executable/source root. A custom config can be absolute; logs/cache are separately configurable and cannot overwrite protected templates/routes. `--offline-smoke` uses generated pixels and the real capture/native-planner child boundaries; it rejects accompanying flags and opens no camera/input/telemetry. The three-frame fixture is packaged under `fixtures/smoke`; development `tests/` is not shipped. Exit0 means normal finite completion/deliberate stop, exit2 invalid config/CLI, exit3 runtime/startup failure. Wrappers retain exact arguments and child status.

## Before any manual live acceptance

Use [README](../../README.md) for the exact manual DXcam/OBS dry-run and explicit `--enable-input` commands, vJoy bindings and operator checklist. Full `--preflight [--status-file ...]` remains an explicit manual hardware/network check. It queries capabilities but no longer acquires/relinquishes vJoy. It never installs or configures drivers. Static `scripts/check_environment.py --mode core|runtime|build` reads metadata/config/resources without hardware imports; legacy `--installation-only` now means static runtime readiness.

The supported recognition profile is Simplified Chinese UI, native1280x720 game content, UI100%, DPI96. English/Russian game interfaces are not supported by existing templates. Translated and negative-origin windows are mapped; arbitrary scaling is not calibrated. Select DXcam adapter/output explicitly. OBS uses OpenCV numeric device index/API, whose identity may change: the operator must confirm it is the intended Virtual Camera and correctly map `geometry.obs_content_rect`. Cropping, bars, overlays and scene changes can invalidate content. No scene or display setting is changed automatically.

Input requires the explicit `--enable-input` flag every launch; config alone cannot enable it. It can click menus/join matchmaking and operate a battle. Replay cannot enable it. F8 emergency-stop/F9 pause-resume hooks exist only in live-input mode; dry-run stops with Ctrl+C and replay finishes its finite sequence. Focus loss/stop/pause invalidates pending intents and releases owned input; resume requires fresh context. No automatic validation establishes that real game/input behavior is correct.

## Compatibility retirements and diagnostics

`pilot.pathfinder` callable is retired; `pilot.py` is a CLI shim. Offline `toolkit/process_path` compatibility wrappers no longer perform random selection, interactive prompting or file-writing route behavior. V2 runtime uses deterministic route filtering/controllers and bounded native planning, not the old side-effectful bot imports. `path.json`, original template names/pixels and `toolkit/way_search.cp311-win_amd64.pyd` remain byte-preserved.

Runtime logs rotate in `logs/v2/autonavy.log`; launcher logs in `logs/launcher-*.log` can be cleaned manually. Debug preview and per-frame output are explicit opt-ins. Receive age is not source-render age, CPU/memory measurements may cover only the parent, and synthetic replay cannot establish live capture latency. Measured offline menu medians376–394ms and battle167–170ms exceed30Hz; see [BENCHMARKS](BENCHMARKS.md). Full source/compiled validation and the bounded verification incident are disclosed in [VERIFICATION](VERIFICATION.md); live capture, physical input and external CI are separate manual/not-run gates.

## Rollback

Stop the v2 process first (F8 in live mode, Ctrl+C in dry-run; wait for child cleanup). Return to `C:\Develop\game\WT\AutoNavy_WT` or the preserved original revision/worktree; no reset, checkout overwrite or worktree deletion is required. Keep v2 logs and configuration for diagnosis. The old checkout retains its old behavior, assumptions and automation risks. Do not copy v2 environments into it or change installed system drivers as a rollback shortcut.
