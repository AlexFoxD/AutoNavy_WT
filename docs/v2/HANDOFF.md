# AutoNavy_WT v2 handoff

## 1. Delivery

Implementation delivered; hardware validation pending. M0–M9 and independent whole-branch/fix reviews are complete. Offline tests and actual Windows compilation/package checks passed in the scopes below. There is no outstanding mandatory implementation task.

Use [the corrected local ZIP](../../.output/m9-final/AutoNavy_WT-win64.zip), 69,007,274 bytes, SHA256 `75b364a596df4c7d8a9f2302f4acd58fd1166a8505baf28ba1f05a99f669e4a8`. Historical root/m9-fixed archives are not the final delivery. Extract the whole ZIP. It contains the real compiled executable, corrected wrappers, resources and synthetic fixture. The archive is a verified build/document snapshot; later repository handoff records do not change its verified bytes.

## 2. Git and preservation

- Original: `C:\Develop\game\WT\AutoNavy_WT`, source/master `45fc36cc4d173fb1e46eac2dcd1be3338157c500`; clean and unchanged.
- Retained worktree: `C:\Develop\game\WT\AutoNavy_WT-v2`; branch `feature/v2-modernization`.
- Compiled production code: `818bd5aa04e3c9984472e72d23600cbb554a98f5`; final wrapper fix: `e4d207e57fb9ade311a8df15ea27da3d218871f9`. Later commits contain documentation/evidence only. Use `git rev-parse HEAD` for the final handoff commit.
- Original refs, template tree, path.json and exact native bytes were preserved. Final hash check: [final-preservation.json](evidence/m9/final-preservation.json).
- No push, PR, merge, tag or release publication. Keep this worktree and branch; no cleanup/reset is needed.

## 3. Implemented changes

| Replaced/added components | Practical effect |
|---|---|
| CLI/shims, `autonavy/app.py`, `behavior.py` | Actual cancellable battle flow, finite replay and non-actuating defaults; no legacy orchestration fallback. |
| `autonavy/capture`, `geometry.py` | Real DXcam/OBS adapters, bounded latest-frame transport, owned immutable packets, supervised blocking calls and calibrated mappings. |
| `autonavy/vision` | Cached templates/packet preprocessing, one-channel prepared matching, ROI-first masks and immutable throttled previews. |
| `telemetry.py`, `input/` | One fresh snapshot service and one guarded actuation owner; current context checks, bounded scheduling and tracked cleanup. |
| `navigation/` | Real native JPS, ordered waypoints, bounded supervised planning and separate wrapped controllers. |
| Launchers, build/bench scripts, core/dev requirements | Offline readiness, exact argv/status, legacy layout rejection, real frozen worker checks and reproducible measurement evidence. |

## 4. Executed verification

Host: Windows build 26200, CPython 3.11.9 x64, NumPy 1.26.0, OpenCV 4.8.0.74, Pillow 11.1.0; actual build used Nuitka 4.2.1 and MSVC 14.5. Runtime pins and native ABI remain unchanged.

Executed from the v2 worktree:

```powershell
.venv/Scripts/python.exe -m pytest tests -q --tb=short
.venv/Scripts/python.exe -m pytest tests/test_launcher.py tests/test_build_release.py -q --tb=short
.venv/Scripts/python.exe -m ruff check autonavy scripts/benchmark_common.py scripts/benchmark_pipeline.py scripts/benchmark_capture.py scripts/check_environment.py --select E9,F --output-format concise
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -SkipCompile -DistributionPath .output/nuitka/autonavy.dist -OutputPath .output/m9-final/AutoNavy_WT-win64.zip
```

Full suite before final wrapper-only correction: **463 passed in 103.72 s**, no exclusions/warnings. After that correction: **97 focused tests passed in 53.68 s**. No compiled runtime changed between them. Scoped lint and E9/F pass. A broader default style diagnostic reports 247 nonblocking E701/E702/E741 findings; blanket lint compliance is not claimed. Raw RED logs retain original whitespace.

Actual build3 succeeded; final assembly reused that real executable. Nine actual extracted-package commands from an unrelated Unicode directory passed, plus 74 trapped legacy/version guard cases. Frozen synthetic capture and native planning children exited 0; native route contained 91 points. Fresh core-only Windows environment passed 454 full tests, then 26 focused checks after later changes. Linux/external CI were authored but not executed.

Failures are retained: build1 lacked Dependency Walker (bundled PE parser used subsequently); the first compiled relative-config check failed and was fixed/rebuilt; final review found legacy launcher selection/compatibility issues and they were fixed/re-reviewed. The earlier unguarded readiness-test incident is disclosed in [the incident record](evidence/M8b-verification-incident.md): native import/query/brief acquisition depth is uncertain; no explicit frame-grab or actuator-write call existed on that path. Corrective tests do not reconstruct or erase it.

Exact argv/results/logs: [M8b report](evidence/M8b.md), [final fix report](evidence/M9-fix.md), [M9 checks](evidence/m9/README.md), [acceptance map](VERIFICATION.md).

## 5. Measured performance

On deterministic identical pixels, three repetitions of 20 samples plus 3 warmups produced v2/legacy median ratios: preprocessing 0.738–0.903, prepared matching 0.223–0.232, fire mask 0.198–0.204; heading mask 1.076–1.095 (a small slowdown). Fresh real offline menu ticks took 376–394ms median; battle ticks 167–170ms. Both miss the configured 33.3 ms interval. There is no measured whole-project speedup.

Unpaced synthetic capture delivered 600 publications at 290.76/s. Receive ages 0/16 ms use a 15.625 ms-resolution clock and cannot establish zero/source latency. Live DXcam-versus-OBS, GPU/game impact and render-to-input latency were not measured. DXcam remains default and pinned 0.0.5 because no validated upgrade or same-machine live comparison justified changing it. See [BENCHMARKS](BENCHMARKS.md) for raw samples, correctness gates and timing boundaries.

## 6. Operation

The existing local source environment is ready for offline use:

```powershell
Set-Location 'C:\Develop\game\WT\AutoNavy_WT-v2'
.venv/Scripts/python.exe -m autonavy --check-config --config configs/default.toml
.venv/Scripts/python.exe -m autonavy --dry-run --capture replay --fixture fixtures/smoke --max-frames 3
```

From an extracted final ZIP, use `AutoNavy_WT.exe` instead of `.venv/Scripts/python.exe -m autonavy`. Relative config/fixture paths use the source/executable root; absolute external config paths are supported. Batch/PowerShell wrappers without arguments only validate config. Manifestless legacy builds and incompatible manifests are refused.

The following commands are **manual only, not executed live during delivery**. Prepare runtime dependencies and calibration first; see [README](../../README.md):

```powershell
.venv/Scripts/python.exe -m autonavy --dry-run --capture dxcam --config configs/default.toml
.venv/Scripts/python.exe -m autonavy --dry-run --capture obs --config configs/default.toml
.venv/Scripts/python.exe -m autonavy --capture dxcam --config configs/default.toml --enable-input
.venv/Scripts/python.exe -m autonavy --capture obs --config configs/default.toml --enable-input
```

Templates require Simplified Chinese game UI, native 1280×720 content, UI 100%, DPI 96. OBS requires operator-verified camera index/API/composition and exact content rectangle. Input opt-in can click menus and queue for battle. Config alone cannot enable it. F8 stops and F9 pauses/resumes only in live-input mode; use Ctrl+C for dry-run, while replay ends itself. Purchase dialogs pause; no automatic purchase is implemented.

Rollback: stop v2, wait for cleanup, then return to `C:\Develop\game\WT\AutoNavy_WT`. Do not reset or overwrite either checkout or copy environments into the original. Its old behavior and risks remain unchanged.

## 7. Remaining validation and next steps

- Manually validate DXcam/OBS identity, profile/coordinates, interruptions and driver recovery; then, only in an explicitly authorized controlled setting, physical bindings, focus/stop/pause and release behavior. Exact checklist: [VERIFICATION](VERIFICATION.md) and [MIGRATION](MIGRATION.md).
- Profile the measured vision bottleneck before expecting 30 Hz; measure live backend and complete latency on the same machine with a trustworthy clock or visual counter.
- Execute Linux/Windows CI remotely when separately authorized; local Windows success is not remote CI evidence.
- Address 247 nonblocking style findings in a separate focused cleanup if desired; do not confuse that debt with the passing correctness checks.
- Preserve and review the verification incident rather than interpreting it as a hardware PASS. No driver/global changes, game/input validation or external publication is scheduled automatically.
