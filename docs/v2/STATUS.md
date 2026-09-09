# AutoNavy v2 status

Source: master at 45fc36cc4d173fb1e46eac2dcd1be3338157c500, initially clean. Original worktree C:\Develop\game\WT\AutoNavy_WT must remain untouched.
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2. M8a starts from documentation commit 06b81de. Last independently accepted production code: 1b5ca7877330f2b4e35a6db8374a21b7c0d5b0f1 (M7).
Initial origin/master: c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master: 69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 audit/isolation; M1 safe configuration/CLI/replay; M2 DXcam ownership, geometry and lifecycle; M3 cached packet-bound vision; M4 central telemetry; M5 guarded input and cancellable battle flow; M6 ordered native navigation and independent controllers; M7 real optional OBS and calibrated source geometry. Independent review gates passed after recorded fixes. Reports are in evidence/M1.md through evidence/M7.md; review history is in REVIEW.md.

Current: /root/m8a implements benchmarks and runtime diagnostics. It owns benchmark scripts, actual bounded metrics/logging/preview integration, necessary config/tests, plans/M8a.md and BENCHMARKS.md. Coordinator owns shared status/acceptance/review/decision records and evidence copies. One production writer; no staging or reverting each other's changes.

Remaining: M8a implementation, measurements and independent review; M8b launcher/preflight/dependency/CI/actual Windows build and English operation docs, then review; M9 full available verification, whole-branch review/fixes and handoff. Prepared task-8a-brief.md and task-8b-brief.md supplement the full task-8-brief.md in .superpowers/sdd/PLAN. Preserve their appended audits. Both M8 gates are required.

Latest verification: M7 full permitted suite 411 passed, 1 known launcher exclusion in 61.51s. Subsequent test-only strengthening: 21 OBS tests passed in 0.36s. OBS config-only CLI exited 0. No production changes followed the full suite. M7 independent SPEC/QUALITY PASS. M6 executed native-only adapter and encoded-map planning smoke on CPython 3.11.9 x64; this is not a hardware/game check.

Do not run the unfiltered legacy suite until M8b repairs tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy. Baseline CheckOnly unexpectedly installed local dependencies and masked RuntimePath binding failure. Until repaired, use `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short`.

No established blocker. Hardware capture, OBS device identity, vJoy/game actuation, compiled executable and complete latency validation remain NOT RUN. No real camera or game input, driver/system changes, push, PR, merge, tag or release. Local environment is CPython 3.11.9 x64; Nuitka 4.2.1, ordered-set 4.1.0 and zstandard 0.23.0 are installed locally; MSVC cl14.5 is available. M8b must migrate static build readiness before attempting the actual compile, then verify device-free frozen capture/planner spawning and resources. Evidence: environment-build-prerequisites.txt, DXcam-upgrade-assessment.md and plans/M8-investigation.md.

Latest source preservation check during M7: original checkout clean; source/default refs unchanged; src tree and native blob/SHA256 match baseline; no target working asset/native diff. Repeat at M9. All commits remain local and the finished branch/worktree must be retained. No goal tool is active.

Resume this continuing execution from STATUS, SPEC, PLAN, AUDIT, DECISIONS and .superpowers/sdd/PLAN/progress.md. Do not restart the migration, reopen approved design questions, or treat context limits as completion. M8a reviewer comes before M8b writer; final answer only after required work is completed or a genuine blocker is precisely established.
