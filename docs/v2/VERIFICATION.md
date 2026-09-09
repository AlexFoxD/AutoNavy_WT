# Verification evidence

Environment: Windows, project-local CPython 3.11 x64. Source 45fc36cc4d173fb1e46eac2dcd1be3338157c500. No live input or game startup is authorized for verification.

Current stage: M0-M3 independently reviewed; M4 telemetry implementation active. PASS rows identify their concrete milestone scope and evidence. Downstream acceptance remains NOT RUN until implemented and verified. A01 requires another preservation check at final handoff.

Hardware capture, OBS, vJoy actuation, matchmaking, packaged executable and source-to-input latency: NOT RUN.

## M0 executed baseline

- `.venv\Scripts\python.exe -m pytest tests -q`: **42 passed, 14 warnings in 37.97s** (39 existing tests plus 3 new synthetic characterization tests).
- `.venv\Scripts\python.exe -m pytest tests/unit/test_legacy_characterization.py -q`: **3 passed in 0.17s**.
- Interpreter: CPython 3.11.9 x64, Windows build 26200. NumPy 1.26.0, OpenCV 4.8.0.74, Requests 2.32.3, SciPy 1.15.1, pytest 8.3.5.
- The existing launcher policy test invokes `-CheckOnly`, which unexpectedly repairs project-local dependencies. Its permissive exit-code assertion passes despite a `RuntimePath` PowerShell binding failure recorded in `logs/launcher-20260909-180131.log`. This is a pre-existing launcher defect to fix in M8; a passing suite does not establish a working launcher. No driver install or real input occurred. Subsequent verification will avoid this side effect until repaired.
- Matplotlib/Pyparsing deprecation warnings occurred during initial collection; launcher repair restored repository runtime pins afterward. Do not suppress warnings to manufacture a clean baseline.
- Native-only smoke: three subprocess probes, exit 0, bounded 15-second timeouts, detailed cases in AUDIT.md. Not a native game-route accuracy claim.

## Acceptance ledger

| Requirement | Status | Evidence |
|---|---|---|
| A01 / GIT-01 | PASS | M0 scope: isolated `feature/v2-modernization` worktree from exact source 45fc36c; source checkout clean and HEAD/master/default refs unchanged; recorded src/native tree/blob/hash match. Commands and identifiers in Preservation baseline below. Local commit 021f575; no push/merge/release. Final preservation recheck still required at M9. |
| A02 / AUDIT-01 | PASS | M0 scope: AUDIT.md exact-symbol reconciliation and behavior inventory, three bounded native-only probes, environment constraints and executed 42-test baseline plus 3-test characterization recheck above; characterization at tests/unit/test_legacy_characterization.py, committed in 021f575. Hardware accuracy explicitly unverified. |
| A03 / ARCH-01 | PASS | autonavy/{__init__,cli,app}.py and three Python shims; tests/integration/test_replay.py::test_all_supported_imports_are_side_effect_free and ::test_entrypoints_use_safe_cli_from_unrelated_cwd; M1 regression command/results in evidence/M1.md; recheck extended modules at M9 |
| A04 / CAP-01 | PASS | M2: production capture.factory selects ProcessCapture/DXcamSource; fake lifecycle/error/restart tests in tests/unit/test_capture.py and tests/integration/test_capture_runtime.py. Final M2 regression168 pass/1 excluded atceee7bb; evidence/M2.md. Hardware NOT RUN. |
| A05 / FRAME-01 | PASS | M2: bounded latest slot/shared pixel transport and owned FramePacket copies, slow-consumer/replacement/generation-race tests in test_capture.py and test_capture_runtime.py; evidence/M2.md commands/results, reviewedceee7bb. |
| A06 / FRAME-01 | PASS | M2 retained packet/producer-buffer mutation tests and M3 debug-copy/overlay immutability tests pass; packet-local observations unchanged. evidence/M2.md and evidence/M3.md. |
| A07 / FRAME-01 | PASS | M3 Application passes exact acquired packet to VisionPipeline; samepacket degree/ROI observations and import-safe explicit deg_cal.get_deg remove independent capture. test_vision.py/test_vision_runtime.py; evidence/M3.md. Final active-caller audit remains M9. |
| A08 / CAP-03 | PARTIAL | M2 cancellation wakes reads, generation snapshot/start/cleanup races covered, fake hung child reclaimed with bounded process shutdown; pinned native limits documented. Input/cache invalidation integration follows M3/M5/M7. |
| A09 / VISION-01 | PASS | M3 FrameContext/TemplateRegistry raw color Canny outputs feed one-channel match_edges; call-count/cache-version/invalidation tests include alpha-only aim asset. evidence/M3.md:201regression pass1excluded, previewfix36covering pass. |
| A10 / VISION-01 | PASS | M3 real-asset synthetic positive/negative and malformed/constant/oversize/nonfinite tests; frame/desktop ROI mapping and configured-profile gates; required assets validated before capture construction. evidence/M3.md. Live accuracy NOT RUN. |
| A11 / VISION-02 | PASS | M3 test_vision.py validates pixelwise cropped HSV and actual fire/lock/collision ROI mask-Canny behavior; separates neighborhood boundary effects from HSV equivalence. evidence/M3.md. |
| A12 / VISION-02/03 | PASS | M0/M3 no-op morphology, empty/degenerate heading, debug-copy on/off equality;713a507 adds independently throttled copy/draw with injectedclock and deadline tests (36covering passed). evidence/M3.md. |
| A13 / GEOM-01 | PARTIAL | M2 pure GeometrySnapshot transforms and Windows client/output mapping cover translated/negative origins, bounds and content scaling. Actual OBS source/calibration integration follows M7. |
| A14 / GEOM-01 | NOT RUN | Implementation/validation pending |
| A15 / TEL-01 | NOT RUN | Implementation/validation pending |
| A16 / TEL-01 | NOT RUN | Implementation/validation pending |
| A17 / TEL-01 | NOT RUN | Implementation/validation pending |
| A18 / LIFE-01 | NOT RUN | Implementation/validation pending |
| A19 / LIFE-01 | NOT RUN | Implementation/validation pending |
| A20 / INPUT-01 | NOT RUN | Implementation/validation pending |
| A21 / INPUT-01 | NOT RUN | Implementation/validation pending |
| A22 / INPUT-01/02 | NOT RUN | Implementation/validation pending |
| A23 / INPUT-02 | NOT RUN | Implementation/validation pending |
| A24 / APP-01 | NOT RUN | Implementation/validation pending |
| A25 / APP-01 | NOT RUN | Implementation/validation pending |
| A26 / NAV-01 | NOT RUN | Implementation/validation pending |
| A27 / NAV-01 | NOT RUN | Implementation/validation pending |
| A28 / CTRL-01 | NOT RUN | Implementation/validation pending |
| A29 / CAP-02 | NOT RUN | Implementation/validation pending |
| A30 / CAP-02/03 | NOT RUN | Implementation/validation pending |
| A31 / CFG-01 | PASS | autonavy/config.py + configs/default.toml; tests/unit/test_foundations.py::test_config_precedence_and_default_resource_resolution, ::test_invalid_config_is_rejected_before_startup, ::test_cli_input_requires_explicit_flag_and_replay_rejects_it; evidence/M1.md commands/results; final schema recheck at M9 |
| A32 / CLI-01 | PASS | autonavy/cli.py + capture/replay.py; tests/integration/test_replay.py::test_entrypoints_use_safe_cli_from_unrelated_cwd, ::test_finite_replay_budget_restart_and_packet_identity; tests/unit/test_foundations.py::test_preflight_conflicts_are_rejected_before_diagnostic_dispatch; evidence/M1.md commands/results and coordinator smoke below |
| A33 / OBSERVE-01 | NOT RUN | Implementation/validation pending |
| A34 / PERF-01 | NOT RUN | Implementation/validation pending |
| A35 / PERF-01 | NOT RUN | Implementation/validation pending |
| A36 / BUILD-01 | NOT RUN | Implementation/validation pending |
| A37 / BUILD-01 | NOT RUN | Implementation/validation pending |
| A38 / HANDOFF | NOT RUN | Implementation/validation pending |
| A39 / HANDOFF | NOT RUN | Implementation/validation pending |

## Preservation baseline

- `src` Git tree: 070c99be932097c428b3be83a635bb9f749b3283.
- Native extension Git blob: e34e40f0db6be26bdfc867c89e36b897c677acdf.
- Native SHA256: ABE3EF91491C5C53EDA3BC16C63843545942079DEA80E80C8A139671FBEDF721.
- Source master: 45fc36cc4d173fb1e46eac2dcd1be3338157c500.
- origin/master: c2f889336e5c656763ecac76ed54c960b36a666f.
- upstream/master: 69570b424a3b552b4d56ebca062cc412ad105521.
- Rechecked initial worktree: clean; HEAD unchanged. At final compare asset/native tree objects and branch refs; no screenshot capture is needed.
- M0 record-fix recheck executed: `git -C 'C:\Develop\game\WT\AutoNavy_WT' status --porcelain=v1 -uall` produced no output; `git -C 'C:\Develop\game\WT\AutoNavy_WT' rev-parse HEAD master origin/master upstream/master 'HEAD:src' 'HEAD:toolkit/way_search.cp311-win_amd64.pyd'` returned the recorded source/default refs and tree/blob identifiers above. `Get-FileHash toolkit/way_search.cp311-win_amd64.pyd -Algorithm SHA256` matched the recorded native hash in the v2 worktree. This confirms current M0 preservation, not a future final state.

## M1 foundations evidence

Code commit 43aa40e7f3485dda9de807448d3a5b742ebbffad. See [M1 test-first report](evidence/M1.md) for 66 focused and 107 regression passes (one known side-effecting policy test excluded), import guards, actual launcher calls and explicit later-milestone limitations.

Coordinator executed at that commit: `.venv\Scripts\python.exe -m autonavy --check-config --config configs/default.toml` => exit0; `.venv\Scripts\python.exe -m autonavy --dry-run --capture replay --fixture tests/fixtures/smoke --max-frames 120` => exit0, 3 synthetic frames, stopped. Frame budget caps the finite three-frame sequence; this is not a recorded battle or a performance measurement.


Environment package snapshot after the legacy baseline repair and M1: evidence/environment-after-M1.txt (`.venv\Scripts\python.exe -m pip freeze`). It records the actual local venv; it is not a new dependency requirement or a claim that hardware was tested.

M2-close/M3-active preservation recheck at987dc61: source status --porcelain=v1 -uall empty; source HEAD/master/origin/master/upstream/master unchanged at recorded identifiers. Target HEAD:src and native blob match baseline; native file SHA256 matches ABE3EF91491C5C53EDA3BC16C63843545942079DEA80E80C8A139671FBEDF721. No asset/native/source changes. Final M9 recheck still required.
