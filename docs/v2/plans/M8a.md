# M8a Benchmarks and Runtime Diagnostics Implementation Plan

> **For agentic workers:** Execute inline with the installed executing-plans skill, TDD and verification-before-completion. Coordinator arranges independent review. No nested agents.

**Goal:** Deliver reproducible finite offline measurements and bounded observability on actual runtime paths (A33–A35, CFG-01, PERF-01).

**Architecture:** A bounded Metrics collector stores numeric samples and counters; Application and InputController supply real stage/dispatch timestamps. Capture reports delivered publications and observed transport gaps. Explicit CLI runtime logging owns rotating handlers, while preview consumes only M3 debug images. Standalone benchmarks use safe imports and deterministic pixel inputs, gate correctness before timing, and write JSON/CSV under ignored logs/v2.

**Tech Stack:** Existing CPython 3.11, NumPy/OpenCV pins, pytest, Python standard library. No new packages.

**Spec:** docs/v2/SPEC.md and .superpowers/sdd/PLAN/task-8{,a}-brief.md, including all audit appendices.

## Global constraints

- Work only in C:/Develop/game/WT/AutoNavy_WT-v2 on feature/v2-modernization; source checkout stays untouched.
- No live devices, hooks, input, telemetry networking, driver/compiler/global changes, publishing or M8b packaging work.
- Preserve raw alpha aim template channels and normalized matching tolerance 6e-6; do not edit assets/native bytes.
- Preserve input release before service waits, source generations, freshness, geometry, M7 diagnostics and safe inert configuration/replay.
- Preview/per-frame logging default off. Never write screenshots/input text. Metrics and rotating logs remain bounded.
- No timing assertions or unequal speedup claims; investigate repeated comparable median regression above 10%.
- Coordinator owns shared STATUS/PLAN/DECISIONS/VERIFICATION/REVIEW and evidence copies. Stage only owned files.

## Task 1: Bounded runtime diagnostics

**Files:** Create autonavy/metrics.py, autonavy/diagnostics.py, tests/unit/test_metrics.py, tests/integration/test_diagnostics_runtime.py. Modify autonavy/app.py, input/controller.py, capture/process.py, navigation/planner.py, telemetry.py, cli.py, config.py, configs/default.toml.

**Interfaces:** Metrics(max_samples=512,max_series=32).observe(name,value), increment(name,count=1), snapshot(); FaultThrottle(interval_s,clock,max_keys=32).allow(key); runtime_logging(settings) context manager; Preview.show(image)/close(); Application(...,metrics=None,display=None); ProcessCapture.statistics dictionary.

- [x] Write tests asserting deque bounds/counts/finite values/cardinality and detached snapshots; fault interval and bounded keys; log rotation/handler removal/traceback; default disabled preview and injected display identity; actual tick timings/dispatch samples; CaptureTimeout idle and capture gap counters.
```python
m = Metrics(max_samples=2, max_series=2)
for value in (1, 2, 3): m.observe('vision_ns', value)
assert m.snapshot()['samples']['vision_ns']['retained'] == 2
assert m.snapshot()['samples']['vision_ns']['count'] == 3
```
- [x] RED: `.venv/Scripts/python.exe -m pytest tests/unit/test_metrics.py tests/integration/test_diagnostics_runtime.py -q --tb=short` fails on missing APIs.
- [x] Implement bounded deques and fixed-bound series with summaries calculated only on snapshot. Configure rotating file + stream logs only at explicit run; close/remove own handlers. Measure vision/policy/full decision and idle separately; dispatch age from intent creation. Count actual delivered publications/gaps. Emit throttled navigation faults and preserve bounded traceback text crossing native boundaries. Consume M3 debug image directly through lazy preview display.
- [x] GREEN with focused tests plus affected app/input/capture/navigation tests; record exact commands/results.
- [x] Commit scoped runtime changes and tests after verification.

## Task 2: Finite comparable pipeline benchmark

**Files:** Create scripts/benchmark_pipeline.py, scripts/benchmark_common.py, tests/unit/test_benchmarks.py.

**Interfaces:** run_benchmark(samples,warmups,seed,repetitions) -> schema-versioned report; measure callable using perf_counter_ns, paired interleaving by repetition. write_report(report,output) -> JSON plus CSV paths. Environment includes Python/platform/dependency versions/OpenCV threads/commit. Each series includes finite n/warmups/p50/p95/mean/throughput and scope.

- [x] Add schema/correctness/finite count tests and structural Canny/match tests without speed assertions.
```python
report = run_benchmark(samples=1, warmups=0, seed=42, repetitions=1)
assert report['correctness']['passed']
assert all(row['n'] == 1 for row in report['timings'])
assert report['correctness']['aim_channels'] == 4
```
- [x] RED: `.venv/Scripts/python.exe -m pytest tests/unit/test_benchmarks.py -q --tb=short` fails on missing script APIs.
- [x] Implement narrowly extracted source45fc36c color-Canny edge expansion, normalized matching and full-HSV/ROI masking versus new FrameContext/registry/matcher arithmetic on identical deterministic pixels. Gate full surfaces/location/masks before timings. Cold TemplateRegistry.from_settings is separate. Warm per-frame uses fresh contexts, cached static template only. Actual offline Application.tick receives fresh supported-geometry packets and OfflineTelemetry/RecordingBackend; report independently, without legacy whole-stage speedup.
- [x] GREEN schema/structural checks; execute repeated benchmark measurements and investigate flagged median regressions before interpreting results.

## Task 3: Backend-selectable non-actuating capture benchmark

**Files:** Create scripts/benchmark_capture.py; extend tests/unit/test_benchmarks.py and focused capture runtime tests.

**Interfaces:** run_benchmark(settings,duration_s,max_frames) -> report. CLI defaults replay, supports explicit dxcam/obs, validates settings, forces input off and preview off. Factory uses actual backend path. Finite duration and frame count; source startup/cleanup separated from collection.

- [x] Add finite replay schema tests, unknown latency/resource-scope assertions, backend factory wiring with injected fake only and capture timeout classification.
- [x] RED then implement using actual capture factory/read/counters, receive-to-consume measurements, parent process_time and available platform process memory. Source/render latency, presentation rate and unavailable child/GPU/game metrics stay null with reasons. No input/backend owner is constructed.
- [x] GREEN and execute only replay mode; write JSON/CSV under logs/v2/benchmarks.

## Task 4: Self-review, full permitted regression, evidence and commit

**Files:** docs/v2/BENCHMARKS.md; .superpowers/sdd/PLAN/task-8a-report.md; this plan.

- [x] Review scopes, bounds, inert imports, exception paths, cleanup ordering, comparable timing and exact executed artifact provenance. Run focused regressions for findings.
- [x] Execute `.venv/Scripts/python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short` once after self-review. Launcher exclusion remains M8b-owned.
- [x] Document exact commands, RED/GREEN, counts, benchmark medians/p95, honest limitations, APIs and commit SHAs. No live backend ranking.
- [x] Scoped local commits; retain branch/worktree for independent review and M8b.


## Execution notes and refinements

- Inline implementation used the existing approved v2 worktree; coordinator retains independent review ownership.
- ReplayCapture needed no production change: its finite IDs/packets drive actual benchmark delivery counts; unavailable negotiated settings remain null. Native ProcessCapture exposes its actual per-generation counters.
- Added bounded traceback text to the existing throttled TelemetryService fault path. Native planner keeps its original 512-byte IPC field, with at most511 bytes and an explicit truncation marker; capture stays4096 bytes. Preserve exception type/reason and selected-device context.
- Existing capture interleaving regression caught an introduced wrapper race. The implementation now passes the one captured session to the internal read method; no second session lookup can cross a restart boundary.
- Self-review caught startup constructor exceptions escaping the rotating handler context. A failing CLI test demonstrated the missing file traceback, then logging was moved before handler cleanup.
- Added clock implementation/resolution metadata and explicit per-frame tick timing. GetTickCount64 resolution explains zero/quantized ages; it is not proof of zero latency.
- Coordinator requested a distinct real battle workload after observing slow menu decisions. Both use fresh supported-profile packets, real vision/policy/recording input; battle injects valid telemetry without maps/native planning. Actual states and selected detector names are asserted/reported.
- Final focused diagnostic/benchmark tests and narrow Ruff checks passed. One full permitted regression:440 passed,1 deselected in62.34s. Exact commands, measurements, commit SHAs and limitations are in the task report and BENCHMARKS.md.
- No repeated comparable median regression over10% was observed across executed runs. Heading's smaller slowdown remains documented. Menu and battle decision times exceed the configured30Hz period; no whole-project speedup/FPS claim is made.

- Coordinator requested durable raw measurement evidence; all executed JSON/CSV variants, the synthetic600-frame manifest and full regression text are copied byte-for-byte into tracked docs/v2/evidence/benchmarks, with SHA-256 equality checks. Generated runtime outputs still default to ignored logs/v2.
