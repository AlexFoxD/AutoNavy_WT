import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path


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
