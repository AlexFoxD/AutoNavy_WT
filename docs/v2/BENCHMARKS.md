# M8a benchmark measurements and runtime diagnostics

M8a measures deterministic offline work on the existing pinned environment. These measurements do not establish live game FPS or source-to-input latency. DXcam remains the default; DXcam and OBS hardware runs are **NOT RUN**.

## Reproduce safely

Run from the v2 worktree with its existing environment:

```powershell
.venv/Scripts/python.exe scripts/benchmark_pipeline.py --samples 20 --warmups 3 --repetitions 3 --seed 42 --output logs/v2/benchmarks/pipeline-menu-battle
.venv/Scripts/python.exe scripts/benchmark_capture.py --backend replay --fixture tests/fixtures/smoke --duration 5 --max-frames 3 --output logs/v2/benchmarks/capture-smoke
```

Both scripts also support `python -m scripts.benchmark_pipeline` / `python -m scripts.benchmark_capture`. Outputs are JSON detail (including raw timing samples) and a timing CSV. Default output is under ignored `logs/v2/benchmarks`; output writers reject `src` and the route `path.json`. No screenshot or input text is saved. Asset hashes are hashes of decoded pixels; environment provenance records code-file hashes, Git HEAD/status, platform, Python, package versions, OpenCV thread count and monotonic/performance clock resolution.

The capture script accepts explicit `--backend dxcam` or `--backend obs`, `--config`, `--duration`, `--max-frames` and `--output`; it constructs the actual capture factory/backend and never constructs an input controller or telemetry service. The native modes are delivered for separately authorized manual measurement and were not executed here. Requested capture settings, available backend-reported negotiation and actual delivered shape/format are separate fields. Repeated/unique rendered FPS cannot be inferred from publication IDs.

## Measurement boundaries and correctness

Legacy computations are narrow safe extractions from source `45fc36c`: `toolkit/scn.py:match_img`, `firesystem.py:fire_control.lock_and_fire`, and `toolkit/deg_cal.py:get_deg`. The scripts do not import those legacy modules. Identical seeded pixels, parameters and ROI boundaries feed each pair. Ordering alternates within every paired sample to reduce systematic order bias. Correctness gates run before all timings and check exact masks/edges, the full normalized aim score surface and expected match location. `src/cir.png` retains all four raw channels; converting its alpha-only shape to BGR would invalidate the comparison. Absolute score tolerance is `6e-6` with zero relative tolerance.

The 1280x720 BGR fixture contains seed-42 uint8 noise, an alpha-derived green aim stencil and a green heading triangle. It is deliberately synthetic and is not a recording of a battle. Preparation measures full-frame color Canny plus the start template; legacy recomputes/expands both to BGRA, while v2 prepares a fresh frame context and reuses the warmed static template. Matching measures prepared fire-ROI/aim edges: expanded BGRA legacy matching versus validated single-channel v2 matching. Fire HSV/mask compares full-frame HSV and mask followed by crop with crop-first work. Heading mask compares the same 60x70 crop, including the legacy identity close/open operations and v2 ownership/cache checks.

`cold_registry` constructs a new `TemplateRegistry.from_settings` for each sample: it reads and decodes all 45 selected assets, takes owned copies, and computes all template edges. It is a combined loading-and-preparation measurement, not an isolated edge-preparation or cold-disk benchmark. The OS filesystem cache can be warm. Warm timings reuse only static template derivatives; per-frame contexts and derivatives are new.

Two separate whole-decision workloads call actual `Application.tick` on fresh supported-profile packets. Packet construction/ownership copying, timestamp publication, startup and static template preparation are outside the timed tick. Vision, real state policy, freshness/ownership guards, recording-input dispatch and bounded metrics are inside. Each workload processes 69 distinct publications: 9 warmups and 60 measured frames. The menu workload stays `WAITING/hangar` with `OfflineTelemetry`; the battle workload stays `IN_BATTLE/battle`, initializes the real ammo baseline once, injects valid player/metadata snapshots and executes real aiming/recording-input dispatch. There is no map image or capture zone, so real Navigation returns without submitting a native job. Native planning, telemetry networking, input drivers and live acquisition are excluded and disclosed. Neither decision workload has a comparable legacy whole-stage baseline.

## Runtime observability

`Application.metrics` stores numeric `vision_ns`, `policy_ns`, `decision_ns`, `idle_tick_ns`, `receive_age_ns` and actual `intent_to_dispatch_ns` samples, plus dispatch/idle counters. Samples are bounded by `diagnostics.metrics_samples` (default 512; validated 1–100000), with at most 32 metric series. Snapshot means and percentiles describe the retained window; counts are lifetime counts. No packet/image/intent payload is retained by metrics. The input timing is intent creation to the start of the successful backend dispatch call, not OS completion, game response or render-to-input latency.

Actual `ProcessCapture.statistics` reports delivered packets, observed skipped publication IDs, idle reads and failed calls for the current generation. Gaps include publications before the first consumption and reflect transport replacement/skips; they are not verified source/render drops. Restart starts new generation counters. Read metrics use the same single captured session as packet acquisition, preserving M7's restart/interleaving contract. `ProcessCapture.diagnostic` remains a deep-copy snapshot, and its requested/reported/delivered negotiation and source/window/content geometry are preserved.

The real CLI runtime owns a module-named console handler and rotating `paths.logs/autonavy.log` (default 2000000 bytes, 3 backups); it removes/closes its handlers on exit. Python's rotating handler rolls between records, so a single record can exceed the nominal byte threshold. Config checks/imports do not create handlers/files. State transitions, source geometry, resolved nonsecret settings and final runtime/capture summaries are logged. Explicit `per_frame = true` adds publication/generation/backend/state/receive-age/tick duration; it is off by default. No input resource names or values are logged by metrics.

`CaptureTimeout` during normal reads is an idle tick, not a recurring error. Navigation's `last_error`, preview faults and existing telemetry faults are throttled. Capture child errors retain at most 4096 bytes; native planner errors retain at most 511 bytes in the unchanged 512-byte field. Tracebacks preserve final exception type/reason and selected-device context where applicable; overlong payloads explicitly say they are truncated. Telemetry traceback text is also bounded. Startup constructor failures are logged before rotating handlers close.

Preview defaults off. Explicit preview consumes only M3's already-throttled independent `debug_image`, with its separate `preview_fps` (default 5). There is no second image copy or redisplay of stale overlays. Native display imports occur only on a selected display call. Tests inject a fake display; no real preview window was opened. Preview closes after input and service cleanup, keeping input release before waits.

## Executed measurements (2026-09-09)

Final measured code: `2fdc1cb0daa0542f8b93c956fc04a92e5e019902`. The JSON records the documentation-only dirty state alongside content hashes of the measured scripts/runtime. Host: Windows x64, CPython 3.11.9, AMD64 Family 25 Model 117 Stepping 2, 16 OpenCV threads; NumPy 1.26.0, OpenCV 4.8.0.74, Pillow 11.1.0, DXcam 0.0.5 (metadata only, not imported for capture).

`perf_counter` uses QueryPerformanceCounter with reported 100 ns resolution. `monotonic` uses GetTickCount64 with 15.625 ms resolution on this CPython/Windows host. Capture receive-age and intent-to-dispatch samples can therefore be zero or quantized to roughly 15–16 ms. **Zero samples do not establish zero latency.**

Pipeline command above produced `logs/v2/benchmarks/pipeline-menu-battle.json` and `.csv`. Every table range is the minimum–maximum of the three independent repetition summaries, each with n=20 measured samples and 3 untimed warmups. Values are milliseconds; these are not pooled percentiles.

| Stage | Legacy p50 range | V2 p50 range | V2 p95 range | Median v2/legacy ratio range |
| --- | ---: | ---: | ---: | ---: |
| preprocess | 4.2789–5.4156 | 3.1568–4.7867 | 4.0309–6.1009 | 0.738–0.903 |
| match | 9.8414–9.9749 | 2.2201–2.3110 | 2.5430–2.7251 | 0.223–0.232 |
| hsv_mask | 0.9268–1.0438 | 0.1890–0.2069 | 0.2157–0.3777 | 0.198–0.204 |
| heading_mask | 0.0205–0.0226 | 0.0221–0.0244 | 0.0233–0.0278 | 1.076–1.095 |
| cold_registry | not compared | 13.0516–14.4562 | 15.5555–16.8143 | not compared |
| decision | not compared | 376.0003–393.7699 | 399.9318–441.1682 | not compared |
| decision_battle | not compared | 166.7150–169.5617 | 174.5259–189.5402 | not compared |

The full score-surface maximum absolute difference was `3.919936716556549e-6`, below `6e-6`, with identical aim location `(170, 100)` within the fire ROI (frame position `(540, 300)`). Mask and preprocessing pixel-equality gates passed. All four same-pixel comparisons had no repeated median regression over 10% in initial, final, clock-provenance and menu/battle runs. Raw reports retain every repetition, including slow p95 values.

The heading mask remains slower: final median overhead is approximately 1.55–2.05 microseconds (7.6–9.5%). Its tiny 60x70 ROI gains almost nothing from removing 1x1 morphology; fresh FrameContext construction, ROI validation and bounded derivative-cache bookkeeping add work. This is a documented ownership/validation tradeoff, not an acceleration. No hot-path correctness check was removed to improve a timing result.

The menu workload selects 24 detectors and the battle workload selects 16 (including heading degree). Vision accounts for approximately 99.96% and 99.93% of mean tick time respectively; these runtime summaries include the warmups. Policy means are approximately 0.077 ms and 0.066 ms. The real policy performs 69 recording dispatches in each workload. The code shows many full-profile template matches in the menu set; vision is the measured dominant stage, while a per-matcher CPU profile was not collected.

Both measured decision workloads exceed the 33.3 ms period of the configured 30 Hz target: menu medians are 376–394 ms (roughly 2.5–2.7 decisions/s), battle medians 167–170 ms (roughly 5.9–6.0 decisions/s). Scheduling does not promise that configured tick_hz is achievable. This synthetic noise fixture is not evidence of representative live performance. Further representative offline profiling and ROI/state-selection work would be needed before claiming 30 Hz; live hardware remains unmeasured. The improvements in narrow arithmetic cannot be multiplied into a whole-application speedup.

Capture command executed:

```powershell
.venv/Scripts/python.exe scripts/benchmark_capture.py --backend replay --fixture logs/v2/benchmarks/replay-600 --duration 5 --max-frames 600 --output logs/v2/benchmarks/capture-reviewed
```

The local synthetic fixture contains 600 BGR colors `[i % 256, (i*17) % 256, (i*31) % 256]` for i=0..599 at 1280x720; no screenshot is involved. Manifest SHA-256: `9c2f0067eb19be77945b1a9f600718f0741e0f3186a20cbee476eef9062a9124`. The report files are `logs/v2/benchmarks/capture-reviewed.json` and `.csv`.

It delivered 600 publications in 2.063531 seconds (290.76/s), with zero observed gaps, idle reads or failures. Requested FPS is 60; replay has no reported negotiated FPS and is deliberately unpaced. Delivered dimensions/format are 1280x720 BGR. This number measures synthetic publication/copy throughput, not rendered FPS or live backend performance.

receive_age: n=600, p50=0.0000 ms, p95=16.0000 ms.

capture_read: n=600, p50=3.1726 ms, p95=3.9567 ms.

Collection CPU is 2.031250 seconds, 98.44% of one core; post-cleanup parent working set is 52170752 bytes (49.75 MiB). This covers the benchmark parent only. Replay has no isolated capture/planner child; live-child CPU/memory, GPU/game impact, source presentation rate, source/render latency and capture-only decision/input latency remain unavailable.

Earlier artifacts remain under the same ignored directory: `pipeline-initial`, `pipeline-final`, `pipeline-reviewed`, `capture-replay`, `check-config.txt`, `replay-smoke.txt`. The final menu/battle report adds the separately requested battle characterization; it does not replace or conceal the slower menu measurements.


## Verification

The final permitted regression command was:

```powershell
.venv/Scripts/python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short
```

Result: **440 passed, 1 deselected in 62.34 seconds**. The exclusion is the known launcher policy issue owned by M8b. Full output is `logs/v2/benchmarks/m8a-full-tests.txt`. Focused tests cover bounded samples/cardinality/tracebacks, log rotation/cleanup, constructor failure logging, default-off and injected preview, actual dispatch timing, capture generation interleaving, publication gaps/idle, finite report schema/output protection, correctness-first measurements and the separate real battle workload without native submission. Existing M3 structural tests still check single-channel matching, cached unchanged templates, per-packet derivative work and ROI boundary equivalence. Narrow Ruff and whitespace checks passed; protected source asset/route/native bytes have no diff against `45fc36c`.

This is M8a evidence only. M8b launcher/dependency/CI/build work and independent M8a review remain separate gates. No actual camera, game, input driver, network telemetry, native preview, hardware benchmark, build, push or release was run as part of M8a.
