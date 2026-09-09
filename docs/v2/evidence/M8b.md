# M8b implementation report

Status: DONE_WITH_CONCERNS — implementation and actual compiled verification complete; one earlier verification safety incident is disclosed below. Independent review remains coordinator-owned. No unresolved functional defect was found in self-review; live hardware acceptance and external CI are not claimed.

## Scope, isolation and commits

Every command used `C:/Develop/game/WT/AutoNavy_WT-v2` explicitly. Started at e2d7637 on feature/v2-modernization; preserved accepted M8a and the original checkout. Coordinator independently committed ec84f37 during this work. No push/PR/merge/tag/release, driver/global package/config change, game launch or intentional live input/capture occurred. The incident prevents a blanket claim that every test was device-free.

Scoped commits:
- c7aabc5 — fix: make launcher readiness offline and preserve exact CLI arguments
- 818bd5aa04e3c9984472e72d23600cbb554a98f5 — feat: validate real standalone resources and frozen worker boundaries
- d6b03a643b84cd5cb5023351b361747667bb21da — docs: record M8b operation guide and actual compiled verification

Final HEAD d6b03a643b84cd5cb5023351b361747667bb21da. Final working tree has only coordinator-owned `docs/v2/STATUS.md` modified. Compiled Python source hashes match code commit818bd5a exactly; see evidence/m8b/m8b-build-source-manifest.json. A later staging-only change removed redundant root MIGRATION.md (relative links work under docs/v2); that separate script hash is recorded. The ZIP is an immutable local build/doc snapshot preceding this evidence/handoff commit.

## What changed

- Source/packaged batch and PowerShell wrappers default to offline configuration validation, never automatic installer/preflight/driver prompts. Exact argv survives both Windows PowerShell5.1 legacy native binding and PowerShell7 standard binding, including Unicode/spaces/empty strings/embedded quotes/trailing backslash; child statuses preserved. Missing source environment fails with explicit install guidance. Manifest paths cannot select an executable outside the package.
- Explicit Core/Dev/Runtime/Build installation changes only project .venv/cache and refuses to delete an incompatible/incomplete environment. Static readiness reads pinned metadata and validates resources/config; deprecated --installation-only means static runtime readiness. Full preflight stays explicit and queries capabilities without acquiring/relinquishing vJoy. Removed retired SciPy/Matplotlib/simple_pid from preflight import requirements; original runtime version pins remain unchanged.
- Added requirements-core/dev and Linux/Windows3.11 core CI. Narrow skips isolate actual PowerShell/registry/DLL/native-extension checks; pure fake adapters still run. Windows build workflow is manual and has no release or artifact publication. Authored workflows were not executed remotely.
- Build uses installed local CPython3.11.9x64/Nuitka4.2.1/MSVC14.5, bounded checked native PowerShell output deletion and .output caches. No implicit pip/compiler/helper downloads. Includes dynamic autonavy/capture/planner modules, DXcam/Windows adapters, exact native extension, config, fixture, templates and pyvjoy/utils/x64/vJoyInterface.dll. Nuitka's installed bundled PE scanner replaces missing Dependency Walker; experimental flag is pinned/documented.
- All actual entrypoint shims call freeze_support. Explicit standalone --offline-smoke validates packaged resources, production ProcessCapture with generated pixels and actual NativeJob/native JPS with a generated tactical image. Contradictory flags fail before adapters; no camera/input/telemetry is opened by this diagnostic.
- Relative --config paths now use the distribution root consistently with resources/fixtures; absolute external configs remain absolute. Resolved config source is printed for check-config and logged for runtime.
- English README/MIGRATION cover source/packaged install/config/replay/build, manual DXcam/OBS/live opt-in, Simplified Chinese1280x720/UI100%/DPI96, translated/negative origins, numeric OBS index/operator trust/composition, F8/F9 live only/Ctrl+C dry-run, matchmaking capability, logs, retired compatibility behaviors and untouched-worktree rollback. Retain M8a menu376–394ms/battle167–170ms; no30Hz/live/source-latency claim. Existing localized legacy preflight messages remain explicitly described.

## TDD and focused execution evidence

All commands below ran in the isolated worktree with `.venv/Scripts/python.exe` unless stated. Full outputs are tracked under `docs/v2/evidence/m8b/` with matching original `logs/v2/` filenames. Tool command exit outputs were inspected; shell redirection sometimes returned the final Get-Content status, so pytest outcomes are taken from preserved test logs, not that shell status.

1. Plan written first: docs/v2/plans/M8b.md. Launcher RED used isolated copied source fixtures with checker/installer traps and a junction to the test interpreter, never the real unsafe launcher path. Two initial harness mistakes (array passing/venv cfg) were corrected before valid RED. `-m pytest tests/test_launcher.py -k isolated -q --tb=short`:6failed, reproduced forbidden checker→installer flow plus rejected CLI argv. `m8b-launcher-red.txt`. After fix `-m pytest tests/test_launcher.py -q --tb=short`:13passed5.82s, including policy test strengthened from allowing0/2/3 to requiring0. `m8b-launcher-green.txt`.
2. Static/package/smoke RED: `-m pytest tests/test_check_environment.py tests/test_build_release.py tests/integration/test_packaging_smoke.py -q --tb=short`:7failed9passed4.37s. Missing static metadata semantics, config/fixture/exact-native ZIP resources and --offline-smoke. This run contains the safety incident below. `m8b-build-red.txt`.
3. Guarded corrected static/smoke GREEN: `-m pytest tests/test_check_environment.py tests/integration/test_packaging_smoke.py -q --tb=short`:14passed1.52s. Combined `-m pytest tests/test_build_release.py tests/test_launcher.py tests/test_check_environment.py tests/integration/test_packaging_smoke.py -q --tb=short`:29passed9.60s. `m8b-static-smoke-green.txt`, `m8b-tooling-green.txt`.
4. Nonmutating full-preflight fake-API RED: `-m pytest tests/test_runtime_preflight.py -k 'configured or retained' -q --tb=short`:2failed18deselected0.06s (old acquisition and unnecessary legacy imports). After removal `-m pytest tests/test_runtime_preflight.py tests/test_check_environment.py tests/test_launcher.py -q --tb=short`:43passed6.24s. `m8b-preflight-red.txt`, `m8b-preflight-green.txt`. No live preflight was used for this correction.
5. PS7 self-review RED: `-m pytest tests/test_launcher.py -k 'isolated and pwsh' -q --tb=short`:6failed13deselected6.39s, confirming extra literal quotes under its different native binding. GREEN `-m pytest tests/test_launcher.py -q --tb=short`:19passed13.39s. `m8b-pwsh-red.txt`, `m8b-pwsh-green.txt`.
6. Manifest traversal self-review RED: `-m pytest tests/test_launcher.py -k 'manifest_cannot or installer_refuses' -q --tb=short`:1failed1passed0.70s (incomplete installer test characterized already-safe behavior). GREEN `-m pytest tests/test_launcher.py tests/test_build_release.py -q --tb=short`:23passed16.17s. `m8b-selfreview-red.txt`, `m8b-selfreview-green.txt`.
7. Actual compiled command revealed relative config was caller-cwd-dependent. Source regression RED `-m pytest tests/integration/test_packaging_smoke.py -k relative -q --tb=short`:1failed4deselected0.21s, misleading caller config shadowed packaged default. Fixed root resolution and source diagnostics; GREEN `-m pytest tests/integration/test_packaging_smoke.py tests/integration/test_replay.py tests/integration/test_diagnostics_runtime.py -q --tb=short`:57passed9.75s. Existing absolute-config tests retained; final compiled external Unicode/spaced config also verified. `m8b-config-red.txt`, `m8b-config-green.txt`.

## Fresh core-only environment and full regression

Executed:

```powershell
.venv/Scripts/python.exe -m venv .output/core-venv
.output/core-venv/Scripts/python.exe -m pip install --disable-pip-version-check --cache-dir logs/v2/build-cache/pip -r requirements-dev.txt
.output/core-venv/Scripts/python.exe -m pytest tests -q --tb=short
.output/core-venv/Scripts/python.exe -m pip list --format=freeze
```

Initial full core suite454passed73.12s (`m8b-core-full.txt`). Fresh environment has14 explicitly pinned core/dev distributions plus bootstrap pip24.0/setuptools65.5.0,16 total; exact list `m8b-core-packages.txt`. No DXcam/pyvjoy/pywin32/keyboard/PyDirectInput/SciPy/Matplotlib/simple_pid distribution. Install downloaded wheels/metadata into the project-local cache where needed; did not alter global Python. This is actual headless dependency separation on Windows, not an executed Linux CI claim.

After final config/launcher tests were added:

```powershell
.venv/Scripts/python.exe -m pytest tests -q --tb=short
.output/core-venv/Scripts/python.exe -m pytest tests/integration/test_packaging_smoke.py tests/test_launcher.py -q --tb=short
```

Final full unfiltered suite **463passed80.29s** (`m8b-final-full.txt`); final core-focused **26passed15.47s** (`m8b-final-core-focused.txt`). No exclusions remain. Final staging documentation-layout cleanup additionally checked with `-m pytest tests/test_build_release.py -q --tb=short`:2passed2.80s (`m8b-final-packaging-tests.txt`).

Scoped lint:

```powershell
.venv/Scripts/python.exe -m ruff check autonavy/packaging_smoke.py scripts/check_environment.py tests/test_launcher.py tests/test_build_release.py tests/test_check_environment.py tests/integration/test_packaging_smoke.py --output-format concise
git diff --check
git diff --exit-code 45fc36c -- src path.json toolkit/way_search.cp311-win_amd64.pyd
```

All checks passed; no protected tracked asset/route/native byte changes. Only expected Git CRLF normalization warnings. Initial lint import-order/unused-variable findings were corrected narrowly; no repository-wide formatting.

## Actual build and compiled execution

Prerequisites were present; `scripts/check_environment.py --mode build` returned0 using static metadata/config/resources (`m8b-build-readiness.txt`). Prebuild free space9,333,927,936bytes. Actual repeated build command:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1
```

- Build1 (`m8b-build-1.txt`) exit1: missing Dependency Walker; empty stdin refused optional tool download. No compiler/global install. Investigated installed Nuitka DllDependenciesWin32.py/SharedLibraries.py: force-dependencies-pefile uses bundled inline PE parser. Added `--experimental=force-dependencies-pefile`, preserving Nuitka4.2.1 pin. No additional helper package/download needed.
- Build2 (`m8b-build-2.txt`) exit0: actual cl14.5 compiled388C files,0cachehits/388misses; produced executable and ZIP. Actual compiled absolute-config/replay/capture-child/native-planner smoke passed. First relative-config command failed2; retained `m8b-compiled-smoke-1.json`, diagnostic successes in `m8b-compiled-smoke-diagnostic.json`. Source fix above required rebuild.
- Build3 (`m8b-build-3.txt`) exit0 after config source fix: compiled388C files,386cachehits/2misses; produced actual final executable. Nuitka report `nuitka-report.xml` and source SHA manifest retained. Anti-bloat notice excludes PIL.ImageQt (no Qt feature used); default cv2 DLL and certifi cacert.pem inclusion logged. No warning is presented as executed live functionality.
- Final staging refresh (`m8b-final-stage.txt`) exit0 used the real build3 distribution, **not a synthetic executable**:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -SkipCompile -DistributionPath .output/nuitka/autonavy.dist
```

This refreshed noncompiled wrapper/docs layout. SkipCompile is assembly only; build3 provides the actual compile evidence. Recursive deletion stayed in resolved checked output/staging targets via native PowerShell. No environment/source/unrelated deletion. Optional downloads were refused; caches are local. About8.17GB free after final staging before verification extraction.

The real final ZIP was extracted into fresh `.output/verified-package` after checking every ZIP destination remains within it. Executed from temporary unrelated working directories, with absolute executable/wrapper paths (exact arrays/cwd/stdout/stderr in `m8b-compiled-final.json`, `m8b-compiled-external-batch.json`):

```text
AutoNavy_WT.exe --check-config --config configs/default.toml                   exit0
AutoNavy_WT.exe --dry-run --capture replay --fixture fixtures/smoke --max-frames 3  exit0,frames3,stopped
AutoNavy_WT.exe --offline-smoke                                               exit0
AutoNavy_WT.exe --offline-smoke --enable-input                                exit2
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <package>/scripts/run.ps1 -CheckOnly  exit0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <package>/scripts/run.ps1 --dry-run --capture replay --fixture fixtures/smoke --max-frames 3  exit0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <package>/scripts/run.ps1 --unknown-option  exit2
AutoNavy_WT.exe --check-config --config <absolute Unicode/spaced external TOML>  exit0, resolved external source retained
cmd.exe /d /c <package>/ЗАПУСТИТЬ.bat -CheckOnly -NoPause                        exit0
```

Frozen diagnostic: capture_publication1, capture_child_exit0, planner_child_exit0, route_points91, resources4, hardware_openedfalse. This executes the production capture/native-planning process owners and actual Windows native planner, with generated data only. Pyvjoy SDK DLL placement is checked as a file, not imported/actuated by the smoke. All125 src files in extracted ZIP byte-equal source; exact native extension, path.json and SDK DLL byte-equal; tests/ absent. Source actual CLI help/CheckOnly/replay3/invalidexit2 from unrelated cwd also passed (`m8b-source-cli.json`).

Final local artifacts (`m8b-artifact-hashes.json`):
- `.output/AutoNavy_WT-win64.zip`:68,896,167bytes; SHA256 `0a5417badd91c608b0cbcf8dc4f085101cc3379a6b76fefedaf7ff0a5013ea61`.
- `.output/verified-package/AutoNavy_WT.exe`:30,566,400bytes; SHA256 `fbe585a2abfc31757fa985095ca196311c1549c5d5f6c66f709cb016d243014c`.
- `toolkit/way_search.cp311-win_amd64.pyd`:416,768bytes; SHA256 `abe3ef91491c5c53eda3bc16c63843545942079dea80e80c8a139671fbedf721`.
- `pyvjoy/utils/x64/vJoyInterface.dll`:179,200bytes; SHA256 `4a48db89c3158cf54aca298d77f9a14579ab11acc648199e474c1092e7ee5944`.

## Verification safety incident and limits

During static-readiness RED, the first new test guarded hardware imports but the second metadata-missing test accidentally called old run_checks without that guard. This was my error. Old code attempted its REQUIRED_IMPORTS sequence, including dxcam/pyvjoy/toolkit.way_search, then check_vjoy_driver. The run returned a CheckResult list; pytest truncated its individual results. Successful native-import/query depth is not reconstructible from captured output and was not re-executed to find out.

Installed-source tracing establishes potential DXcam factory/adapter enumeration on import, pyvjoy SDK DLL load and vJoyEnabled/DriverMatch/status/axis/button queries; if enabled/free, old preflight could briefly acquire/relinquish ownership. Those effects cannot honestly be excluded. The inspected path contains no explicit frame capture or keyboard/mouse/axis/button write; no installer/game/global configuration command was invoked. Do not describe the entire milestone verification as device-free. Coordinator informed the user and owns `docs/v2/evidence/M8b-verification-incident.md`.

Prevention/correction: guarded checker tests now block native import/driver paths; new static readiness does only metadata/config/resource checks. Old preflight acquisition was removed and fake-API RED/GREEN verifies it. All subsequent compiler/resource/replay/child diagnostics followed explicit offline paths; real Windows SDK version-only packaging test remains narrowly platform-scoped. The original failing log is preserved durably.

Remaining manual/not-run gates: live DXcam/OBS/device identity/composition/profile validation, actual vJoy/input/hotkey/focus/device cleanup and game behavior, deliberate full manual hardware preflight, Linux execution/external CI. Experimental bundled PE scanner is pinned and actual compiled native route/core smoke passed, but this cannot certify unexecuted live hardware dependencies. No external publication occurred. No performance claims beyond accepted M8a data.

## Files and handoff

Production/tooling: scripts/{launcher,run,install,check_environment,build}, runtime_preflight.py, requirements-core/dev, .github/workflows/{core,build_prog}, all CLI shims, autonavy/{cli,config,packaging_smoke}, fixtures/smoke/manifest.json. Tests: test_launcher/check_environment/runtime_preflight/build_release and integration/test_packaging_smoke. Docs: README, MIGRATION, plans/M8b and evidence/m8b. Coordinator shared STATUS/PLAN/DECISIONS/VERIFICATION/REVIEW were not staged or overwritten.

Self-review covered offline routing/import boundaries, argv/exit propagation across both shells, manifest bounds, environment/output deletion policy, requirements/platform guards, frozen startup/child cleanup, dynamic imports/native/DLL/assets, config precedence/paths, actual ZIP/resource identity, docs/profile/OBS/hotkey/queue/performance precision. Found and fixed PS7 quoting, manifest traversal and relative config resolution as recorded above. Ready for independent spec/quality review against code818bd5a/finalHEADd6b03a6. Keep branch/worktree/artifacts; no push or merge.
