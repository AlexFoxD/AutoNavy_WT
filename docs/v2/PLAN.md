# AutoNavy v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Execute task by task with test-first changes and independent task review.

**Goal:** Implement the approved modernization in the actual application, with non-actuating offline verification.
**Architecture:** One managed runtime owns capture, telemetry and input. Decisions consume owned frame packets and fresh snapshots. Pure vision, geometry and navigation feed bounded input intents.
**Tech Stack:** Windows x64 CPython 3.11, NumPy 1.26.0, OpenCV 4.8.0.74, Requests 2.32.3, DXcam 0.0.5, pytest.
**Spec:** docs/v2/SPEC.md (binding; milestone briefs supplement this index).

## Global Constraints

- Keep DXcam as the default capture backend. Implement OBS Virtual Camera as a fully wired, optional alternative. Do not assume OBS is faster.
- Use one process with managed threads initially. Introduce process isolation only for a documented native-call shutdown problem or a measured CPU bottleneck.
- Preserve Windows x64 and CPython 3.11 compatibility, including `toolkit/way_search.cp311-win_amd64.pyd`.
- All new development communication, identifiers, comments, docstrings, documentation and application messages are English; preserve protocol values, resource filenames, template pixels and notices.
- No live input, matchmaking, purchases, driver installation, global environment changes, push, PR, merge, tag or release during implementation/verification.
- Source `master` at `45fc36cc4d173fb1e46eac2dcd1be3338157c500` remains untouched. Retain `feature/v2-modernization` and sibling worktree.
- Built-in defaults < explicit TOML config < explicit CLI flags. Replay can never enable input.
- Each implementation task: write observable failing tests; record RED; implement; record GREEN; review real callers and quality; fix; scoped commit.

## Milestones and interfaces

### Task 0: M0 isolation, audit and characterization
Files: docs/v2/*.md, tests/unit/test_legacy_characterization.py.
- [x] Inspect source, clean status, branches, worktrees, instructions and installed workflow.
- [x] Create isolated branch from exact source SHA and persist complete embedded specification.
- [ ] Reconcile actual gameplay symbols and build/launcher/test constraints in AUDIT.md.
- [ ] Run `.venv/Scripts/python.exe -m pytest tests -q` without live devices and record baseline.
- [ ] Characterize color Canny, four-channel matching and 1x1 morphology using synthetic images; never import unsafe legacy modules.
- [ ] Commit audit and plan after content checks.

### Task 1: M1 safe foundations
Files: autonavy/{__init__,__main__,cli,config,models,app}.py, autonavy/capture/replay.py, configs/default.toml, start_prog.py, main.py, autonavy.py, tests/unit/test_foundations.py, tests/integration/test_replay.py, tests/fixtures/smoke/manifest.json.
Interfaces: `Settings`, `load_settings(path=None, overrides=None) -> Settings`; `FramePacket`; `RuntimeState`; `main(argv=None) -> int`; `Application(settings).run() -> int`.
- [ ] First test import safety, config precedence/unknown keys, bounded replay and replay/input rejection. Assert `main(['--capture','replay','--enable-input']) == 2`; subprocess help/check/replay must avoid hardware imports/network.
- [ ] Run focused tests RED, implement safe configuration, finite synthetic replay and minimal cleanup; migrate supported Python entrypoints to same CLI.
- [ ] Run GREEN/regression, review and commit. Later milestones extend live runtime; no temporary live fallback.

### Task 2: M2 capture ownership and geometry
Files: autonavy/capture/{base,dxcam,latest,factory}.py, autonavy/geometry.py, autonavy/windows.py, autonavy/app.py, toolkit/scn.py, tests/unit/test_capture.py, tests/unit/test_geometry.py.
Interfaces: `start/read/stop/close` capture protocol; `LatestFrameSlot.publish/read/wait/close`; generation-tagged owned `FramePacket`; pure frame/ROI/desktop transforms.
- [ ] Test producer buffer mutation, latest-only replacement, shutdown wake, fake DXcam no-frame/error/restart, moved/negative-origin windows.
- [ ] Preserve pin, explicit startup and non-repeated frames; inspect pinned native read semantics and use narrowly supervised capture process if a blocking call cannot be safely interrupted.
- [ ] Factory and application must use selected backend; no independent camera reader remains. GREEN/review/commit.

### Task 3: M3 vision
Files: autonavy/vision/{context,templates,detectors}.py, toolkit/{scn,img_map,deg_cal}.py, firesystem.py, autonavy/app.py, tests/unit/test_vision.py.
Interfaces: `FrameContext(packet)` caches bounded ROI derivatives; `TemplateRegistry` caches color-input Canny per version; structured match and degree observations.
- [ ] Characterization first: single-channel score/location agrees with legacy expansion; ROI HSV equals cropped full-frame HSV; 1x1 morphology is identity.
- [ ] RED tests for empty/oversize/constant templates, nonfinite score, positive/negative matches, cache call counts, coordinates, no contours, debug immutability.
- [ ] Implement cached detectors, same-packet degree extraction and runtime recognition. GREEN/review/commit.

### Task 4: M4 telemetry
Files: autonavy/telemetry.py, info.py, toolkit/map.py, autonavy/app.py, tests/unit/test_telemetry.py.
Interfaces: immutable `TelemetrySnapshot`; lifecycle-owned `TelemetryService` with `snapshot()`; isolated cached map metadata/image.
- [ ] RED: timeout/status/schema/missing player/empty zones/nonfinite/stale/recovery/session change; failed polls preserve last-success time.
- [ ] Single reusable Session; 10 Hz, (0.5,0.5) timeout, 1s TTL; serial polling without backlog; move all active HTTP callers behind snapshot service.
- [ ] GREEN/review/commit; document Requests tuple is not a total deadline.

### Task 5: M5 coordinated input and integrated battle flow
Files: autonavy/input/{controller,scheduler,windows}.py, autonavy/app.py, autonavy/behavior.py, toolkit/{MnK,joystick,th_pool}.py, firesystem.py, dxin.py, tests/unit/test_input.py, tests/integration/test_battle_cycle.py.
Interfaces: `InputIntent`; `InputController.submit/tick/cancel/release_all`; owned generation tokens; clock-injected bounded scheduling; runtime waiting/battle/recovery/pause/end/stop states.
- [ ] RED: priority/preemption, stale release race, focus/emergency/profile/telemetry checks immediately before dispatch, wheel signs/zero, all held input release despite errors, vJoy neutral, bounded coalescing.
- [ ] RED: fake complete battle cycle, startup/worker/camera errors, pause then stop, cancellation without sleeps, purchase dialogs pause.
- [ ] Implement physical adapters lazily; preserve failsafe; explicit live opt-in and hotkey lifecycle; release before slow cleanup. Remove direct-input/asynchronous-kill bypasses. GREEN/review/commit.

### Task 6: M6 navigation and controllers
Files: autonavy/navigation/{route,native,control,planner}.py, pilot.py, toolkit/process_path.py, autonavy/behavior.py, tests/unit/test_navigation.py.
Interfaces: immutable ordered `RouteCursor`; lazy `NativePathfinder`; bounded replanning service; `angular_error(target,current)`; separate pixel/heading controllers with reset.
- [ ] RED: immutable paths, intersections cannot jump, adjacent endpoints, no route, bounded retries, cancellation, 359->1=+2, 1->359=-2, tie=-180, invalid/large elapsed times and reset.
- [ ] Native audit shows GOAL->ORIGIN interior path, endpoints excluded; reverse once, add requested endpoints, do not concatenate jump points. Handle same-point before native; empty interior can mean adjacent valid path.
- [ ] Integrate route planning into real battle navigation and verify actuator sign from legacy mappings. GREEN/review/commit.

### Task 7: M7 optional OBS and geometry
Files: autonavy/capture/obs.py, autonavy/capture/factory.py, autonavy/geometry.py, autonavy/app.py, tests/unit/test_obs.py.
- [ ] RED: selected device only, failed open/read, shape/dimension mismatch, BGR, cleanup/reopen and optional-import isolation.
- [ ] Real VideoCapture(index,api) with actual properties; content rectangle separate from desktop bounds; test scale/letterbox/move invalidation and diagnostic output.
- [ ] Native blocking capture uses tested process shutdown if required; fake hanging backend demonstrates termination only after input cleanup. GREEN/review/commit.

### Task 8: M8 tooling and packaging
Files: scripts/benchmark_{pipeline,capture}.py, autonavy/metrics.py, requirements-{core,dev}.txt, scripts/{install,run,launcher,build}.ps1, scripts/check_environment.py, .github/workflows/*.yml, README.md, docs/v2/{BENCHMARKS,MIGRATION}.md.
- [ ] RED: metrics bounded, benchmark schema correctness and finite sample counts, CLI flag forwarding, core preflight and packaged resource resolution.
- [ ] Implement finite warm/cold JSON/CSV timings, capture delivery/freshness metrics with explicit unknown source latency; run offline measurements without timing assertions.
- [ ] Keep dependency ABI pins; primary-source DXcam update assessment; Linux/Windows 3.11 core CI, Windows packaging resources and no automatic publishing.
- [ ] Execute available script/build smoke checks, classify true hardware/build checks; GREEN/review/commit.

### Task 9: M9 final review and handoff
Files: docs/v2/{STATUS,VERIFICATION,REVIEW,DECISIONS,BENCHMARKS,MIGRATION}.md.
- [ ] Full suite and scoped lint; finite replay through supported launchers; requirements A01-A39 mapped to real implementation/callers/evidence.
- [ ] Independent whole-branch review; targeted failing regression tests for findings; fixes and re-review.
- [ ] Compare source branch/status/assets/native hashes with baseline, retain worktree/branch, record last verified code commit and clean state.
- [ ] Deliver exact executed/manual commands, measured scope, safe launch/stop/rollback and precise hardware gaps.

## Dependency review

| Tasks | Shared boundary | Resolution |
|---|---|---|
| 1/2/3/4/5/6/7 | app.py and settings/contracts | Sequential implementers; extend real runtime each milestone |
| 2/3/7 | FramePacket geometry and source generation | One ownership copy, consumer cache per packet, no source timestamp invention |
| 4/5/6 | Fresh snapshot/session | Cancel battle state and route/intents on generation change |
| 5/6 | Typed input intents | Navigation emits only, controller alone actuates |
| 1/8 | Legacy entrypoints/build | Keep autonavy.py thin shim for packaged launcher while package serves -m |
| 0-9 | Documentation/evidence | Coordinator owns persistent status; never mark downstream implementation delivered early |
