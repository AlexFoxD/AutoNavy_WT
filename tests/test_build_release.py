import ctypes
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build.ps1"
VJOY_RUNTIME_DLL = PROJECT_ROOT / "third_party" / "vjoy" / "2.1.9.1" / "x64" / "vJoyInterface.dll"


class ReleasePackagingTests(unittest.TestCase):
    def test_vendored_vjoy_sdk_matches_winget_driver_version(self):
        self.assertTrue(VJOY_RUNTIME_DLL.is_file(), VJOY_RUNTIME_DLL)
        dll = ctypes.CDLL(str(VJOY_RUNTIME_DLL))
        dll.GetvJoyVersion.restype = ctypes.c_ushort

        self.assertEqual(0x219, dll.GetvJoyVersion())

    def test_package_contains_one_click_runtime_without_development_files(self):
        with tempfile.TemporaryDirectory(prefix="AutoNavy build test ") as directory:
            temporary = Path(directory)
            distribution = temporary / "fresh standalone.dist"
            distribution.mkdir()
            (distribution / "AutoNavy_WT.exe").write_bytes(b"standalone executable")
            (distribution / "python311.dll").write_bytes(b"runtime dll")
            (distribution / "way_search.pyd").write_bytes(b"native module")
            (distribution / "ignored.build").mkdir()
            (distribution / "ignored.build" / "cache.obj").write_bytes(b"cache")
            pyvjoy_dll = temporary / "vJoyInterface.dll"
            pyvjoy_dll.write_bytes(b"vjoy sdk runtime")
            archive = temporary / "AutoNavy_WT-win64.zip"

            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(BUILD_SCRIPT),
                    "-SkipCompile",
                    "-DistributionPath",
                    str(distribution),
                    "-OutputPath",
                    str(archive),
                    "-PyVJoyDllPath",
                    str(pyvjoy_dll),
                ],
                cwd=temporary,
                capture_output=True,
                timeout=120,
            )
            stderr = completed.stderr.decode("utf-8-sig", errors="replace")
            self.assertEqual(0, completed.returncode, stderr)

            with zipfile.ZipFile(archive) as package:
                names = set(package.namelist())
                manifest = json.loads(package.read("release-manifest.json"))

        expected = {
            "ЗАПУСТИТЬ.bat",
            "scripts/launcher.ps1",
            "AutoNavy_WT.exe",
            "python311.dll",
            "way_search.pyd",
            "pyvjoy/utils/x64/vJoyInterface.dll",
            "path.json",
            "README.md",
            "src/game_image/start.png",
            "release-manifest.json",
        }
        self.assertTrue(expected.issubset(names), expected - names)
        self.assertFalse(any(".venv" in name for name in names))
        self.assertFalse(any("tests/" in name for name in names))
        self.assertFalse(any("ignored.build" in name for name in names))
        self.assertEqual("AutoNavy_WT.exe", manifest["executable"])
        required = {entry["path"] for entry in manifest["required_files"]}
        self.assertIn("src/game_image/start.png", required)
        self.assertIn("python311.dll", required)
        self.assertIn("pyvjoy/utils/x64/vJoyInterface.dll", required)
        entries = {entry["path"]: entry for entry in manifest["required_files"]}
        self.assertIsNone(entries["path.json"]["size"])
        self.assertIsNone(entries["src/origin_map.png"]["size"])


if __name__ == "__main__":
    unittest.main()
