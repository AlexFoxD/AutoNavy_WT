# Verification evidence

Environment: Windows, project-local CPython 3.11 x64. Source 45fc36cc4d173fb1e46eac2dcd1be3338157c500. No live input or game startup is authorized for verification.

Current stage: baseline setup. Acceptance rows have not yet been implemented or verified. The complete A01-A39 matrix is in SPEC.md and will be maintained here as milestones produce evidence.

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
| A01 / GIT-01 | NOT RUN | Implementation/validation pending |
| A02 / AUDIT-01 | NOT RUN | Implementation/validation pending |
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
