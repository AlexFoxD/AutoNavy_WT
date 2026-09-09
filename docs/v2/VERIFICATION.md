# Verification evidence

Environment: Windows, project-local CPython 3.11 x64. Source 45fc36cc4d173fb1e46eac2dcd1be3338157c500. No live input or game startup is authorized for verification.

Current stage: M0 audit/baseline complete with record corrections pending re-review; M1 foundations implementation active. A01/A02 below pass for the current M0 checkpoint. Downstream acceptance remains NOT RUN until concrete implementation and verification evidence exists. A01 requires another preservation check at final handoff.

Hardware capture, OBS, vJoy actuation, matchmaking, packaged executable and source-to-input latency: NOT RUN.

## M0 executed baseline

- `.venv\Scripts\python.exe -m pytest tests -q`: **42 passed, 14 warnings in 37.97s** (39 existing tests plus 3 new synthetic characterization tests).
- `.venv\Scripts\python.exe -m pytest tests/unit/test_legacy_characterization.py -q`: **3 passed in 0.17s**.
- Interpreter: CPython 3.11.9 x64, Windows build 26200. NumPy 1.26.0, OpenCV 4.8.0.74, Requests 2.32.3, SciPy 1.15.1, pytest 8.3.5.
- The existing launcher policy test invokes `-CheckOnly`, which unexpectedly repairs project-local dependencies. Its permissive exit-code assertion passes despite a `RuntimePath` PowerShell binding failure recorded in `logs/launcher-20260909-180131.log`. This is a pre-existing launcher defect to fix in M8; a passing suite does not establish a working launcher. No driver install or real input occurred. Subsequent verification will avoid this side effect until repaired.
- Matplotlib/Pyparsing deprecation warnings occurred during initial collection; launcher repair restored repository runtime pins afterward. Do not suppress warnings to manufacture a clean baseline.
- Native-only smoke: three subprocess probes, exit 0, bounded 15-second timeouts, detailed cases in AUDIT.md. Not a native game-route accuracy claim.

## Acceptance ledger

| Requirement | Status | Evidence |
|---|---|---|
| A01 / GIT-01 | PASS | M0 scope: isolated `feature/v2-modernization` worktree from exact source 45fc36c; source checkout clean and HEAD/master/default refs unchanged; recorded src/native tree/blob/hash match. Commands and identifiers in Preservation baseline below. Local commit 021f575; no push/merge/release. Final preservation recheck still required at M9. |
| A02 / AUDIT-01 | PASS | M0 scope: AUDIT.md exact-symbol reconciliation and behavior inventory, three bounded native-only probes, environment constraints and executed 42-test baseline plus 3-test characterization recheck above; characterization at tests/unit/test_legacy_characterization.py, committed in 021f575. Hardware accuracy explicitly unverified. |
| A03 / ARCH-01 | NOT RUN | Implementation/validation pending |
| A04 / CAP-01 | NOT RUN | Implementation/validation pending |
| A05 / FRAME-01 | NOT RUN | Implementation/validation pending |
| A06 / FRAME-01 | NOT RUN | Implementation/validation pending |
| A07 / FRAME-01 | NOT RUN | Implementation/validation pending |
| A08 / CAP-03 | NOT RUN | Implementation/validation pending |
| A09 / VISION-01 | NOT RUN | Implementation/validation pending |
| A10 / VISION-01 | NOT RUN | Implementation/validation pending |
| A11 / VISION-02 | NOT RUN | Implementation/validation pending |
| A12 / VISION-02/03 | NOT RUN | Implementation/validation pending |
| A13 / GEOM-01 | NOT RUN | Implementation/validation pending |
| A14 / GEOM-01 | NOT RUN | Implementation/validation pending |
| A15 / TEL-01 | NOT RUN | Implementation/validation pending |
| A16 / TEL-01 | NOT RUN | Implementation/validation pending |
| A17 / TEL-01 | NOT RUN | Implementation/validation pending |
| A18 / LIFE-01 | NOT RUN | Implementation/validation pending |
| A19 / LIFE-01 | NOT RUN | Implementation/validation pending |
| A20 / INPUT-01 | NOT RUN | Implementation/validation pending |
| A21 / INPUT-01 | NOT RUN | Implementation/validation pending |
| A22 / INPUT-01/02 | NOT RUN | Implementation/validation pending |
| A23 / INPUT-02 | NOT RUN | Implementation/validation pending |
| A24 / APP-01 | NOT RUN | Implementation/validation pending |
| A25 / APP-01 | NOT RUN | Implementation/validation pending |
| A26 / NAV-01 | NOT RUN | Implementation/validation pending |
| A27 / NAV-01 | NOT RUN | Implementation/validation pending |
| A28 / CTRL-01 | NOT RUN | Implementation/validation pending |
| A29 / CAP-02 | NOT RUN | Implementation/validation pending |
| A30 / CAP-02/03 | NOT RUN | Implementation/validation pending |
| A31 / CFG-01 | NOT RUN | Implementation/validation pending |
| A32 / CLI-01 | NOT RUN | Implementation/validation pending |
| A33 / OBSERVE-01 | NOT RUN | Implementation/validation pending |
| A34 / PERF-01 | NOT RUN | Implementation/validation pending |
| A35 / PERF-01 | NOT RUN | Implementation/validation pending |
| A36 / BUILD-01 | NOT RUN | Implementation/validation pending |
| A37 / BUILD-01 | NOT RUN | Implementation/validation pending |
| A38 / HANDOFF | NOT RUN | Implementation/validation pending |
| A39 / HANDOFF | NOT RUN | Implementation/validation pending |

## Preservation baseline

- `src` Git tree: 070c99be932097c428b3be83a635bb9f749b3283.
- Native extension Git blob: e34e40f0db6be26bdfc867c89e36b897c677acdf.
- Native SHA256: ABE3EF91491C5C53EDA3BC16C63843545942079DEA80E80C8A139671FBEDF721.
- Source master: 45fc36cc4d173fb1e46eac2dcd1be3338157c500.
- origin/master: c2f889336e5c656763ecac76ed54c960b36a666f.
- upstream/master: 69570b424a3b552b4d56ebca062cc412ad105521.
- Rechecked initial worktree: clean; HEAD unchanged. At final compare asset/native tree objects and branch refs; no screenshot capture is needed.
- M0 record-fix recheck executed: `git -C 'C:\Develop\game\WT\AutoNavy_WT' status --porcelain=v1 -uall` produced no output; `git -C 'C:\Develop\game\WT\AutoNavy_WT' rev-parse HEAD master origin/master upstream/master 'HEAD:src' 'HEAD:toolkit/way_search.cp311-win_amd64.pyd'` returned the recorded source/default refs and tree/blob identifiers above. `Get-FileHash toolkit/way_search.cp311-win_amd64.pyd -Algorithm SHA256` matched the recorded native hash in the v2 worktree. This confirms current M0 preservation, not a future final state.
