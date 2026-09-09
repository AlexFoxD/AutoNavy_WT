# M8a implementation report

## Scope and final state

Implemented only M8a in `C:/Develop/game/WT/AutoNavy_WT-v2`, branch `feature/v2-modernization`. Starting HEAD was `06b81deeeb4a68a8487855fd4575ff73c4e7c7aa`; accepted M7 production is `1b5ca7877330f2b4e35a6db8374a21b7c0d5b0f1`. Coordinator committed its shared records separately. Final worker HEAD is `efa5d445b4bacfec9848f098da3ff6475bef086e` (durable evidence); final measured/verified production code is `2fdc1cb0daa0542f8b93c956fc04a92e5e019902`.

The original checkout was not edited. No dependency pins, templates, native binary or route bytes changed. No device/camera/game/global hook/input/network telemetry was opened. No new dependency, driver, compiler or global setting was installed. No push, PR, merge, tag, release or M8b build was performed. Tests used fake/synthetic sources and injected displays. No subagents were spawned; coordinator arranges independent review.

Read `task-8a-brief.md` first, then complete parent `task-8-brief.md` including appended audits, SPEC global/CFG/OBSERVE/PERF constraints, actual M3/M5/M6/M7 code/tests/evidence. Applied installed planning/TDD/debugging/verification workflow under the already-approved design and existing isolated worktree. Concrete plan: `docs/v2/plans/M8a.md`, now checked off with execution refinements. Shared STATUS/PLAN/DECISIONS/VERIFICATION/REVIEW edits are coordinator-owned and were not staged by this worker.

## Owned changes and APIs

- `autonavy/metrics.py`: `Metrics(*, max_samples=512,max_series=32)`, `.observe(name,value)`, `.increment(name,count=1)`, `.snapshot()`. Both series cardinality and retained numeric deque samples are bounded. Snapshot count is lifetime; p50/p95/mean is the retained window. No images, packets, input resources or intent payloads are retained.
- `autonavy/diagnostics.py`: `FaultThrottle(interval_s,clock,max_keys=32).allow(key)`, bounded `exception_text(exc,limit=4096,context='')`, `runtime_logging(settings)` context manager, lazy native `Preview.show(image)/close()`. Rotating handlers default2MB+3 backups and close/remove on exit; a single log record may exceed the nominal threshold because rotation occurs between records. Traceback tails retain exception type/reason/device context with explicit truncation.
- `Application(...,metrics=None,display=None)` wires numeric vision/policy/new-frame-decision/idle/receive-age samples and throttled Navigation.last_error/preview faults into actual ticks. `per_frame=false` and `preview=false` remain defaults. Explicit per-frame logs identify frame/generation/backend/state/age/tick duration. Actual M3 debug images are displayed without re-copying/re-displaying cached overlays. Display closes last, after input and service cleanup.
- `InputController(...,metrics=None)` records `intent_to_dispatch_ns` from actual intent creation to dispatch start, plus successful dispatch counts. Guard/generation/ownership/emergency ordering remains.
- `ProcessCapture.statistics` exposes current-generation delivered, publication_gaps, idle_reads and failures. Same captured session flows into internal read; M7 `.diagnostic` deep-copy and requested/reported/delivered/source/window geometry contracts remain. Gaps are observed skipped IDs, not confirmed game/source drops.
- Normal read CaptureTimeout increments idle counts, not faults. Native errors preserve bounded traceback bytes: capture4096; planner511 in its original512-byte field. Existing TelemetryService fault throttle now emits bounded traceback text. CLI startup constructor errors are logged before runtime handlers close.
- `diagnostics.metrics_samples=512`, validated1..100000, added to actual config/default TOML.
- `scripts/benchmark_common.py`: finite summaries and JSON/CSV writing, protected asset/route output refusal, environment/code hashes/clock metadata.
- `scripts/benchmark_pipeline.py`: `run_benchmark(samples=20,warmups=3,seed=42,repetitions=3)`, paired interleaved legacy/v2 pixel arithmetic, full-surface correctness gate first, cold registry load+copy+all-edge preparation, new warm contexts, separate real menu and battle ticks.
- `scripts/benchmark_capture.py`: `run_benchmark(settings,duration_s=5,max_frames=100000)`, actual factory/backend selection, non-actuating read loop, finite frames/time, delivery gaps/idle/errors/read time/receive-age, negotiated versus delivered settings, parent-only CPU/memory and explicit unknown upstream/child/GPU/game latency/resources. CLI defaults replay; live selection implemented but NOT RUN.
- `ReplayCapture` needed no edit; actual finite packet IDs support capture report counters and its unavailable negotiated FPS remains null.
- Focused tests: `tests/unit/test_metrics.py`, `tests/unit/test_benchmarks.py`, `tests/integration/test_diagnostics_runtime.py`. Documentation: plan and `docs/v2/BENCHMARKS.md`.

## RED/GREEN and debugging evidence

All commands below ran in the v2 worktree with `.venv/Scripts/python.exe`. No timing performance assertions were added.

1. Initial diagnostics RED:
   `-m pytest tests/unit/test_metrics.py tests/integration/test_diagnostics_runtime.py -q --tb=short`
   Result `8 failed, 3 passed in0.85s`: missing Metrics/diagnostics modules, missing metrics_samples/display APIs, missing ProcessCapture.statistics, missing capture traceback text. The three existing invalid-config rejection cases passed before the new positive-valid-config assertions were added.
   GREEN same command: `11 passed in2.21s`.
2. Expanded affected regression:
   `-m pytest tests/unit/test_metrics.py tests/integration/test_diagnostics_runtime.py tests/unit/test_input.py tests/unit/test_navigation_planner.py tests/integration/test_capture_runtime.py tests/integration/test_battle_cycle.py tests/integration/test_replay.py tests/test_autonavy_entry.py -q --tb=short`
   Initial result `1 failed,172 passed in22.85s`. Existing `test_read_snapshot_is_one_generation_even_when_paused_at_first_attribute` found an introduced race: read wrapper captured `_session`, then internal read fetched `_session` again after a concurrent stop/restart. It returned a generation2 packet where the canceled original read must returnNone. Fix passes the single captured session into `_read(session,timeout)`, including metric attribution. Focused interleaving/diagnostics GREEN `14 passed in2.88s`; repeated affected command GREEN `173 passed in22.67s`. This was a real regression fixed without weakening the existing test.
3. Benchmark RED:
   `-m pytest tests/unit/test_benchmarks.py -q --tb=short`
   Result `7 failed in0.18s` (missing benchmark APIs). First implementation result `1 failed,6 passed in1.21s`: API capture report still contained a WindowsPath although CLI conversion hid it; fixed JSON-safe requested paths at report construction. Focused benchmark/metrics/diagnostics GREEN `20 passed in3.05s` (then `20 passed in2.98s` after formatting).
4. Coordinator-requested truncation/context RED:
   `-m pytest tests/unit/test_metrics.py::test_long_exception_preserves_type_tail_and_device_context -q --tb=short`
   `1 failed`: missing context keyword. Implemented bounded context/type prefix plus final traceback/exception tail. Existing huge-message assertion and new511-byte test pass. Capture context names selected backend/device/output; no buffer sizes enlarged.
5. Telemetry traceback RED:
   `-m pytest tests/unit/test_metrics.py::test_telemetry_fault_has_bounded_traceback_and_keeps_existing_throttle -q --tb=short`
   `1 failed in0.08s`: fault lacked Traceback. Reused bounded formatter while preserving existing throttle. Expanded focused/telemetry command:
   `-m pytest tests/unit/test_metrics.py tests/integration/test_diagnostics_runtime.py tests/unit/test_benchmarks.py tests/unit/test_telemetry.py tests/integration/test_telemetry_runtime.py -q --tb=short`
   GREEN `66 passed in6.05s`.
6. Clock/per-frame RED:
   `-m pytest tests/unit/test_benchmarks.py::test_environment_discloses_monotonic_clock_resolution tests/integration/test_diagnostics_runtime.py::test_explicit_per_frame_logging_connects_publication_and_tick_timing -q --tb=short`
   `2 failed in0.74s`: missing clock provenance and tick_ns linkage. GREEN focused diagnostics/benchmark suite `27 passed in3.52s`.
7. Self-review startup-file logging RED:
   `-m pytest tests/integration/test_diagnostics_runtime.py::test_cli_constructor_failure_is_logged_before_handlers_close -q --tb=short`
   `1 failed in0.24s`: Application constructor exception was logged only after runtime handlers closed. Context manager now logs exception before close; GREEN focused diagnostics/benchmark suite `28 passed in3.69s`.
8. Separate battle workload RED:
   `-m pytest tests/unit/test_benchmarks.py::test_battle_benchmark_runs_real_vision_policy_and_recording_input_without_native -q --tb=short`
   `1 failed in0.89s`: missing battle_decision. Implemented valid injected player/metadata snapshots, real VisionPipeline/ammo baseline, real BattlePolicy/Navigation(no map/no zones), RecordingBackend. Test forbids PlanningService.submit and asserts actual successful dispatches and IN_BATTLE state. Benchmark suite GREEN `11 passed in2.09s`.
9. Narrow lint initially found only new-file formatting/unused-import issues. Scoped Ruff format and the unused import removal resolved them. Final:
   `-m ruff check autonavy/metrics.py autonavy/diagnostics.py scripts/benchmark_common.py scripts/benchmark_pipeline.py scripts/benchmark_capture.py tests/unit/test_metrics.py tests/unit/test_benchmarks.py tests/integration/test_diagnostics_runtime.py --output-format concise`
   `All checks passed!`; `git diff --check` exit0. No repository-wide formatting.

## Executed measurements and artifacts

Final measurement code is `2fdc1cb0daa0542f8b93c956fc04a92e5e019902`; reports also contain code SHA-256 hashes and documentation-only working-tree status. Runtime pins unchanged: CPython3.11.9 x64, NumPy1.26.0, OpenCV4.8.0.74, Pillow11.1.0, DXcam0.0.5 metadata. Windows AMD64 Family25 Model117 Stepping2, 16 OpenCV threads.

Executed pipeline commands (all exit0):

```powershell
.venv/Scripts/python.exe scripts/benchmark_pipeline.py --samples 20 --warmups 3 --repetitions 3 --seed 42 --output logs/v2/benchmarks/pipeline-initial
.venv/Scripts/python.exe scripts/benchmark_pipeline.py --samples 20 --warmups 3 --repetitions 3 --seed 42 --output logs/v2/benchmarks/pipeline-final
.venv/Scripts/python.exe scripts/benchmark_pipeline.py --samples 20 --warmups 3 --repetitions 3 --seed 42 --output logs/v2/benchmarks/pipeline-reviewed
.venv/Scripts/python.exe scripts/benchmark_pipeline.py --samples 20 --warmups 3 --repetitions 3 --seed 42 --output logs/v2/benchmarks/pipeline-menu-battle
```

Every base has `.json` and `.csv`, kept under ignored logs/v2. Initial/final runs established measurements; reviewed added clock provenance; menu-battle added coordinator-requested separate battle characterization without deleting the slow menu case. A benchmark JSON contains all raw samples, n/warmups/repetition/p50/p95/mean/throughput, fixture/asset hashes and environment. Cold registry measurement really reads/decodes45 assets, copies images and prepares all edges; OS disk cache can be warm. No cached no-work decision ticks are timed.

Final normalized full aim score-surface max error `3.919936716556549e-6` within `6e-6`, absolute tolerance withrtol0; raw aim has4 channels, location `(170,100)` within ROI, frame top-left `(540,300)`. Exact mask/preprocessing equality gates passed before timing. Legacy arithmetic is from source45fc36c, extracted safely without legacy module import.

Final ranges across3 repetition summaries, n20 each,3 warmups each (milliseconds):

| Stage | Legacy p50 | V2 p50 | V2 p95 | V2/legacy median ratio |
| --- | --- | --- | --- | --- |
| Preprocessing |4.2789–5.4156|3.1568–4.7867|4.0309–6.1009|0.738–0.903|
| Prepared matching |9.8414–9.9749|2.2201–2.3110|2.5430–2.7251|0.223–0.232|
| Fire HSV/mask |0.9268–1.0438|0.1890–0.2069|0.2157–0.3777|0.198–0.204|
| Heading mask |0.0205–0.0226|0.0221–0.0244|0.0233–0.0278|1.076–1.095|
| Cold registry read/decode/copy/edges |not compared|13.0516–14.4562|15.5555–16.8143|not compared|
| Real menu decision |not compared|376.0003–393.7699|399.9318–441.1682|not compared|
| Real battle decision |not compared|166.7150–169.5617|174.5259–189.5402|not compared|

No repeated comparable median regression above10% was triggered in any executed report. Heading's1.55–2.05us/7.6–9.5% slowdown remains visible; bounded FrameContext validation/bookkeeping adds overhead at this tiny ROI where removing1x1 morphology has negligible savings. It is not an acceleration, and no safety checks were removed. Menu selects24 detectors; battle16 includingdegree. Real vision accounts for99.96%/99.93% of mean tick including warmups; policy means0.077ms/0.066ms. Each workload processes69 fresh publications and69 recording dispatches. Packet ownership copy/startup and injected telemetry publication are outside timing; vision, real policy, freshness/input ownership and metrics are inside. Native planning, network, game and source-to-input latency are not included. Both workloads exceed the configured30Hz33.3ms target. No whole-project speedup or30Hz claim is made.

Capture fixture creation actually used this local Python data (not a screenshot):

```python
fixture = Path('logs/v2/benchmarks/replay-600')
fixture.mkdir(parents=True, exist_ok=True)
manifest = dict(schema_version=1, synthetic=True, pixel_format='BGR', geometry_id='synthetic-benchmark',
                width=1280, height=720, frames=[dict(color=[i % 256, (i*17) % 256, (i*31) % 256]) for i in range(600)])
(fixture/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
```

Manifest SHA256 `9c2f0067eb19be77945b1a9f600718f0741e0f3186a20cbee476eef9062a9124`.

Executed capture commands (exit0, replay ONLY):

```powershell
.venv/Scripts/python.exe scripts/benchmark_capture.py --backend replay --fixture logs/v2/benchmarks/replay-600 --duration 5 --max-frames 600 --output logs/v2/benchmarks/capture-replay
.venv/Scripts/python.exe scripts/benchmark_capture.py --backend replay --fixture logs/v2/benchmarks/replay-600 --duration 5 --max-frames 600 --output logs/v2/benchmarks/capture-reviewed
```

Final JSON/CSV: `logs/v2/benchmarks/capture-reviewed.{json,csv}`.600 publications,2.0635314s collection,290.7636879 publications/s, zero gaps/idle/failures. Unpaced synthetic replay, requestedfps60/reportfpsnull/delivered1280x720BGR; not a live/backend ranking. Capture readp503.17265ms,p953.956715ms. Receive-agep500,p9516ms: **GetTickCount64 resolution15.625ms, zero does not prove zero latency**. perf_counter usesQPC with reported100ns resolution. CPU2.03125s/98.4356% onecore, postcleanup parent workingset52170752bytes/49.75MiB. Isolated child memory/CPU, GPU/game/presentation/source latency unknown; replay has no child and no input/decision stage. Actual backend-selectable code was tested with injected factories; no DXcam/OBS/webcam/game was opened.

Safe smoke commands (exit0):

```powershell
.venv/Scripts/python.exe -m autonavy --check-config --config configs/default.toml > logs/v2/benchmarks/check-config.txt
.venv/Scripts/python.exe -m autonavy --dry-run --capture replay --fixture tests/fixtures/smoke --max-frames 3 > logs/v2/benchmarks/replay-smoke.txt
```

Actual replay finished3 frames/stopped and wrote rotating `logs/v2/autonavy.log` with resolved settings, states and bounded runtime summary. Tests separately prove check-config does not create a log directory, preview injection receives M3 images, and default per-frame output is absent.

## Self-review and final regression

Reviewed actual runtime tick/input/capture integration; bounds/history/cardinality; no image/text saving; default-off preview/per-frame logs; fault throttling and long-error context/truncation; original capture/planner IPC limits; exact cleanup ordering; source/session/geometry/freshness guards; paired correctness/ROI/channel math; cold versus warm boundary; fresh menu/battle work; finite capture reports; resource and source-clock scope; protected outputs; CLI log handler lifecycle. Two implementation findings (session double-read race and constructor traceback loss) were reproduced and fixed with tests, detailed above. No unresolved self-review defect remains. Independently reviewing the change is coordinator's next gate.

`git diff --exit-code 45fc36c -- src path.json toolkit/way_search.cp311-win_amd64.pyd` exit0 confirms protected tracked asset/route/native bytes unchanged. Narrow Ruff and `git diff --check` passed.

After self-review and final production changes, executed exactly one full permitted regression:

```powershell
.venv/Scripts/python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short
```

Result **440 passed,1 deselected in62.34s** (exit0), output `logs/v2/benchmarks/m8a-full-tests.txt`. The known launcher policy exclusion remains until M8b fixes it. No full rerun was needed after documentation-only changes.

## Commits and next step

- `e6fc744` feat: add bounded runtime metrics and explicit diagnostics
- `4c66c8b` fix: preserve bounded fault tracebacks and device context
- `7d7b1b0` feat: add finite offline pipeline and capture benchmarks
- `ffb9a4b` fix: disclose clock resolution and connect frame logs to timings
- `e1cb620` fix: log startup exceptions before closing runtime handlers
- `2fdc1cb0daa0542f8b93c956fc04a92e5e019902` test: characterize separate real menu and battle decision workloads
- `7d62733dc7200ff5b3f715963d20310a17ccb5aa` docs: record measured M8a results and runtime diagnostic limits

Ready for coordinator-arranged independent M8a review. Keep branch/worktree; do not merge/push/discard. Launcher/dependency/CI/build/preflight and README/MIGRATION remain M8b and are not claimed complete. Live hardware remains NOT RUN; current synthetic decision throughput is below configured30Hz, and source/render-to-input latency remains unknown.


## Durable evidence follow-up

At coordinator request, copied all12 executed pipeline/capture JSON/CSV artifacts, the replay600 manifest and full regression output into `docs/v2/evidence/benchmarks` (14 files). Every destination SHA-256 was checked equal to its original ignored log artifact before commit. BENCHMARKS links the final reports and a replay command using the tracked fixture. Earlier reports remain to preserve every recorded repetition and environment. Historical paths/code hashes inside JSON were not rewritten. Documentation/evidence-only commit `efa5d445b4bacfec9848f098da3ff6475bef086e` is final HEAD; measured/verified production remains `2fdc1cb0daa0542f8b93c956fc04a92e5e019902`. No test rerun was needed for byte-identical evidence copies/documentation. Report path is unchanged. Final working-tree changes belong only to coordinator (`docs/v2/STATUS.md`, `docs/v2/VERIFICATION.md`).
