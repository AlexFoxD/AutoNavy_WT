import json
import ctypes
import tempfile
import unittest
from pathlib import Path

import runtime_preflight


class FakeVJoyApi:
    def __init__(
        self,
        *,
        enabled=True,
        driver_matches=True,
        status=1,
        axes=("X", "Y", "Z", "RY"),
        buttons=8,
        acquire=True,
    ):
        self.enabled = enabled
        self._driver_matches = driver_matches
        self.status = status
        self.axes = set(axes)
        self.buttons = buttons
        self.acquire_result = acquire
        self.acquired = False
        self.relinquished = False

    def is_enabled(self):
        return self.enabled

    def driver_matches(self):
        return self._driver_matches

    def get_status(self, device_id):
        self.requested_device_id = device_id
        return self.status

    def axis_exists(self, device_id, axis_name):
        return axis_name in self.axes

    def button_count(self, device_id):
        return self.buttons

    def acquire(self, device_id):
        self.acquired = True
        return self.acquire_result

    def relinquish(self, device_id):
        self.relinquished = True


class VJoyPreflightTests(unittest.TestCase):
    def test_reports_missing_driver_in_russian(self):
        result = runtime_preflight.check_vjoy(FakeVJoyApi(enabled=False))

        self.assertFalse(result.ok)
        self.assertEqual("vjoy_not_installed", result.code)
        self.assertIn("vJoy не установлен", result.message)

    def test_reports_missing_device_one(self):
        result = runtime_preflight.check_vjoy(FakeVJoyApi(status=3))

        self.assertFalse(result.ok)
        self.assertEqual("vjoy_device_missing", result.code)
        self.assertIn("Устройство vJoy № 1 не создано", result.message)

    def test_reports_busy_device_one_without_acquiring(self):
        api = FakeVJoyApi(status=2)

        result = runtime_preflight.check_vjoy(api)

        self.assertFalse(result.ok)
        self.assertEqual("vjoy_device_busy", result.code)
        self.assertIn("занято другой программой", result.message)
        self.assertFalse(api.acquired)

    def test_reports_each_missing_required_axis(self):
        result = runtime_preflight.check_vjoy(FakeVJoyApi(axes=("X", "Y", "Z")))

        self.assertFalse(result.ok)
        self.assertEqual("vjoy_axis_missing", result.code)
        self.assertIn("RY", result.message)

    def test_reports_too_few_buttons(self):
        result = runtime_preflight.check_vjoy(FakeVJoyApi(buttons=7))

        self.assertFalse(result.ok)
        self.assertEqual("vjoy_buttons_missing", result.code)
        self.assertIn("не менее 8 кнопок", result.message)

    def test_checks_configured_device_without_acquiring_or_relinquishing(self):
        api = FakeVJoyApi()

        result = runtime_preflight.check_vjoy(api)

        self.assertTrue(result.ok)
        self.assertEqual("vjoy_ready", result.code)
        self.assertEqual(1, api.requested_device_id)
        self.assertFalse(api.acquired)
        self.assertFalse(api.relinquished)


class PyVJoyApiTests(unittest.TestCase):
    def test_driver_match_passes_version_pointers_to_native_dll(self):
        class NativeDriverMatch:
            def __init__(self):
                self.argtypes = None
                self.restype = None
                self.calls = 0

            def __call__(self, dll_version, driver_version):
                self.calls += 1
                ctypes.cast(dll_version, ctypes.POINTER(ctypes.c_ushort)).contents.value = 0x219
                ctypes.cast(driver_version, ctypes.POINTER(ctypes.c_ushort)).contents.value = 0x219
                return True

        native_driver_match = NativeDriverMatch()
        api = runtime_preflight.PyVJoyApi.__new__(runtime_preflight.PyVJoyApi)
        api.dll = type("NativeDll", (), {"DriverMatch": native_driver_match})()
        api.sdk = type("BrokenPyVJoySdk", (), {"DriverMatch": lambda self: False})()

        self.assertTrue(api.driver_matches())
        self.assertEqual(1, native_driver_match.calls)


class ResourcePreflightTests(unittest.TestCase):
    def test_reports_invalid_path_json_in_russian(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "path.json").write_text("{broken", encoding="utf-8")

            result = runtime_preflight.check_path_json(root)

        self.assertFalse(result.ok)
        self.assertEqual("path_json_invalid", result.code)
        self.assertIn("path.json повреждён", result.message)

    def test_accepts_current_path_json_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = {"start_point": [1, 2], "end_point": [3, 4], "path": [[1, 2]]}
            (root / "path.json").write_text(json.dumps(payload), encoding="utf-8")

            result = runtime_preflight.check_path_json(root)

        self.assertTrue(result.ok)

    def test_reports_missing_image_resource_by_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            result = runtime_preflight.check_image_resources(root, lambda _path: object())

        self.assertFalse(result.ok)
        self.assertEqual("resource_missing", result.code)
        self.assertIn("src", result.message)

    def test_reports_native_module_import_failure_without_raw_traceback(self):
        def failing_import(name):
            if name == "toolkit.way_search":
                raise ImportError("DLL load failed: secret technical detail")
            return object()

        result = runtime_preflight.check_runtime_imports(failing_import)

        self.assertFalse(result.ok)
        self.assertEqual("runtime_import_failed", result.code)
        self.assertIn("toolkit.way_search", result.message)
        self.assertNotIn("secret technical detail", result.message)
        self.assertIn("secret technical detail", result.detail)


class ScreenCapturePreflightTests(unittest.TestCase):
    def test_initializes_grabs_and_releases_dxcam_without_starting_capture(self):
        class Camera:
            def __init__(self):
                self.grabbed = False
                self.released = False

            def grab(self):
                self.grabbed = True
                return object()

            def release(self):
                self.released = True

        camera = Camera()

        result = runtime_preflight.check_screen_capture(lambda: camera)

        self.assertTrue(result.ok)
        self.assertTrue(camera.grabbed)
        self.assertTrue(camera.released)


class WarThunderPreflightTests(unittest.TestCase):
    def test_distinguishes_game_not_running(self):
        state = runtime_preflight.GameState(False, 0, None, None)

        result = runtime_preflight.check_war_thunder(state)

        self.assertFalse(result.ok)
        self.assertEqual("game_not_running", result.code)
        self.assertIn("War Thunder не запущен", result.message)

    def test_distinguishes_running_game_without_expected_window(self):
        state = runtime_preflight.GameState(True, 0, None, None)

        result = runtime_preflight.check_war_thunder(state)

        self.assertFalse(result.ok)
        self.assertEqual("game_window_missing", result.code)
        self.assertIn("DagorWClass", result.message)

    def test_rejects_wrong_client_size_with_required_settings(self):
        state = runtime_preflight.GameState(True, 100, (1920, 1080), 96)

        result = runtime_preflight.check_war_thunder(state)

        self.assertFalse(result.ok)
        self.assertEqual("game_window_size", result.code)
        self.assertIn("1280×720", result.message)

    def test_accepts_expected_window_size_and_dpi(self):
        state = runtime_preflight.GameState(True, 100, (1280, 720), 96)

        result = runtime_preflight.check_war_thunder(state)

        self.assertTrue(result.ok)


class ApiPreflightTests(unittest.TestCase):
    def test_api_unavailable_is_a_nonfatal_game_state_warning(self):
        def unavailable(*_args, **_kwargs):
            raise OSError("connection refused")

        result = runtime_preflight.check_war_thunder_api(unavailable)

        self.assertFalse(result.ok)
        self.assertTrue(result.warning)
        self.assertEqual("game_api_unavailable", result.code)
        self.assertIn("локальный API", result.message)


class PreflightSummaryTests(unittest.TestCase):
    def test_successful_simulated_preflight_has_zero_exit_code(self):
        results = [
            runtime_preflight.CheckResult(True, "runtime_ready", "Среда готова."),
            runtime_preflight.CheckResult(True, "vjoy_ready", "vJoy готов."),
            runtime_preflight.CheckResult(True, "game_ready", "War Thunder готов."),
        ]

        exit_code, summary = runtime_preflight.summarize_results(results)

        self.assertEqual(0, exit_code)
        self.assertIn("Проверка завершена успешно", summary)

    def test_status_file_parent_is_created(self):
        results = [runtime_preflight.CheckResult(True, "ready", "Готово.")]
        with tempfile.TemporaryDirectory() as directory:
            status_path = Path(directory) / "new logs" / "status.json"

            runtime_preflight.write_status_file(status_path, results, 0)

            payload = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertEqual(0, payload["exit_code"])


if __name__ == "__main__":
    unittest.main()


def test_runtime_preflight_checks_only_retained_runtime_dependencies():
    assert not {'scipy', 'matplotlib', 'simple_pid'} & set(runtime_preflight.REQUIRED_IMPORTS)
    assert {'cv2', 'numpy', 'dxcam', 'pyvjoy', 'toolkit.way_search'} <= set(runtime_preflight.REQUIRED_IMPORTS)
