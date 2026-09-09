# AutoNavy v2 status

Source: master at 45fc36cc4d173fb1e46eac2dcd1be3338157c500; initially clean, no excluded user changes.
Source worktree: C:\Develop\game\WT\AutoNavy_WT (must remain untouched).
Target: feature/v2-modernization at C:\Develop\game\WT\AutoNavy_WT-v2.
Last verified code checkpoint: 0c9a5d8fe693fe3b81cfe71e3cf7c3ca957ec9a7 (M1 foundations and reviewed fixes).
Initial origin/master: c2f889336e5c656763ecac76ed54c960b36a666f; upstream/master: 69570b424a3b552b4d56ebca062cc412ad105521.

Completed: M0 isolation/audit/characterization and independent review (record fixes df8cd8f re-reviewed PASS). M1 implementation and self-review committed; independent M1 review requires fixes for offline/preflight flag conflicts and invalid config encoding. Original M1 worker is applying test-first fixes; do not mark review complete yet.
Current: execute M2 capture/geometry using the prepared .superpowers/sdd/PLAN/task-2-brief.md and DECISIONS.md capture-process rationale.
Remaining: M2-M9 implementation/integration/verification. Live capture, vision, telemetry, input, navigation, OBS, benchmarks and packaging are not delivered yet. M1 live selections deliberately fail safely; no legacy fallback.

Last tests (M1 worker): 66 focused passed; full regression excluding one known side-effecting legacy test: 107 passed, 1 deselected in 7.82s; compileall and scoped diff check passed. Evidence: docs/v2/evidence/M1.md.
Coordinator smoke at 43aa40e: `.venv\Scripts\python.exe -m autonavy --check-config --config configs/default.toml` returned 0; `.venv\Scripts\python.exe -m autonavy --dry-run --capture replay --fixture tests/fixtures/smoke --max-frames 120` returned 0 after 3 synthetic frames, state stopped. Neither requires hardware/network.

Do not run the unfiltered legacy suite until M8 fixes `tests/test_launcher.py::LauncherPolicyTests::test_batch_launcher_does_not_permanently_change_execution_policy`; baseline -CheckOnly unexpectedly installed local dependencies and masked a RuntimePath binding failure. Use `.venv\Scripts\python.exe -m pytest tests -q -k 'not test_batch_launcher_does_not_permanently_change_execution_policy' --tb=short` meanwhile.

Blockers: none established. Hardware capture/OBS/vJoy/game actuation/compiled executable/full latency validation NOT RUN. No live input, driver/system changes, push, PR, merge, tag or release.
Next executable action: dispatch M2 from .superpowers/sdd/PLAN/task-2-brief.md (capture-process rationale in DECISIONS.md). Review package: .superpowers/sdd/PLAN/review-df8cd8f..43aa40e.diff; report: docs/v2/evidence/M1.md.

Coordinator owns shared docs; M2 capture implementer will own its scoped package/capture/geometry/app/tests. M1 is complete and should not be reimplemented. Inspect git status/log, this file, SPEC.md/PLAN.md/AUDIT.md/DECISIONS.md and the SDD progress ledger after compaction. Continue this worktree, never restart migration. Retain final branch/worktree and repeat source/ref/asset preservation checks at M9.


