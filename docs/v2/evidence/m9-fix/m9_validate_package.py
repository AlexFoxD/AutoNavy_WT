"""Verify the actual M9 ZIP and trapped extracted-wrapper compatibility boundaries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

root = Path.cwd()
archive = root / '.output/m9-final/AutoNavy_WT-win64.zip'
package = root / '.output/m9-final/verified-package'
assert not package.exists(), 'Use a fresh extraction directory'
with zipfile.ZipFile(archive) as zipped:
    for name in zipped.namelist():
        assert (package / name).resolve().is_relative_to(package.resolve())
    zipped.extractall(package)
exe = package / 'AutoNavy_WT.exe'
wrapper = package / 'scripts/launcher.ps1'
expected_exe = 'fbe585a2abfc31757fa985095ca196311c1549c5d5f6c66f709cb016d243014c'
assert hashlib.sha256(exe.read_bytes()).hexdigest() == expected_exe
assert wrapper.read_bytes() == (root / 'scripts/launcher.ps1').read_bytes()
results = []
with tempfile.TemporaryDirectory(prefix='M9 final unrelated Тест cwd ') as cwd:
    config = Path(cwd) / 'external config with spaces.toml'
    config.write_bytes((package / 'configs/default.toml').read_bytes())
    ps = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(package / 'scripts/run.ps1')]
    commands = [
        ([str(exe), '--check-config', '--config', 'configs/default.toml'], 0),
        (ps, 0), (ps + ['-CheckOnly'], 0),
        (ps + ['--dry-run', '--capture', 'replay', '--fixture', 'fixtures/smoke', '--max-frames', '3'], 0),
        (ps + ['--unknown-option'], 2), ([str(exe), '--offline-smoke'], 0),
        (ps + ['--check-config', '--config', str(config)], 0),
        (['cmd.exe', '/d', '/c', str(package / 'ЗАПУСТИТЬ.bat')], 0),
        (['cmd.exe', '/d', '/c', str(package / 'ЗАПУСТИТЬ.bat'), '-CheckOnly', '-NoPause'], 0),
    ]
    for command, expected in commands:
        result = subprocess.run(command, cwd=cwd, env=dict(os.environ, AUTONAVY_NO_PAUSE='1'), capture_output=True, text=True, encoding='utf-8-sig', errors='replace', timeout=60)
        results.append(dict(command=command, cwd=cwd, expected=expected, exit=result.returncode, stdout=result.stdout, stderr=result.stderr))
        (root / 'logs/v2/m9-final-extracted-commands.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        assert result.returncode == expected, results[-1]
    assert 'frames=3' in results[3]['stdout']
    assert str(config) in results[6]['stdout']
print('Nine final extracted-package commands passed.', flush=True)
spec = importlib.util.spec_from_file_location('m9_launcher_regression', root / 'tests/test_launcher.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.LAUNCHER_SCRIPT = wrapper
cases = []
for shell in ['powershell.exe'] + (['pwsh.exe'] if shutil.which('pwsh.exe') else []):
    for candidate in ['AutoNavy_WT.dist/AutoNavy_WT.exe', 'start_prog.dist/start_prog.exe']:
        for has_source in [False, True]:
            for arguments, expected in [([], ['--check-config']), (['-CheckOnly'], ['--check-config']), (['--dry-run', '--capture', 'replay', '--fixture', 'fixtures/smoke', '--max-frames', '3'], ['--dry-run', '--capture', 'replay', '--fixture', 'fixtures/smoke', '--max-frames', '3'])]:
                with tempfile.TemporaryDirectory(prefix='M9 final trapped fallback ') as directory:
                    module.test_manifestless_legacy_candidates_never_execute(Path(directory), shell, candidate, has_source, arguments, expected)
                cases.append(dict(boundary='manifestless', shell=shell, candidate=candidate, source=has_source, arguments=arguments, result='PASS', all_child_calls_trapped=True))
    for metadata in [
        {'schema_version': 1, 'launcher_version': '1.0.0'}, {'schema_version': 1},
        {'schema_version': 1, 'launcher_version': '3.0.0'}, {'launcher_version': '2.0.0'},
        {'schema_version': 2, 'launcher_version': '2.0.0'}, {'schema_version': '1', 'launcher_version': '2.0.0'},
    ]:
        for arguments in [[], ['-CheckOnly'], ['--dry-run', '--capture', 'replay', '--fixture', 'fixtures/smoke'], ['--run']]:
            with tempfile.TemporaryDirectory(prefix='M9 final trapped manifest ') as directory:
                module.test_incompatible_package_metadata_never_reaches_process(Path(directory), shell, metadata, arguments)
            cases.append(dict(boundary='manifest-version', shell=shell, metadata=metadata, arguments=arguments, result='PASS', all_child_calls_trapped=True))
for version in [True, ['2.0.0']]:
    with tempfile.TemporaryDirectory(prefix='M9 final version type ') as directory:
        module.test_package_version_does_not_use_powershell_type_coercion(Path(directory), version)
    cases.append(dict(boundary='version-type', version=version, result='PASS', resolver_only=True))
(root / 'logs/v2/m9-final-extracted-guards.json').write_text(json.dumps(cases, indent=2), encoding='utf-8')
print('Extracted wrapper guards:', len(cases), 'passed; legacy processes never executed.', flush=True)
files = [archive, exe, wrapper, root / 'scripts/launcher.ps1', root / 'tests/test_launcher.py', root / 'scripts/build.ps1']
hashes = {str(path.relative_to(root)): dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size) for path in files}
hashes['historical_m8_zip_unchanged'] = hashlib.sha256((root / '.output/AutoNavy_WT-win64.zip').read_bytes()).hexdigest() == '0a5417badd91c608b0cbcf8dc4f085101cc3379a6b76fefedaf7ff0a5013ea61'
assert hashes['historical_m8_zip_unchanged']
(root / 'logs/v2/m9-final-artifact-hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
print(json.dumps(hashes, indent=2), flush=True)
