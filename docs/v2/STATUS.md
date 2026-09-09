# AutoNavy v2 status

Source: master at 45fc36cc4d173fb1e46eac2dcd1be3338157c500; initially clean, no excluded user changes.
Source worktree: C:\Develop\game\WT\AutoNavy_WT (must remain untouched).
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2.
Last tested and independently reviewed code: ceee7bb886f7f4b524f2c8560c4efd64dd6f4720 (M2 complete).
Initial origin/master: c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master: 69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 audit/isolation/characterization; M1 safe configuration/CLI/replay; M2 real DXcam capture supervisor, stable packets, geometry and lifecycle. All independently reviewed PASS. M2 round1 fixed generation snapshot/start cancellation races; round2 fixed concurrent cleanup completion/error reporting. Detailed reports and commands: evidence/M1.md and evidence/M2.md; review history in REVIEW.md.
Current: M3 vision implementer /root/m3, baseceee7bb. Ownership: vision modules, legacy image helpers/firesystem, app integration, vision tests and plans/M3.md. Coordinator owns shared docs; do not stage each other's work. No other production writer.
Remaining: M3-M9 implementation/integration/verification. Telemetry, coordinated input, navigation, OBS, benchmarks and packaging are not delivered yet. Explicit OBS currently fails safely. No legacy fallback.

Latest executed tests (M2 round2):3 new race regressions passed;78 focused passed;168 regression passed,1 known launcher-policy test excluded in29.93s. Compileall and diff checks passed. Earlier coordinator config/replay smoke returned0; replay fixture has3 synthetic frames and max-frames caps rather than loops.

Do not run the unfiltered legacy suite until M8 repairs tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy. Baseline -CheckOnly unexpectedly installed local dependencies and masked RuntimePath binding failure. Permitted regression: `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short`.

Blockers: none established. Hardware capture, OBS, vJoy/game actuation, compiled executable and full latency validation NOT RUN. No live input, driver/system changes, push, PR, merge, tag or release. Local .venv and available MSVC toolchain recorded for M8 actual build attempt.
Next: receive M3 test-first report/scoped commit, generate review package, dispatch independent review, fix any findings before M4. Later briefs task4..9 are already prepared in .superpowers/sdd/PLAN; preserve appended contract detail.

Resume after compaction from this file, SPEC/PLAN/AUDIT/DECISIONS and .superpowers/sdd/PLAN/progress.md. All work continues in the sibling worktree; source checkout remains untouched. Retain branch/worktree and repeat source/ref/asset preservation checks at M9.
