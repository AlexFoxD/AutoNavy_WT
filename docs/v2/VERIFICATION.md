# Verification evidence

Environment: Windows, project-local CPython 3.11 x64. Source 45fc36cc4d173fb1e46eac2dcd1be3338157c500. No live input or game startup is authorized for verification.

Current stage: M0-M7 and M8a independently reviewed; M8b launcher/build work next. PASS rows identify their concrete milestone scope and evidence. Downstream acceptance remains NOT RUN until implemented and verified. A01 requires another preservation check at final handoff.

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
| A08 / CAP-03 | PASS | M2/M5/M7 source generation/start/stop/cleanup races and fake native hangs tested through real supervisor and Application. M7 tests cover confirmed native open/read/release hangs, cancel/restart and input release before parent termination waits. Native driver recovery remains hardware NOT RUN. evidence/M2.md and evidence/M7.md. |
| A09 / VISION-01 | PASS | M3 FrameContext/TemplateRegistry raw color Canny outputs feed one-channel match_edges; call-count/cache-version/invalidation tests include alpha-only aim asset. evidence/M3.md:201regression pass1excluded, previewfix36covering pass. |
| A10 / VISION-01 | PASS | M3 real-asset synthetic positive/negative and malformed/constant/oversize/nonfinite tests; frame/desktop ROI mapping and configured-profile gates; required assets validated before capture construction. evidence/M3.md. Live accuracy NOT RUN. |
| A11 / VISION-02 | PASS | M3 test_vision.py validates pixelwise cropped HSV and actual fire/lock/collision ROI mask-Canny behavior; separates neighborhood boundary effects from HSV equivalence. evidence/M3.md. |
| A12 / VISION-02/03 | PASS | M0/M3 no-op morphology, empty/degenerate heading, debug-copy on/off equality;713a507 adds independently throttled copy/draw with injectedclock and deadline tests (36covering passed). evidence/M3.md. |
| A13 / GEOM-01 | PASS | M2/M7 GeometrySnapshot and source_geometry pure tests cover translation, negative origins, arbitrary content offsets, scale round trips and bounds. Actual full-detector parity on asymmetric OBS canvas includes ammo/heading/clicks and content-centered aim. evidence/M7.md:129 covering and411 full passed1excluded. |
| A14 / GEOM-01 | PASS | M5/M7 LiveWindowGuard and InputController compare current source/window/DPI/profile/calibration mapping before physical-marked fake dispatch. test_obs_runtime.py queued intents rejected after movement/DPI/source/scaling/content changes; requested/reported/delivered diagnostics preserve distinctions. evidence/M7.md. Physical calibration NOT RUN. |
| A15 / TEL-01 | PASS | M4 real TelemetryService/parser with fake Session covers HTTP/status/JSON/schema/player/nonfinite/zero-heading/empty-zones/stale/recovery; evidence/M4.md full241pass1excluded, focusedmetadatafix41pass. No live HTTP executed. |
| A16 / TEL-01 | PASS | M4 serial worker/no queue, monotonic per-component timestamps, TTL at consumption, locally inferred map/recovery generations.0c44df0 atomically invalidates published data on metadata failure while next request blocks; reviewer4case repro passed. evidence/M4.md. |
| A17 / TEL-01 | PASS | Application owns TelemetryService/OfflineTelemetry; info.py and toolkit/map.py require explicit snapshot source and issue no HTTP. Separate bounded metadata/image cache in memory; no asset writes. evidence/M4.md and test_telemetry_runtime.py. M5/M6 consumer integration and final caller audit remain required. |
| A18 / LIFE-01 | PASS | M2/M5 Application shared cleanup; test_battle_cycle.py::test_actual_run_input_cleanup_on_startup_worker_and_observation_errors and ::test_pause_then_stop_signals_never_dispatch_again. evidence/M5.md:326 regression passed1excluded at20142e0. |
| A19 / LIFE-01 | PASS | M5 input.close precedes capture/telemetry cleanup; ::test_paused_stop_and_cleanup_release_before_capture_or_telemetry_errors and test_input.py::test_legacy_input_and_thread_modules_have_no_raw_hardware_or_kill_paths. evidence/M5.md; remaining legacy navigation retired in M6. |
| A20 / INPUT-01 | PASS | M5 InputController and WindowsBackend track uncertain holds, attempt all releases, retain failures for retry and neutralize queried vJoy axes before relinquish. test_input.py release failure, owned vJoy and close retry cases; evidence/M5.md. Physical hardware NOT RUN. |
| A21 / INPUT-01 | PASS | M5 test_input.py signed wheel/zero no-op/focus/emergency and fake Windows transport tests; test_battle_cycle.py current prerequisite and delayed guard tests. evidence/M5.md. No real input executed. |
| A22 / INPUT-01/02 | PASS | M5 owner generations/global epochs and bounded coalescing; test_input.py::test_mode_round_trip_invalidates_issued_but_not_yet_submitted_intents and four review_pointer regressions. Scoped re-review20142e0 PASS; evidence/M5.md. |
| A23 / INPUT-02 | PASS | M5 SequenceScheduler and real policy fake-clock recovery/UI cycles; test_battle_cycle.py::test_review_persistent_start_retries_keep_original_queue_deadline and ::test_review_cancelled_recovery_deadline_never_delays_fresh_menu; bounded pending/history in test_input.py. evidence/M5.md. |
| A24 / APP-01 | PASS | M5 ::test_full_scripted_cycle_uses_real_application_run executes actual Application/Policy/Input with synthetic capture double, observations and immutable telemetry through full states. 168 covering tests passed; evidence/M5.md. This is a scripted offline scenario, not recorded gameplay. |
| A25 / APP-01 | NOT RUN | Implementation/validation pending |
| A26 / NAV-01 | PASS | M6 RouteCursor/Navigation/PlanningService actual runtime; test_navigation.py route immutability/intersections/order and test_navigation_runtime.py dense-turn/off-route target tracking regressions. c4c3810 scoped review PASS;86covering tests. Bounded retries, stale results/deviation and arrival covered. evidence/M6.md. |
| A27 / NAV-01 | PASS | M6 native.py lazy exact ABI adapter and supervised planner real production caller; tests/unit/test_navigation_planner.py::test_native_adapter_and_supervised_encoded_route_on_exact_supported_host passed onCPython3.11.9 Windows x64. Four8x8 cases and encoded128grid route17points via actual native child. Pure tests inject fake adapter. evidence/M6.md. |
| A28 / CTRL-01 | PASS | M6 separate PID states with units/wrapped errors/dt/integral/output bounds and mode/target/waypoint/session/stop resets. test_navigation.py and test_navigation_runtime.py plus source signs characterized in AUDIT; full371pass1excluded then86covering route fix. Physical sign calibration NOT RUN. evidence/M6.md. |
| A29 / CAP-02 | PASS | M7 actual OBSSource selected inside ProcessCapture; test_obs.py and test_obs_runtime.py fake VideoCapture cover exact API/index, failed open/read, malformed dtype/channels/size, partial cleanup, stale repeats, reopen and source generation.21 final OBS tests passed; evidence/M7.md. Hardware NOT RUN. |
| A30 / CAP-02/03 | PASS | M7 factory/import and exact selected-index/API tests; no discovery or alternate-device fallback. OpenCV core import does not open VideoCapture; source construction/start ownership explicit. Device friendly-name identity remains operator trust and is labeled false in diagnostics. evidence/M7.md. |
| A31 / CFG-01 | PASS | autonavy/config.py + configs/default.toml; tests/unit/test_foundations.py::test_config_precedence_and_default_resource_resolution, ::test_invalid_config_is_rejected_before_startup, ::test_cli_input_requires_explicit_flag_and_replay_rejects_it; evidence/M1.md commands/results; final schema recheck at M9 |
| A32 / CLI-01 | PASS | autonavy/cli.py + capture/replay.py; tests/integration/test_replay.py::test_entrypoints_use_safe_cli_from_unrelated_cwd, ::test_finite_replay_budget_restart_and_packet_identity; tests/unit/test_foundations.py::test_preflight_conflicts_are_rejected_before_diagnostic_dispatch; evidence/M1.md commands/results and coordinator smoke below |
| A33 / OBSERVE-01 | PASS | M8a metrics.py/diagnostics.py integrated into actual Application, InputController, ProcessCapture and planner/telemetry faults; test_metrics.py and test_diagnostics_runtime.py cover bounds, throttle, explicit preview and startup logging. 440 full tests passed, 1 launcher exclusion. Independent review PASS; evidence/M8a.md. |
| A34 / PERF-01 | PASS | M8a benchmark_pipeline.py executes correctness-gated paired cold/warm arithmetic and separate fresh menu/battle ticks. Repeated measured JSON/CSV and raw samples in evidence/benchmarks; reviewer independently recomputed summaries. BENCHMARKS.md records exact scope and the decision-rate shortfall. |
| A35 / PERF-01 | PASS | M8a benchmark_capture.py has real backend-selectable non-actuating capture and bounded duration/frame budget. Executed replay only: 600 publications, 290.76/s, receive p50 0/p95 16ms with 15.625ms clock resolution, upstream/child scope explicitly unknown. Retain DXcam default and 0.0.5 pin without a live ranking; BENCHMARKS.md and evidence/DXcam-upgrade-assessment.md. Live comparison NOT RUN. |
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

M5 current code20142e0 independently reviewed PASS. Exact new16/covering168/full326pass1excluded commands and RED evidence in evidence/M5.md. Source shim config/replay smoke at12c6379 exited0 (3synthetic frames). A14 awaits complete OBS geometry integration; A25 awaits launcher M8. These rows intentionally remain NOT RUN for full requirement scope.

M6 accepted code c4c3810. Native algorithm/route validation is offline synthetic, not real-battle navigability or physical steering calibration. Narrow native planner isolation and OS failure limits in DECISIONS/evidence/M6.md. Existing source refs/assets remain protected; final M9 preservation check required.

M7-active preservation recheck: original checkout `git status --porcelain=v1 -uall` empty; source HEAD/master45fc36cc4d173fb1e46eac2dcd1be3338157c500, origin/master c2f889336e5c656763ecac76ed54c960b36a666f, upstream/master69570b424a3b552b4d56ebca062cc412ad105521 unchanged. Both HEAD asset trees070c99be932097c428b3be83a635bb9f749b3283 and native blobs e34e40f0db6be26bdfc867c89e36b897c677acdf match baseline; target working native SHA256 ABE3EF91491C5C53EDA3BC16C63843545942079DEA80E80C8A139671FBEDF721 matches. `git diff HEAD --exit-code -- src toolkit/way_search.cp311-win_amd64.pyd` exited0. No source/asset/native edits; final M9 recheck still required.

## Manual hardware acceptance — NOT RUN

The following checks are instructions for an operator after delivery, not commands executed during this task. Current automation verification uses synthetic pixels, fake observations/devices and the real native pathfinder only.

1. **DXcam capture and geometry.** Use a compatible Windows x64 CPython3.11 environment, the bundled Simplified Chinese game-template locale, a native1280x720 client, UI100% and DPI96. Run `.venv\Scripts\python.exe -m autonavy --dry-run --capture dxcam --config configs/default.toml`. Confirm requested/delivered settings and client/content mapping in diagnostics. Check window translation, negative desktop origins where available, minimize/restore and source recovery. Unsupported calibration must inhibit actionable recognition/input. Stop dry-run with Ctrl+C; F8/F9 hooks are not installed in this mode.
2. **OBS capture and calibration.** The operator starts OBS Virtual Camera and manually verifies its configured device index/API and selected Program/Preview/Scene/Source. Prepare an explicit configuration matching delivered canvas size and the unscaled game-content rectangle, then run the same dry-run command with `--capture obs` and that configuration. Verify color, dimensions, asymmetric letterbox offsets and client mapping. API name is not proof of friendly device identity. No automatic alternate-device fallback is implemented. Changing the OBS composition requires renewed calibration.
3. **Physical input and safety.** Only after the operator accepts capture/profile/game-policy risks, the documented live commands add `--enable-input` instead of `--dry-run`. Enabling input permits automatic UI and game control, including queuing. Check F9 pause/resume, F8 stop, focus loss, stale capture/telemetry and every held key/button/axis returning to neutral. Verify the physical steering sign and actual vJoy axis/range configuration; offline source-arithmetic tests do not prove game bindings. Do not treat a purchase-dialog pause as permission for automatic purchases.
4. **Device failures.** Observe stop/restart and input neutralization with real capture/telemetry interruptions in an appropriate controlled setting. Mock native hangs prove supervisor behavior on this host, not driver recovery after forced process termination. Verify logs identify the device/source and preserve useful failure context.
5. **Performance and latency.** Run the implemented capture benchmark separately for equal content resolution/profile/preview settings. Report delivered publications and receive-age as such. OBS buffering, game render time, GPU/game impact and full render-to-input latency remain unknown unless measured with a trustworthy clock relationship or external visual-counter method. Offline arithmetic measurements cannot rank live backends.

Exact installer, packaged executable, benchmark arguments and operation examples are finalized by M8b in README/MIGRATION. Hardware acceptance results remain NOT RUN until an operator actually performs and records them.

M8a-review preservation check at a7584d3: both worktrees have empty status output; original HEAD/master, origin/master and upstream/master match the recorded baseline. Target src tree and native blob match the original identifiers; native SHA256 matches ABE3EF91491C5C53EDA3BC16C63843545942079DEA80E80C8A139671FBEDF721. The target working diff for src, path.json and the native extension is empty. This is a current preservation check; final M9 check remains required.
