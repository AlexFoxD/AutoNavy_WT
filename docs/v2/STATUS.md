# AutoNavy v2 status

Source: master at45fc36cc4d173fb1e46eac2dcd1be3338157c500; initially clean, no excluded user changes.
Source worktree: C:\Develop\game\WT\AutoNavy_WT (must remain untouched).
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2.
Last tested and independently reviewed code:c4c3810c37f9202c387d8e95650e0bf667b9369c (M6 complete).
Initial origin/master:c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master:69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 audit/isolation; M1 safe configuration/CLI/replay; M2 DXcam ownership/geometry/lifecycle; M3 packet-bound cached vision; M4 single-owner telemetry; M5 coordinated guarded input and cancellable battle flow; M6 ordered native navigation and independent controllers. Independently reviewed PASS after scoped fixes; evidence/M1.md through evidence/M6.md.
Current: M6 review gate PASS atc4c3810, corner-progress finding addressed with no new issues. M7 optional OBS/source geometry next. Coordinator owns shared records.
Remaining: M7 OBS/source geometry; M8a measured benchmarks/runtime diagnostics; M8b launchers/dependencies/CI/actual packaging/English operation docs; M9 final review and handoff. OBS currently fails safely until M7.

Latest tests: M6 full371passed1knownlauncherexcluded56.68s at9ca0e57; final route fix3new/86covering passed3.52s atc4c3810. Real native-only adapter/encoded-map supervisor smoke passedCPython3.11.9. Coordinator config/replay9ca0e57 exit0,3synthetic frames. Independent M6 re-review PASS.

Do not run unfiltered legacy suite until M8 repairs tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy. Baseline CheckOnly unexpectedly installed local dependencies and masked RuntimePath binding failure. Permitted regression: `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short`.

Blockers: none established. Hardware capture, OBS, vJoy/game actuation, compiled executable and full latency validation NOT RUN. No input, driver/system changes, push, PR, merge, tag or release. Local venv CPython3.11.9 x64; Nuitka4.2.1/ordered-set4.1.0/zstandard0.23.0 now installed locally, MSVC cl14.5 detected. Actual M8 compile still required; evidence/environment-build-prerequisites.txt and plans/M8-investigation.md.
Next: M7 using preserved task7 brief, then scoped review/fixes. M8 explicitly subdivided in PLAN and task8 brief; static preflight must be repaired before actual compile, frozen capture/planner spawn required.

Resume from this file, SPEC/PLAN/AUDIT/DECISIONS and .superpowers/sdd/PLAN/progress.md. Continue sibling worktree, never restart migration. Retain branch/worktree and repeat source/ref/asset preservation at M9. M2-close/M3-active source/hash recheck matched baseline. No current goal tool exists; this is one continuing authorized task.
