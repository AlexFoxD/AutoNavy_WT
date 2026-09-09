# AutoNavy v2 status

Source: master at45fc36cc4d173fb1e46eac2dcd1be3338157c500; initially clean, no excluded user changes.
Source worktree: C:\Develop\game\WT\AutoNavy_WT (must remain untouched).
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2.
Last tested and independently reviewed code:0c44df04135d977953dabea9035e26f8fef5df3a (M4 complete).
Initial origin/master:c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master:69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 audit/isolation; M1 safe configuration/CLI/replay; M2 DXcam supervisor/stable packets/geometry/lifecycle; M3 cached packet-bound vision/throttled preview; M4 single-owner telemetry/immutable freshness/map cache/runtime integration. All independently reviewed PASS after scoped fixes. Reports: evidence/M1.md through evidence/M4.md; review history in REVIEW.md.
Current: M5 /root/m5 active from0c44df0. Owns input/controller/scheduler/Windows adapter, behavior/app integration, legacy input modules, relevant config/CLI/vision selection, tests and M5 plan. Coordinator owns shared records; do not stage/revert each other's work. One production writer.
Remaining: M5-M9 implementation/integration/verification. Coordinated input, complete battle flow, navigation, OBS, benchmarks and packaging remain pending. OBS selection currently fails safely. No legacy fallback.

Latest tests: M4 full241passed/1knownlauncherexcluded in70.86s; metadata-invalidation fix41covering passed3.13s; independent reviewer new4cases passed1.16s. Compile/diff checks passed. Fullsuite predates final4tests (focused fix was appropriate). Earlier coordinator config/replay smoke returned0; fixture has3synthetic frames, max-frames caps rather than loops.

Do not run unfiltered legacy suite until M8 repairs tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy. Baseline CheckOnly unexpectedly installed local dependencies and masked RuntimePath binding failure. Permitted regression: `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short`.

Blockers: none established. Hardware capture, OBS, vJoy/game actuation, compiled executable and full latency validation NOT RUN. No input, driver/system changes, push, PR, merge, tag or release. Local venv CPython3.11.9 x64; Nuitka4.2.1/ordered-set4.1.0/zstandard0.23.0 now installed locally, MSVC cl14.5 detected. Actual M8 compile still required; evidence/environment-build-prerequisites.txt and plans/M8-investigation.md.
Next: receive M5 plan/progress/test-first report, independent review, fix/re-review before M6. Prepared task6..9 briefs in .superpowers/sdd/PLAN include appended audited contracts; preserve them. Task5 brief is particularly detailed (current geometry guard, state-specific telemetry and detectors, exact recovery timing).

Resume from this file, SPEC/PLAN/AUDIT/DECISIONS and .superpowers/sdd/PLAN/progress.md. Continue sibling worktree, never restart migration. Retain branch/worktree and repeat source/ref/asset preservation at M9. M2-close/M3-active source/hash recheck matched baseline. No current goal tool exists; this is one continuing authorized task.
