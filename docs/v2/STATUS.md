# AutoNavy v2 status

Source: master at 45fc36cc4d173fb1e46eac2dcd1be3338157c500; initially clean, no excluded user changes.
Source worktree: C:\Develop\game\WT\AutoNavy_WT (must remain untouched).
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2.
Last tested code checkpoint: e7119e08d2080e8dfe288bab42996d1fc0b0bf65 (M2 capture/geometry; independent review active). Last reviewed milestone: M1 at 0c9a5d8.
Initial origin/master: c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master: 69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 isolation/audit/characterization and independent review (record fixes df8cd8f re-reviewed PASS). M1 implementation, two review fixes at 0c9a5d8, and independent scoped re-review: SPEC PASS, QUALITY PASS, no new findings.
Current: M2 fix round 1 with original implementer after independent review found two lifecycle races: mixed-generation read transport and lost application stop during capture construction/startup. Fix and re-review before M3. M2 implementation includes the real DXcam factory/process and packet geometry; no hardware verification has run.
Remaining: M2 review/fixes and M3-M9 implementation/integration/verification. Vision, telemetry, input, navigation, OBS, benchmarks and packaging are not delivered yet. Explicit OBS selection fails safely until M7; no legacy fallback.

Last tests (M2 worker): full regression 156 passed, 1 known policy test deselected in 18.14s; compileall and scoped diff check passed. Evidence: docs/v2/evidence/M2.md. M1 evidence remains in evidence/M1.md.
Coordinator smoke at 43aa40e: `.venv\Scripts\python.exe -m autonavy --check-config --config configs/default.toml` returned 0; `.venv\Scripts\python.exe -m autonavy --dry-run --capture replay --fixture tests/fixtures/smoke --max-frames 120` returned 0 after 3 synthetic frames, state stopped. Neither requires hardware/network.

Do not run the unfiltered legacy suite until M8 fixes `tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy`; baseline -CheckOnly unexpectedly installed local dependencies and masked a RuntimePath binding failure. Use `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short` meanwhile.

Blockers: none established. Hardware capture/OBS/vJoy/game actuation/compiled executable/full latency validation NOT RUN. No live input, driver/system changes, push, PR, merge, tag or release.
Next executable action: receive /root/m2 fix report and commit; request independent scoped re-review, then dispatch M3 using its prepared brief after a passing gate. Review package: .superpowers/sdd/PLAN/review-19ed1b6..e7119e0.diff. Coordinator replay smoke at e7119e0 returned0 after3 synthetic frames, stopped.

Coordinator owns shared docs; original M2 worker owns capture/app/tests for fix round 1. M1 is complete and should not be reimplemented. Inspect git status/log, this file, SPEC.md/PLAN.md/AUDIT.md/DECISIONS.md and the SDD progress ledger after compaction. Continue this worktree, never restart migration. Retain final branch/worktree and repeat source/ref/asset preservation checks at M9.



## M2 historical implementation notes (superseded by current checkpoint above)

Worker /root/m2 is active from base19ed1b6. Initial RED: 8 unit and7 integration failures; first implementation13/15 focused passed, with startup/read errors incorrectly repeated during close. Worker is separating cleanup errors and expanding edge tests; no M2 milestone completion claim yet. Spawn transport, retained-pixel/packet geometry, stop wake, abandoned-lock timeout, hung child reclaim and factory/cancellation tests passed in that intermediate run. Wait for final task report and review before downstream production edits.

M2 first complete permitted regression reported152 passed,1 known policy test excluded. Self-review is adding calibration logging and uniform replay read(timeout=...) compatibility. Wait for committed final report and independent review; intermediate pass count is not milestone exit evidence.

