# AutoNavy v2 status

Source: master at 45fc36cc4d173fb1e46eac2dcd1be3338157c500; initially clean, no excluded user changes.
Source worktree: C:\Develop\game\WT\AutoNavy_WT (must remain untouched).
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2.
Last tested and independently reviewed code:713a5079402e18e59069c23f4227f5ab680c4abf (M3 complete; focusedfix36 passed, prior full201passed1excluded).
Initial origin/master: c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master: 69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 audit/isolation/characterization; M1 safe configuration/CLI/replay; M2 real DXcam capture supervisor, stable packets, geometry and lifecycle; M3 packet-bound cached vision and throttled preview. All independently reviewed PASS. M2 round1 fixed generation snapshot/start cancellation races; round2 fixed concurrent cleanup completion/error reporting. Detailed reports and commands: evidence/M1.md and evidence/M2.md; review history in REVIEW.md.
Current: M4 telemetry /root/m4 active from713a507. Owns telemetry.py, info.py, toolkit/map.py, app integration, telemetry tests and M4plan. Coordinator owns shared docs. M3 independently PASS including previewcadence fix.
Remaining: M4-M9 implementation/integration/verification. Telemetry, coordinated input, navigation, OBS, benchmarks and packaging are not delivered yet. Explicit OBS currently fails safely. No legacy fallback.

Latest executed tests (M3):33 focused passed;201 regression passed,1 known launcher-policy test excluded in48.28s. Compileall and diff checks passed. Earlier coordinator config/replay smoke returned0; replay fixture has3 synthetic frames and max-frames caps rather than loops.

Do not run the unfiltered legacy suite until M8 repairs tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy. Baseline -CheckOnly unexpectedly installed local dependencies and masked RuntimePath binding failure. Permitted regression: `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short`.

Blockers: none established. Hardware capture, OBS, vJoy/game actuation, compiled executable and full latency validation NOT RUN. No live input, driver/system changes, push, PR, merge, tag or release. Local .venv and available MSVC toolchain recorded for M8 actual build attempt.
Next: receive M4 test-first report/commit, independent review, fix/re-review before M5. Later briefs task4..9 are already prepared in .superpowers/sdd/PLAN; preserve appended contract detail.

Resume after compaction from this file, SPEC/PLAN/AUDIT/DECISIONS and .superpowers/sdd/PLAN/progress.md. All work continues in the sibling worktree; source checkout remains untouched. Retain branch/worktree and repeat source/ref/asset preservation checks at M9.
