# AutoNavy v2 status

Source: master at45fc36cc4d173fb1e46eac2dcd1be3338157c500; initially clean, no excluded user changes.
Source worktree: C:\Develop\game\WT\AutoNavy_WT (must remain untouched).
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2.
Last tested and independently reviewed code: 1b5ca7877330f2b4e35a6db8374a21b7c0d5b0f1 (M7 complete).
Initial origin/master:c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master:69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 audit/isolation; M1 safe configuration/CLI/replay; M2 DXcam ownership/geometry/lifecycle; M3 packet-bound cached vision; M4 single-owner telemetry; M5 coordinated guarded input and cancellable battle flow; M6 ordered native navigation and independent controllers; M7 real optional OBS/source geometry. Independently reviewed PASS after scoped fixes; evidence/M1.md through evidence/M7.md.
Current: M7 independent review PASS at1b5ca78 with no actionable findings. M8a benchmarks/runtime diagnostics next; M8b launcher/build/docs follows its review. Coordinator owns shared records.
Remaining: M8a measured benchmarks/runtime diagnostics; M8b launchers/dependencies/CI/actual packaging/English operation docs; M9 final review and handoff. DXcam and OBS adapters are implemented; hardware validation remains NOT RUN.

Latest tests: M7 full 411 passed, 1 known launcher exclusion in61.51s; final21 OBS unit tests passed0.36s after test-only strengthening. OBS config-only CLI exited0. No production change after full suite. M7 independent review PASS; no hardware capture/input/latency tests.

Do not run unfiltered legacy suite until M8 repairs tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy. Baseline CheckOnly unexpectedly installed local dependencies and masked RuntimePath binding failure. Permitted regression: `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short`.

Blockers: none established. Hardware capture, OBS, vJoy/game actuation, compiled executable and full latency validation NOT RUN. No input, driver/system changes, push, PR, merge, tag or release. Local venv CPython3.11.9 x64; Nuitka4.2.1/ordered-set4.1.0/zstandard0.23.0 now installed locally, MSVC cl14.5 detected. Actual M8 compile still required; evidence/environment-build-prerequisites.txt and plans/M8-investigation.md.
Next: task-8a-brief.md implementation and review, then task-8b-brief.md. Parent task8 brief retains detailed audit contracts. Actual Windows compilation follows repaired offline preflight; true frozen resource/capture/planner spawn tests required.

Resume from this file, SPEC/PLAN/AUDIT/DECISIONS and .superpowers/sdd/PLAN/progress.md. Continue sibling worktree, never restart migration. Retain branch/worktree and repeat source/ref/asset preservation at M9. M2-close/M3-active source/hash recheck matched baseline. No current goal tool exists; this is one continuing authorized task.
