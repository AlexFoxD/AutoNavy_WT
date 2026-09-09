# AutoNavy v2 status

Source: master at 45fc36cc4d173fb1e46eac2dcd1be3338157c500; initially clean, no excluded user changes.
Source worktree: C:\Develop\game\WT\AutoNavy_WT (must remain untouched).
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2.
Last tested and independently reviewed code: ceee7bb886f7f4b524f2c8560c4efd64dd6f4720 (M2 complete).
Initial origin/master: c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master: 69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 audit/isolation/characterization; M1 safe configuration/CLI/replay; M2 real DXcam capture supervisor, stable packets, geometry and lifecycle. All independently reviewed PASS. M2 round1 fixed generation snapshot/start cancellation races; round2 fixed concurrent cleanup completion/error reporting. Detailed reports and commands: evidence/M1.md and evidence/M2.md; review history in REVIEW.md.
Current: M3 implemented59e5914, independent reviewer /root/m3_review active on987dc61..59e5914. No production writer while review runs. Full evidence: evidence/M3.md. Coordinator owns shared docs.
Remaining: M3-M9 implementation/integration/verification. Telemetry, coordinated input, navigation, OBS, benchmarks and packaging are not delivered yet. Explicit OBS currently fails safely. No legacy fallback.

Latest executed tests (M3):33 focused passed;201 regression passed,1 known launcher-policy test excluded in48.28s. Compileall and diff checks passed. Earlier coordinator config/replay smoke returned0; replay fixture has3 synthetic frames and max-frames caps rather than loops.

Do not run the unfiltered legacy suite until M8 repairs tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy. Baseline -CheckOnly unexpectedly installed local dependencies and masked RuntimePath binding failure. Permitted regression: `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short`.

Blockers: none established. Hardware capture, OBS, vJoy/game actuation, compiled executable and full latency validation NOT RUN. No live input, driver/system changes, push, PR, merge, tag or release. Local .venv and available MSVC toolchain recorded for M8 actual build attempt.
Next: receive M3 independent review, route findings to original /root/m3 for scoped fixes/re-review or advance M4 after passing gate. Later briefs task4..9 are already prepared in .superpowers/sdd/PLAN; preserve appended contract detail.

Resume after compaction from this file, SPEC/PLAN/AUDIT/DECISIONS and .superpowers/sdd/PLAN/progress.md. All work continues in the sibling worktree; source checkout remains untouched. Retain branch/worktree and repeat source/ref/asset preservation checks at M9.
