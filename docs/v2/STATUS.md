# AutoNavy v2 status

Source: master at45fc36cc4d173fb1e46eac2dcd1be3338157c500; initially clean, no excluded user changes.
Source worktree: C:\Develop\game\WT\AutoNavy_WT (must remain untouched).
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2.
Last tested and independently reviewed code:20142e08612a9fb7c106e10e772a769e7633512f (M5 complete).
Initial origin/master:c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master:69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 audit/isolation; M1 safe configuration/CLI/replay; M2 DXcam ownership/geometry/lifecycle; M3 packet-bound cached vision; M4 single-owner telemetry; M5 coordinated guarded input and cancellable battle flow. Independently reviewed PASS after scoped fixes; evidence/M1.md through evidence/M5.md.
Current: M6 /root/m6 active from9740ead (M5 accepted20142e0). Owns navigation/controller production integration, legacy navigation migration, relevant config/tests and M6 plan. Coordinator owns shared records; one production writer.
Remaining: M6-M9 navigation, OBS, benchmarks/packaging, final review and verification. OBS selection currently fails safely. No legacy fallback.

Latest tests: M5 fix16new/168covering passed; full326passed1knownlauncherexcluded50.27s; compile/staged diff passed. Evidence/M5.md contains exact RED/GREEN and commands. Coordinator config/replay smoke at12c6379 returned0; fixture3synthetic frames, max-frames caps rather than loops. Independent M5 scoped re-review PASS, no new findings.

Do not run unfiltered legacy suite until M8 repairs tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy. Baseline CheckOnly unexpectedly installed local dependencies and masked RuntimePath binding failure. Permitted regression: `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short`.

Blockers: none established. Hardware capture, OBS, vJoy/game actuation, compiled executable and full latency validation NOT RUN. No input, driver/system changes, push, PR, merge, tag or release. Local venv CPython3.11.9 x64; Nuitka4.2.1/ordered-set4.1.0/zstandard0.23.0 now installed locally, MSVC cl14.5 detected. Actual M8 compile still required; evidence/environment-build-prerequisites.txt and plans/M8-investigation.md.
Next: M6 from20142e0 using prepared task6 brief, then independent review. Preserve appended audited contracts in task6..9 briefs. M6 must wire native planner and separate controllers through actual M5 policy and cleanup.

Resume from this file, SPEC/PLAN/AUDIT/DECISIONS and .superpowers/sdd/PLAN/progress.md. Continue sibling worktree, never restart migration. Retain branch/worktree and repeat source/ref/asset preservation at M9. M2-close/M3-active source/hash recheck matched baseline. No current goal tool exists; this is one continuing authorized task.
