import json
import os
import subprocess
import sys
import tempfile
import unittest
import shutil
from pathlib import Path
import pytest

if sys.platform == "win32":
    import winreg

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Real Windows PowerShell/cmd/registry integration")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_SCRIPT = PROJECT_ROOT / "scripts" / "launcher.ps1"
LAUNCHER_BATCH = PROJECT_ROOT / "ЗАПУСТИТЬ.bat"


def run_powershell(command: str, cwd: Path | None = None, shell="powershell.exe"):
    completed = subprocess.run(
        [
            shell,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        cwd=cwd,
        capture_output=True,
    )
    stdout = completed.stdout.decode("utf-8-sig", errors="replace")
    stderr = completed.stderr.decode("utf-8-sig", errors="replace")
    return completed.returncode, stdout, stderr


def ps_literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


class LauncherLayoutTests(unittest.TestCase):
    def make_release(self, root: Path, required_files: list[dict]):
        manifest = {
            "schema_version": 1,
            "launcher_version": "2.0.0",
            "executable": "AutoNavy_WT.exe",
            "required_files": required_files,
        }
        (root / "release-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

    def invoke_json(self, root: Path, expression: str):
        command = (
            f". {ps_literal(LAUNCHER_SCRIPT)}; "
            f"{expression} | ConvertTo-Json -Depth 6 -Compress"
        )
        code, stdout, stderr = run_powershell(command, cwd=Path(tempfile.gettempdir()))
        self.assertEqual(0, code, stderr)
        return json.loads(stdout.strip().splitlines()[-1])

    def test_selects_standalone_from_manifest_in_path_with_spaces_and_cyrillic(self):
        with tempfile.TemporaryDirectory(prefix="AutoNavy WT Тест ") as directory:
            root = Path(directory)
            (root / "AutoNavy_WT.exe").write_bytes(b"exe")
            self.make_release(root, [{"path": "AutoNavy_WT.exe", "size": 3}])

            layout = self.invoke_json(root, f"Resolve-LaunchLayout -Root {ps_literal(root)}")

        self.assertEqual("Standalone", layout["Mode"])
        self.assertEqual(str(root / "AutoNavy_WT.exe"), layout["ExecutablePath"])

    def test_selects_source_checkout_when_no_standalone_exists(self):
        with tempfile.TemporaryDirectory(prefix="AutoNavy source ") as directory:
            root = Path(directory)
            (root / "autonavy.py").write_text("", encoding="utf-8")
            (root / "requirements.txt").write_text("", encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "scripts" / "install.ps1").write_text("", encoding="utf-8")

            layout = self.invoke_json(root, f"Resolve-LaunchLayout -Root {ps_literal(root)}")

        self.assertEqual("Source", layout["Mode"])

    def test_missing_standalone_executable_is_reported_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_release(root, [{"path": "AutoNavy_WT.exe", "size": 3}])

            result = self.invoke_json(
                root,
                f"Test-ReleasePackage -Root {ps_literal(root)} "
                f"-ManifestPath {ps_literal(root / 'release-manifest.json')}",
            )

        self.assertFalse(result["Ok"])
        self.assertIn("AutoNavy_WT.exe", result["Missing"])

    def test_missing_release_resource_is_reported_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AutoNavy_WT.exe").write_bytes(b"exe")
            self.make_release(
                root,
                [
                    {"path": "AutoNavy_WT.exe", "size": 3},
                    {"path": "src/game_image/start.png", "size": 10},
                ],
            )

            result = self.invoke_json(
                root,
                f"Test-ReleasePackage -Root {ps_literal(root)} "
                f"-ManifestPath {ps_literal(root / 'release-manifest.json')}",
            )

        self.assertFalse(result["Ok"])
        self.assertIn("src/game_image/start.png", result["Missing"])
        self.assertIn("Incomplete release", result["Message"])

    def test_resolves_layout_independently_of_current_working_directory(self):
        with tempfile.TemporaryDirectory(prefix="unrelated cwd "):
            root = PROJECT_ROOT
            layout = self.invoke_json(root, f"Resolve-LaunchLayout -Root {ps_literal(root)}")

        self.assertEqual("Source", layout["Mode"])
        self.assertEqual(str(PROJECT_ROOT), layout["Root"])


class LauncherPolicyTests(unittest.TestCase):
    def read_policy(self):
        locations = (
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\PowerShell\1\ShellIds\Microsoft.PowerShell"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\PowerShell\1\ShellIds\Microsoft.PowerShell"),
            (winreg.HKEY_CURRENT_USER, r"Software\Policies\Microsoft\Windows\PowerShell"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Policies\Microsoft\Windows\PowerShell"),
        )
        values = []
        for hive, key_path in locations:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    value = winreg.QueryValueEx(key, "ExecutionPolicy")[0]
            except FileNotFoundError:
                value = None
            values.append(value)
        return values

    def test_batch_launcher_does_not_permanently_change_execution_policy(self):
        before = self.read_policy()
        environment = os.environ.copy()
        environment["AUTONAVY_NO_PAUSE"] = "1"
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", str(LAUNCHER_BATCH), "-CheckOnly", "-NoPause"],
            cwd=Path(tempfile.gettempdir()),
            env=environment,
            capture_output=True,
            timeout=120,
        )
        after = self.read_policy()

        self.assertEqual(before, after)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)


class LauncherProcessTests(unittest.TestCase):
    def test_native_stderr_is_logged_without_aborting_before_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = (
                f". {ps_literal(LAUNCHER_SCRIPT)}; "
                f"Initialize-LauncherLog -Root {ps_literal(root)}; "
                f"$code = Invoke-LoggedProcess -FilePath {ps_literal(Path(sys.executable))} "
                "-Arguments @('-c', \"import sys; sys.stderr.write('native warning\\n'); sys.exit(2)\") "
                "-HideConsoleOutput; "
                "[PSCustomObject]@{ Code = $code; Log = $script:LauncherLogPath } | ConvertTo-Json -Compress"
            )
            code, stdout, stderr = run_powershell(command)

            self.assertEqual(0, code, stderr)
            payload = json.loads(stdout.strip().splitlines()[-1])
            log_text = Path(payload["Log"]).read_text(encoding="utf-8-sig")

        self.assertEqual(2, payload["Code"])
        self.assertIn("native warning", log_text)


if __name__ == "__main__":
    unittest.main()


@pytest.mark.parametrize("shell", ["powershell.exe"] + (["pwsh.exe"] if shutil.which("pwsh.exe") else []))
@pytest.mark.parametrize("wrapper", ["launcher.ps1", "run.ps1"])
@pytest.mark.parametrize("arguments, expected, expected_code", [
    (["-CheckOnly"], ["--check-config"], 0),
    ([], ["--check-config"], 0),
    (["--config", "a spaced Тест.toml", "--unknown", "", 'a"b', "tail\\"],
     ["--config", "a spaced Тест.toml", "--unknown", "", 'a"b', "tail\\"], 17),
])
def test_isolated_wrapper_is_offline_and_forwards_exact_argv(tmp_path, shell, wrapper, arguments, expected, expected_code):
    root = tmp_path / "source Тест with spaces"
    (root / "scripts").mkdir(parents=True)
    for name in ("launcher.ps1", "run.ps1"):
        shutil.copy(PROJECT_ROOT / "scripts" / name, root / "scripts" / name)
    (root / "requirements.txt").write_text("")
    (root / "scripts/install.ps1").write_text("throw 'INSTALL IS FORBIDDEN'")
    (root / "scripts/check_environment.py").write_text("raise RuntimeError('CHECKER IS FORBIDDEN')")
    # Junction uses the running test interpreter without copying a Python installation.
    venv = root / ".venv"
    venv.mkdir()
    source = Path(sys.executable).parent
    shutil.copy(source.parent / "pyvenv.cfg", venv / "pyvenv.cfg")
    link_code, _, link_error = run_powershell(
        f"New-Item -ItemType Junction -Path {ps_literal(venv / 'Scripts')} -Target {ps_literal(source)} | Out-Null")
    assert link_code == 0, link_error
    record = root / "argv.json"
    (root / "autonavy.py").write_text(
        "import json,sys\nfrom pathlib import Path\n"
        f"Path({str(record)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "raise SystemExit(0 if sys.argv[1:]==['--check-config'] else 17)\n", encoding="utf-8")
    ps_args = " ".join(a if a == "-CheckOnly" else "'" + a.replace("'", "''") + "'" for a in arguments)
    code, stdout, stderr = run_powershell(
        f"& {ps_literal(root / 'scripts' / wrapper)} {ps_args}; exit $LASTEXITCODE", cwd=tmp_path, shell=shell)
    assert code == expected_code, stdout + stderr
    assert json.loads(record.read_text()) == expected


def test_installer_refuses_to_delete_incomplete_environment(tmp_path):
    root = tmp_path / 'install source'
    (root / 'scripts').mkdir(parents=True)
    shutil.copy(PROJECT_ROOT / 'scripts/install.ps1', root / 'scripts/install.ps1')
    (root / '.venv').mkdir()
    marker = root / '.venv/keep.txt'
    marker.write_text('user data')
    code, out, err = run_powershell(f"& {ps_literal(root/'scripts/install.ps1')} -Mode Core")
    assert code != 0
    assert 'incomplete' in out + err
    assert marker.read_text() == 'user data'


def test_release_manifest_cannot_select_executable_outside_package(tmp_path):
    manifest = tmp_path / 'release-manifest.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'launcher_version': '2.0.0',
                                    'executable': '../outside.exe', 'required_files': []}))
    code, out, err = run_powershell(
        f". {ps_literal(LAUNCHER_SCRIPT)}; Test-ReleasePackage -Root {ps_literal(tmp_path)} -ManifestPath {ps_literal(manifest)} | ConvertTo-Json -Compress")
    assert code == 0, err
    assert json.loads(out)['Ok'] is False


@pytest.mark.parametrize("shell", ["powershell.exe"] + (["pwsh.exe"] if shutil.which("pwsh.exe") else []))
@pytest.mark.parametrize("candidate", ["AutoNavy_WT.dist/AutoNavy_WT.exe", "start_prog.dist/start_prog.exe"])
@pytest.mark.parametrize("has_source", [False, True])
@pytest.mark.parametrize("arguments, expected", [
    ([], ["--check-config"]),
    (["-CheckOnly"], ["--check-config"]),
    (["--dry-run", "--capture", "replay", "--fixture", "fixtures/smoke", "--max-frames", "3"],
     ["--dry-run", "--capture", "replay", "--fixture", "fixtures/smoke", "--max-frames", "3"]),
])
def test_manifestless_legacy_candidates_never_execute(tmp_path, shell, candidate, has_source, arguments, expected):
    root = tmp_path / 'launcher safety fixture'
    (root / 'scripts').mkdir(parents=True)
    shutil.copy(LAUNCHER_SCRIPT, root / 'scripts/launcher.ps1')
    executable = root / candidate
    executable.parent.mkdir()
    executable.write_bytes(b'INERT PLACEHOLDER: NEVER EXECUTE')
    if has_source:
        (root / 'autonavy.py').write_text('# inert source layout marker')
        (root / 'requirements.txt').write_text('')
        (root / 'scripts/install.ps1').write_text("throw 'INSTALL FORBIDDEN'")
        (root / '.venv/Scripts').mkdir(parents=True)
        (root / '.venv/Scripts/python.exe').write_bytes(b'INERT PLACEHOLDER: NEVER EXECUTE')
    ps_args = ', '.join("'" + value.replace("'", "''") + "'" for value in arguments)
    # Trap every possible child boundary, including the defective legacy path.
    # Neither placeholder executable nor the source entrypoint is ever invoked.
    command = (
        f". {ps_literal(root/'scripts/launcher.ps1')}; "
        "$script:Calls = @(); "
        "function Invoke-LoggedProcess { param([string]$FilePath, [string[]]$Arguments) "
        "$script:Calls += [PSCustomObject]@{ File = $FilePath; Arguments = @($Arguments) }; return 0 }; "
        f"try {{ $mode = (Resolve-LaunchLayout -Root {ps_literal(root)}).Mode }} catch {{ $mode = 'Refused' }}; "
        f"$result = Invoke-Launcher -CliArguments @({ps_args}); "
        "[PSCustomObject]@{ Mode = $mode; Code = $result; Calls = @($script:Calls) } | ConvertTo-Json -Depth 6 -Compress"
    )
    code, stdout, stderr = run_powershell(command, cwd=tmp_path, shell=shell)
    assert code == 0, stdout + stderr
    payload = json.loads(stdout.strip().splitlines()[-1])
    assert payload['Mode'] == ('Source' if has_source else 'Refused'), payload
    assert payload['Code'] == (0 if has_source else 3), payload
    if has_source:
        assert payload['Calls'] == [{
            'File': str(root/'.venv/Scripts/python.exe'),
            'Arguments': [str(root/'autonavy.py'), *expected],
        }]
    else:
        assert payload['Calls'] == []


@pytest.mark.parametrize("shell", ["powershell.exe"] + (["pwsh.exe"] if shutil.which("pwsh.exe") else []))
@pytest.mark.parametrize("metadata", [
    {"schema_version": 1, "launcher_version": "1.0.0"},
    {"schema_version": 1},
    {"schema_version": 1, "launcher_version": "3.0.0"},
    {"launcher_version": "2.0.0"},
    {"schema_version": 2, "launcher_version": "2.0.0"},
    {"schema_version": "1", "launcher_version": "2.0.0"},
])
@pytest.mark.parametrize("arguments", [[], ["-CheckOnly"], ["--dry-run", "--capture", "replay", "--fixture", "fixtures/smoke"], ["--run"]])
def test_incompatible_package_metadata_never_reaches_process(tmp_path, shell, metadata, arguments):
    root = tmp_path / 'incompatible package'
    (root / 'scripts').mkdir(parents=True)
    launcher = root / 'scripts/launcher.ps1'
    shutil.copy(LAUNCHER_SCRIPT, launcher)
    executable = root / 'AutoNavy_WT.exe'
    executable.write_bytes(b'INERT PLACEHOLDER: NEVER EXECUTE')
    manifest = dict(metadata, executable='AutoNavy_WT.exe', required_files=[
        {'path': 'AutoNavy_WT.exe', 'size': executable.stat().st_size},
        {'path': 'scripts/launcher.ps1', 'size': launcher.stat().st_size},
    ])
    (root / 'release-manifest.json').write_text(json.dumps(manifest))
    ps_args = ', '.join("'" + value.replace("'", "''") + "'" for value in arguments)
    command = (
        f". {ps_literal(launcher)}; $script:Calls = @(); "
        "function Invoke-LoggedProcess { param([string]$FilePath, [string[]]$Arguments) "
        "$script:Calls += $FilePath; return 0 }; "
        f"$result = Invoke-Launcher -CliArguments @({ps_args}); "
        "[PSCustomObject]@{ Code = $result; Calls = @($script:Calls) } | ConvertTo-Json -Compress"
    )
    code, stdout, stderr = run_powershell(command, cwd=tmp_path, shell=shell)
    assert code == 0, stdout + stderr
    payload = json.loads(stdout.strip().splitlines()[-1])
    assert payload == {'Code': 3, 'Calls': []}, payload
    assert 'Incompatible package' in stdout


@pytest.mark.parametrize("version", [True, ["2.0.0"]])
def test_package_version_does_not_use_powershell_type_coercion(tmp_path, version):
    executable = tmp_path / 'AutoNavy_WT.exe'
    executable.write_bytes(b'INERT')
    manifest = tmp_path / 'release-manifest.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'launcher_version': version,
                                    'executable': 'AutoNavy_WT.exe',
                                    'required_files': [{'path': 'AutoNavy_WT.exe', 'size': 5}]}))
    code, out, err = run_powershell(
        f". {ps_literal(LAUNCHER_SCRIPT)}; Test-ReleasePackage -Root {ps_literal(tmp_path)} -ManifestPath {ps_literal(manifest)} | ConvertTo-Json -Compress")
    assert code == 0, err
    payload = json.loads(out)
    assert payload['Ok'] is False
    assert 'Incompatible package' in payload['Message']
