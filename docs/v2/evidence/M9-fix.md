# M9 scoped launcher safety fix report

Status: DONE; ready for the original reviewer. Commit e4d207e57fb9ade311a8df15ea27da3d218871f9 on feature/v2-modernization, starting at 272be6f1c7cbbae903edbed8db89d3423c70bc2d. All commands ran with explicit working directory C:/Develop/game/WT/AutoNavy_WT-v2. Original checkout was untouched. Shared coordinator records and evidence/m9 were not staged.

## Finding, plan and implementation

Original P1 SPEC/QUALITY FAIL: Resolve-LaunchLayout selected manifestless AutoNavy_WT.dist/AutoNavy_WT.exe or start_prog.dist/start_prog.exe before complete v2 source. Legacy start_prog ignores safe CLI flags and can enter its old main. The reviewer demonstrated resolver selection without executing the legacy program.

Plan executed: write trapped RED regression matrix; remove unsupported layout detection; run scoped GREEN tests; restage the real build3 distribution into a new ZIP; validate fresh extraction from unrelated cwd; preserve artifact identity and return for review. Reviewer-confirmed follow-up scope added a minimal manifest CLI compatibility guard before process invocation: integer schema_version 1 and string launcher_version exactly 2.0.0. Missing, legacy, unsupported or type-coerced values now refuse explicitly. Existing path containment and file-size validation remain; legitimate test manifests now declare the supported contract so the original traversal test still exercises traversal.

Manifestless candidates cannot preempt source, and candidate-only roots refuse without invocation. README/MIGRATION document both boundaries. The version check is compatibility metadata, not executable authentication. Specifically, old AutoNavy default unknown flags generally exit 2, while old --run can reach legacy main; replacing only a wrapper in an otherwise intact old ZIP normally fails wrapper file-size validation. This report does not claim that exact replacement case bypasses validation.

Owned changes: scripts/launcher.ps1, tests/test_launcher.py, README.md, docs/v2/MIGRATION.md and docs/v2/evidence/m9-fix. No Python runtime, compiler, build script, dependencies, native assets or executable bytes changed. No broad style cleanup, live check, legacy executable, driver, game or input operation was performed. Legacy tests use inert non-PE placeholders and a recording Invoke-LoggedProcess replacement; type tests call package validation directly. Earlier M8b checker incident remains separately recorded in historical M8 evidence; it is not erased by this M9 verification.

## Executed verification

The following command tails were executed under the explicit workdir above. Logs in docs/v2/evidence/m9-fix are durable copies of logs/v2 originals.

- `.venv/Scripts/python.exe -m pytest tests/test_launcher.py -k manifestless -q --tb=short`: RED 24 failed, 21 deselected, 12.80s; m9-launcher-red.txt. Both Windows PowerShell 5.1 and PowerShell 7, both old names, source present/absent, default/CheckOnly/replay; no child executed.
- `.venv/Scripts/python.exe -m pytest tests/test_launcher.py tests/test_build_release.py -q --tb=short`: first GREEN 47 passed, 30.39s; m9-launcher-green.txt.
- `.venv/Scripts/python.exe -m pytest tests/test_launcher.py -k incompatible_package_metadata -q --tb=short`: RED 48 failed, 45 deselected, 26.44s; m9-manifest-red.txt. Both shells, six unsupported/missing metadata combinations, default/CheckOnly/replay/--run, trapped child boundary.
- Same focused full command: intermediate GREEN 95 passed, 53.29s; m9-final-launcher-green.txt. Despite its historical filename, this is not the accepted final result.
- `.venv/Scripts/python.exe -m pytest tests/test_launcher.py -k type_coercion -q --tb=short`: RED 2 failed, 93 deselected, 0.74s; m9-version-type-red.txt. Boolean true and single-element version array proved PowerShell coercion required explicit string type checking.
- `.venv/Scripts/python.exe -m pytest tests/test_launcher.py tests/test_build_release.py -q --tb=short`: ACCEPTED FINAL GREEN 97 passed, 53.68s; m9-accepted-launcher-green.txt.
- `.venv/Scripts/python.exe -m ruff check tests/test_launcher.py --output-format concise`: All checks passed; m9-accepted-launcher-lint.txt. Earlier lint logs are intermediate snapshots.
- `git diff --exit-code 272be6f -- autonavy autonavy.py main.py start_prog.py pilot.py runtime_preflight.py scripts/build.ps1 requirements.txt requirements-core.txt requirements-dev.txt requirements-build.txt`: exit 0, proving bounded production change.
- `git diff --check`: exit 0 before untracked evidence was staged. Later cached check reports only original pytest RED output trailing spaces (`E     `); these raw logs were preserved rather than edited. No code whitespace findings.

No whole-suite rerun was necessary for this wrapper-only scope; coordinator independently ran 463 passed in 103.72s on pre-fix 272be6f. That result is distinct from the accepted 97 focused checks here. Authored CI, Linux execution and live acceptance are not claimed.

## Actual final package and extracted verification

Executed:

`powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -SkipCompile -DistributionPath .output/nuitka/autonavy.dist -OutputPath .output/m9-final/AutoNavy_WT-win64.zip`

Exit 0; m9-final-package-stage.txt. SkipCompile reuses the already actually compiled M8b build3 distribution, not a fake ZIP or source Python substitute. No recompile is needed for this external wrapper change. The raw compiled executable SHA is asserted unchanged. Output staging is under .output/m9-final and fresh extraction under .output/m9-final/verified-package.

Executed `.venv/Scripts/python.exe -X utf8 logs/v2/m9_validate_package.py > logs/v2/m9-final-package-validation.txt`, exit 0. The exact verification helper is preserved as docs/v2/evidence/m9-fix/m9_validate_package.py. It verifies extraction destinations, unchanged executable SHA, source/extracted wrapper byte equality and the historical M8 ZIP SHA. It then runs these nine actual extracted-package commands from an unrelated temporary Unicode cwd; full argv, cwd, stdout, stderr and exit codes are in m9-final-extracted-commands.json:

1. Compiled exe --check-config --config configs/default.toml: 0.
2. PowerShell scripts/run.ps1 default: 0.
3. PowerShell scripts/run.ps1 -CheckOnly: 0.
4. Wrapper --dry-run --capture replay --fixture fixtures/smoke --max-frames 3: 0, exactly three frames.
5. Wrapper --unknown-option: 2, forwarded as required.
6. Compiled exe --offline-smoke: 0; actual frozen synthetic capture child and native planner smoke.
7. Wrapper --check-config --config with absolute external Unicode/spaced TOML: 0; explicit external file retained.
8. cmd /d /c extracted batch default: 0.
9. Extracted batch -CheckOnly -NoPause: 0.

AUTONAVY_NO_PAUSE=1 is set for batch verification. No command enabled input or used live capture. The same helper then points the regression fixtures at the extracted launcher and executes 74 trapped guard checks: 24 manifestless layout cases, 48 incompatible manifest cases including --run, and two version-type coercion cases. All passed; m9-final-extracted-guards.json. No legacy executable was executed.

Final artifact identity (m9-final-artifact-hashes.json):

- ZIP .output/m9-final/AutoNavy_WT-win64.zip: 69,007,274 bytes; SHA256 75b364a596df4c7d8a9f2302f4acd58fd1166a8505baf28ba1f05a99f669e4a8.
- Extracted AutoNavy_WT.exe: 30,566,400 bytes; unchanged SHA256 fbe585a2abfc31757fa985095ca196311c1549c5d5f6c66f709cb016d243014c.
- Source and extracted scripts/launcher.ps1: 9,738 bytes; SHA256 c8258a26ee0900b04037aace4f2043d7fa519f0f327ed120cdb05f6f4a47b69b.
- tests/test_launcher.py: SHA256 b299468df3aa06bc0600316f1a70ba1a920aabf103ecd335eb54b832e0c742b3.
- Unchanged scripts/build.ps1: SHA256 9d2517284a9e2098d0b70f807f947dd0a33ac8fd2010a7b6a9efd07a2c000eac.

Historical M8 ZIP remains .output/AutoNavy_WT-win64.zip, SHA256 0a5417badd91c608b0cbcf8dc4f085101cc3379a6b76fefedaf7ff0a5013ea61. Its evidence is unchanged. Intermediate fallback-only archive remains .output/m9-fixed/AutoNavy_WT-win64.zip, SHA256 6f08b22b9c93c4d902edcfaa08720319c0d9f6b78c5cff42ad171660a2c03d9e; intermediate m9-package-stage/m9-artifact-hashes/m9-extracted-* logs deliberately remain separate from final-prefixed artifact evidence.

## Commit and handoff

Executed `git add -- scripts/launcher.ps1 tests/test_launcher.py README.md docs/v2/MIGRATION.md docs/v2/evidence/m9-fix`, followed by `git commit -m "fix: refuse legacy launcher layouts and incompatible package contracts"`.

Final scoped commit: e4d207e57fb9ade311a8df15ea27da3d218871f9. Remaining dirty files are coordinator-owned docs/v2/REVIEW.md, STATUS.md, VERIFICATION.md and untracked evidence/m9. No push/PR/merge/tag/release occurred. Ready for the original reviewer's focused SPEC/QUALITY gate; no unresolved implementation concern identified in this bounded fix.
