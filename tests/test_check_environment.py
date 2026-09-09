import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_environment.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_environment", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EnvironmentCheckTests(unittest.TestCase):
    def test_rejects_non_windows_platform(self):
        checker = load_checker()

        result = checker.check_platform("linux")

        self.assertFalse(result.ok)
        self.assertIn("Windows", result.message)

    def test_rejects_wrong_python_minor(self):
        checker = load_checker()

        result = checker.check_python_version((3, 12, 0))

        self.assertFalse(result.ok)
        self.assertIn("3.11", result.message)

    def test_rejects_32_bit_python(self):
        checker = load_checker()

        result = checker.check_python_architecture(4)

        self.assertFalse(result.ok)
        self.assertIn("64", result.message)

    def test_reports_missing_required_file(self):
        checker = load_checker()

        result = checker.check_required_file(Path("Z:/definitely-missing"), "test.dat")

        self.assertFalse(result.ok)
        self.assertIn("test.dat", result.message)

    def test_reports_directory_without_image_resources(self):
        checker = load_checker()

        with tempfile.TemporaryDirectory() as directory:
            result = checker.check_image_resources(Path(directory))

        self.assertFalse(result.ok)
        self.assertIn("PNG", result.message)

    def test_image_scan_ignores_generated_output_directories(self):
        checker = load_checker()

        class Resources:
            @staticmethod
            def read_image(path):
                return object() if Path(path).is_file() else None

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "module.py").write_text("cv2.imread('src/image.png')", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "image.png").write_bytes(b"fixture")
            (root / ".output").mkdir()
            (root / ".output" / "foreign_encoding.py").write_bytes(b"# coding: latin-1\n# \xe4")
            (root / "tests").mkdir()
            (root / "tests" / "test_fixture.py").write_text(
                "cv2.imread('src/not-a-runtime-resource.png')", encoding="utf-8"
            )

            with mock.patch.object(checker.importlib, "import_module", return_value=Resources()):
                result = checker.check_image_resources(root)

        self.assertTrue(result.ok)

    def test_current_interpreter_matches_bundled_abi(self):
        checker = load_checker()

        version = checker.check_python_version(sys.version_info)
        architecture = checker.check_python_architecture(struct.calcsize("P"))

        self.assertTrue(version.ok)
        self.assertTrue(architecture.ok)

    def test_configures_utf8_output_when_supported(self):
        checker = load_checker()

        class Stream:
            def __init__(self):
                self.options = None

            def reconfigure(self, **options):
                self.options = options

        stream = Stream()
        checker.configure_utf8_output(stream)

        self.assertEqual({"encoding": "utf-8", "errors": "replace"}, stream.options)


if __name__ == "__main__":
    unittest.main()


def test_core_readiness_never_imports_hardware_and_runs_on_linux():
    checker = load_checker()
    root = CHECKER_PATH.parents[1]
    real_import = checker.importlib.import_module
    def guarded(name, *args, **kwargs):
        assert name.split('.')[0] not in {'dxcam', 'pyvjoy', 'win32api', 'win32gui', 'keyboard', 'pydirectinput', 'runtime_preflight'}
        return real_import(name, *args, **kwargs)
    with mock.patch.object(checker.sys, 'platform', 'linux'), mock.patch.object(checker.importlib, 'import_module', side_effect=guarded):
        results = checker.run_checks(root)
    assert all(r.ok for r in results), results


def test_static_readiness_reports_missing_pinned_dependency_without_import():
    checker = load_checker()
    with mock.patch('importlib.metadata.version', side_effect=__import__('importlib.metadata', fromlist=['PackageNotFoundError']).PackageNotFoundError), mock.patch.object(checker, 'check_import', side_effect=AssertionError('Native imports forbidden')), mock.patch.object(checker, 'check_vjoy_driver', side_effect=AssertionError('Driver access forbidden')):
        results = checker.run_checks(CHECKER_PATH.parents[1])
    assert any(not r.ok and 'numpy' in r.message for r in results), results
