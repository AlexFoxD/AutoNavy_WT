# M9 final verification evidence

Pre-fix code checkpoint: 272be6f1c7cbbae903edbed8db89d3423c70bc2d. The whole-branch review subsequently found the legacy executable fallback defect; these passing tests do not imply that defect was safe. The scoped launcher correction and re-review are tracked separately.

Executed in C:\Develop\game\WT\AutoNavy_WT-v2:

```powershell
.venv/Scripts/python.exe -m pytest tests -q --tb=short
.venv/Scripts/python.exe -m ruff check autonavy scripts/benchmark_common.py scripts/benchmark_pipeline.py scripts/benchmark_capture.py scripts/check_environment.py --output-format concise
.venv/Scripts/python.exe -m ruff check autonavy scripts/benchmark_common.py scripts/benchmark_pipeline.py scripts/benchmark_capture.py scripts/check_environment.py --select E9,F --output-format concise
```

- Full suite: 463 passed in103.72s, exit0, no exclusions or warnings; pre-fix-full-tests.txt.
- Expanded default Ruff diagnostic: exit1, 247 style findings:143 E701 compact colon statements,90 E702 semicolon statements,14 E741 short ambiguous variable names. No other rule categories reported. Full output broad-style-lint.txt. This diagnostic was broader than the authored CI gate; no policy suppression or blanket formatting was applied to manufacture a pass. The whole-branch reviewer classified this as nonblocking style debt. Default broad style compliance is not claimed.
- Correctness-focused E9/F checks: all passed, exit0, correctness-lint.txt. M8b's configured scoped lint also passed in its retained report.
- Read-only hash/preservation check:41 build-manifest files (using the separately recorded final staging-script hash) and4 actual artifacts match recorded SHA256 values. Original checkout status is empty; original HEAD/master/origin/master/upstream/master and asset/native identifiers match baseline. Protected src/path.json/native diff is empty. pre-fix-preservation.json. Final package/restaging and preservation check must be appended after the launcher fix.

All tests and code checks in this folder were run after the separately disclosed M8b test-isolation incident. No old executable was run during final review; the fallback defect was established with a resolver-only Test-Path stub.

Final wrapper-only correction: e4d207e. See ../M9-fix.md and ../m9-fix/ for97 accepted focused tests, nine actual final extracted-package commands and74 trapped guards. No compiled Python/build source changed. Final source/artifact preservation in final-preservation.json passes41 build-manifest and6 current artifact/wrapper hashes, with original clean refs/assets/native. Independent whole-branch re-review approves completion. Use the corrected .output/m9-final/AutoNavy_WT-win64.zip, not the historical M8 artifact. Final documentation commit does not change those verified bytes.
