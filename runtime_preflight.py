"""Safe runtime readiness checks for AutoNavy_WT.

This module must never send keyboard, mouse, or virtual joystick input.
"""

from __future__ import annotations

import ctypes
import json
import importlib
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


VJOY_DEVICE_ID = 1
VJOY_REQUIRED_AXES = ("X", "Y", "Z", "RY")
VJOY_REQUIRED_BUTTONS = 8
REQUIRED_IMPORTS = (
    "cv2",
    "dxcam",
    "keyboard",
    "matplotlib",
    "numpy",
    "pydirectinput",
    "pyvjoy",
    "requests",
    "scipy",
    "simple_pid",
    "win32api",
    "win32gui",
    "toolkit.way_search",
)
REQUIRED_IMAGE_FILES = (
    "src/origin_map.png",
    "src/cir.png",
    "src/crash_warning.png",
    "src/crashed.png",
    "src/game_image/start.png",
    "src/game_image/joingame4.png",
    "src/game_image/join.png",
    "src/game_image/end.png",
    "src/game_image/close.png",
    "src/game_image/checkin.png",
    "src/game_image/no.png",
    "src/game_image/ok01.png",
    "src/game_image/ok02.png",
    "src/game_image/ok03.png",
    "src/game_image/tectree.png",
    "src/game_image/time.png",
    "src/game_image/yes.png",
    "src/game_image/exit.png",
    "src/game_image/rtb.png",
    "src/game_image/joining.png",
    "src/game_image/hvjoin.png",
    "src/game_image/buy.png",
    "src/game_image/back.png",
    "src/game_image/base.png",
    "src/game_image/ingaming.png",
    "src/game_image/backtobase.png",
    "src/game_image/backtobase2.png",
    "src/game_image/autobuyparts.png",
    "src/game_image/cart.png",
    "src/game_image/confirm.png",
    "src/game_image/confirm1.png",
    "src/game_image/confirm2.png",
    "src/game_image/improvement.png",
    "src/game_image/improvement_.png",
    "src/game_image/purchase.png",
    "src/game_image/purchase_confirm.png",
    "src/game_image/crew_cancel.png",
    "src/game_image/rtlg_no.png",
    "src/game_image/research.png",
    "src/game_image/research1.png",
    "src/game_image/box.png",
    "src/game_image/waiting.png",
    "src/game_image/data.png",
    "src/game_image/wtlogo.png",
    "src/game_image/6auto.png",
    "src/game_image/lock.png",
)


class CheckResult(NamedTuple):
    ok: bool
    code: str
    message: str
    warning: bool = False
    detail: str = ""


class GameState(NamedTuple):
    process_running: bool
    window_handle: int
    client_size: tuple[int, int] | None
    dpi: int | None


def check_runtime_imports(import_module) -> CheckResult:
    for module_name in REQUIRED_IMPORTS:
        try:
            import_module(module_name)
        except BaseException as exc:
            return CheckResult(
                False,
                "runtime_import_failed",
                f"Не удалось загрузить компонент программы: {module_name}. Переустановите или распакуйте сборку заново.",
                detail=str(exc) or type(exc).__name__,
            )
    return CheckResult(True, "runtime_imports_ready", "Все программные компоненты загружены.")


def check_vjoy(api) -> CheckResult:
    """Validate and briefly acquire vJoy device 1 without changing its state."""
    try:
        if not api.is_enabled():
            return CheckResult(False, "vjoy_not_installed", "vJoy не установлен или драйвер отключён.")
        if not api.driver_matches():
            return CheckResult(
                False,
                "vjoy_driver_mismatch",
                "Версия драйвера vJoy не совпадает с библиотекой управления. Переустановите vJoy.",
            )

        status = api.get_status(VJOY_DEVICE_ID)
        if status == 3:
            return CheckResult(False, "vjoy_device_missing", "Устройство vJoy № 1 не создано.")
        if status == 2:
            return CheckResult(
                False,
                "vjoy_device_busy",
                "Устройство vJoy № 1 занято другой программой. Закройте её и повторите проверку.",
            )
        if status not in (0, 1):
            return CheckResult(False, "vjoy_device_unknown", "Состояние устройства vJoy № 1 не удалось определить.")

        missing_axes = [axis for axis in VJOY_REQUIRED_AXES if not api.axis_exists(VJOY_DEVICE_ID, axis)]
        if missing_axes:
            names = ", ".join(missing_axes)
            return CheckResult(
                False,
                "vjoy_axis_missing",
                f"В устройстве vJoy № 1 отключена обязательная ось: {names}.",
            )

        buttons = api.button_count(VJOY_DEVICE_ID)
        if buttons < VJOY_REQUIRED_BUTTONS:
            return CheckResult(
                False,
                "vjoy_buttons_missing",
                f"Устройство vJoy № 1 должно иметь не менее 8 кнопок; сейчас доступно: {buttons}.",
            )

        if status == 1:
            if not api.acquire(VJOY_DEVICE_ID):
                return CheckResult(False, "vjoy_acquire_failed", "Не удалось получить доступ к устройству vJoy № 1.")
            api.relinquish(VJOY_DEVICE_ID)

        return CheckResult(True, "vjoy_ready", "vJoy: устройство № 1, оси X/Y/Z/RY и кнопки 1–8 доступны.")
    except BaseException as exc:
        detail = str(exc) or type(exc).__name__
        return CheckResult(
            False,
            "vjoy_not_installed",
            "vJoy не установлен, отключён или требует перезапуска Windows.",
            detail=detail,
        )


def check_path_json(root: Path) -> CheckResult:
    path = root / "path.json"
    if not path.is_file():
        return CheckResult(False, "path_json_missing", "Отсутствует обязательный файл path.json.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("root must be an object")
        for key in ("start_point", "end_point", "path"):
            if key not in payload or not isinstance(payload[key], list):
                raise ValueError(f"missing or invalid key: {key}")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return CheckResult(
            False,
            "path_json_invalid",
            "Файл path.json повреждён или имеет неверный формат.",
            detail=str(exc),
        )
    return CheckResult(True, "path_json_ready", "Файл path.json прочитан успешно.")


def check_image_resources(root: Path, image_reader) -> CheckResult:
    missing = [relative for relative in REQUIRED_IMAGE_FILES if not (root / relative).is_file()]
    if missing:
        return CheckResult(
            False,
            "resource_missing",
            "Отсутствуют обязательные изображения: " + ", ".join(missing),
        )

    invalid = []
    for relative in REQUIRED_IMAGE_FILES:
        try:
            image = image_reader(str(root / relative))
        except Exception as exc:
            return CheckResult(
                False,
                "resource_unreadable",
                f"Не удалось прочитать изображение: {relative}.",
                detail=str(exc),
            )
        if image is None:
            invalid.append(relative)
    if invalid:
        return CheckResult(
            False,
            "resource_unreadable",
            "Не удалось декодировать изображения: " + ", ".join(invalid),
        )
    return CheckResult(True, "images_ready", f"Изображения проверены: {len(REQUIRED_IMAGE_FILES)}.")


def check_screen_capture(camera_factory) -> CheckResult:
    camera = None
    try:
        camera = camera_factory()
        frame = camera.grab()
        if frame is None:
            return CheckResult(
                False,
                "screen_capture_empty",
                "Захват экрана инициализирован, но изображение не получено.",
            )
        return CheckResult(True, "screen_capture_ready", "Захват экрана DXcam работает.")
    except Exception as exc:
        return CheckResult(
            False,
            "screen_capture_failed",
            "Не удалось инициализировать захват экрана DXcam.",
            detail=str(exc),
        )
    finally:
        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass


def check_war_thunder(state: GameState) -> CheckResult:
    if not state.process_running:
        return CheckResult(
            False,
            "game_not_running",
            "War Thunder не запущен. Запустите игру, откройте ангар и повторите проверку.",
        )
    if not state.window_handle:
        return CheckResult(
            False,
            "game_window_missing",
            "War Thunder запущен, но окно DagorWClass не найдено. Дождитесь появления окна игры.",
        )
    if state.client_size != (1280, 720):
        actual = "неизвестен" if state.client_size is None else f"{state.client_size[0]}×{state.client_size[1]}"
        return CheckResult(
            False,
            "game_window_size",
            f"Размер клиентской области War Thunder должен быть 1280×720; сейчас: {actual}. "
            "Выберите оконный режим и масштаб интерфейса 100 %.",
        )
    if state.dpi not in (None, 96):
        percent = round(state.dpi * 100 / 96)
        return CheckResult(
            False,
            "game_dpi",
            f"Масштаб Windows для окна игры должен быть 100 %; сейчас обнаружено примерно {percent} %.",
        )
    return CheckResult(True, "game_ready", "Окно War Thunder найдено: 1280×720, масштаб 100 %.")


def check_war_thunder_api(request_get) -> CheckResult:
    try:
        response = request_get("http://127.0.0.1:8111/map_info.json", timeout=1.5)
        response.raise_for_status()
        response.json()
    except Exception as exc:
        return CheckResult(
            False,
            "game_api_unavailable",
            "War Thunder запущен, но локальный API 127.0.0.1:8111 пока недоступен. "
            "Обычно он появляется после входа в бой.",
            warning=True,
            detail=str(exc),
        )
    return CheckResult(True, "game_api_ready", "Локальный API War Thunder 127.0.0.1:8111 доступен.")


def summarize_results(results: list[CheckResult]) -> tuple[int, str]:
    failures = [result for result in results if not result.ok and not result.warning]
    if failures:
        return 2, f"Проверка завершена: обнаружено проблем — {len(failures)}."
    return 0, "Проверка завершена успешно."


class PyVJoyApi:
    """Thin read-mostly adapter over the vJoy SDK bundled by pyvjoy."""

    _AXIS_CONSTANTS = {
        "X": "HID_USAGE_X",
        "Y": "HID_USAGE_Y",
        "Z": "HID_USAGE_Z",
        "RY": "HID_USAGE_RY",
    }

    def __init__(self):
        self.pyvjoy = importlib.import_module("pyvjoy")
        self.sdk = self.pyvjoy._sdk
        self.dll = self.sdk._vj

    def is_enabled(self):
        try:
            return bool(self.sdk.vJoyEnabled())
        except BaseException:
            return False

    def driver_matches(self):
        try:
            dll_version = ctypes.c_ushort()
            driver_version = ctypes.c_ushort()
            native_driver_match = self.dll.DriverMatch
            native_driver_match.argtypes = [
                ctypes.POINTER(ctypes.c_ushort),
                ctypes.POINTER(ctypes.c_ushort),
            ]
            native_driver_match.restype = ctypes.c_int
            return bool(native_driver_match(ctypes.byref(dll_version), ctypes.byref(driver_version)))
        except BaseException:
            return False

    def get_status(self, device_id):
        return int(self.sdk.GetVJDStatus(device_id))

    def axis_exists(self, device_id, axis_name):
        axis_id = getattr(self.pyvjoy, self._AXIS_CONSTANTS[axis_name])
        return bool(self.dll.GetVJDAxisExist(device_id, axis_id))

    def button_count(self, device_id):
        return int(self.dll.GetVJDButtonNumber(device_id))

    def acquire(self, device_id):
        return bool(self.sdk.AcquireVJD(device_id))

    def relinquish(self, device_id):
        return bool(self.sdk.RelinquishVJD(device_id))


def get_game_state() -> GameState:
    import ctypes

    win32gui = importlib.import_module("win32gui")
    creation_flags = 0x08000000 if sys.platform == "win32" else 0
    process = subprocess.run(
        ["tasklist.exe", "/FI", "IMAGENAME eq aces.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        check=False,
        creationflags=creation_flags,
    )
    process_running = b"aces.exe" in process.stdout.lower()
    window_handle = int(win32gui.FindWindow("DagorWClass", None))
    if window_handle:
        left, top, right, bottom = win32gui.GetClientRect(window_handle)
        client_size = (right - left, bottom - top)
        get_dpi = getattr(ctypes.windll.user32, "GetDpiForWindow", None)
        dpi = int(get_dpi(window_handle)) if get_dpi else None
        process_running = True
    else:
        client_size = None
        dpi = None
    return GameState(process_running, window_handle, client_size, dpi)


def write_status_file(path: Path, results: list[CheckResult], exit_code: int) -> None:
    payload = {
        "exit_code": exit_code,
        "results": [result._asdict() for result in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_technical_details(results: list[CheckResult]) -> None:
    log_value = os.environ.get("AUTONAVY_LOG_PATH")
    if not log_value:
        return
    lines = [f"Preflight detail [{result.code}]: {result.detail}" for result in results if result.detail]
    if not lines:
        return
    try:
        with Path(log_value).open("a", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
    except OSError:
        pass


def run_preflight(root: Path) -> list[CheckResult]:
    results = [check_runtime_imports(importlib.import_module), check_path_json(root)]

    try:
        resources = importlib.import_module("toolkit.resources")
        results.append(check_image_resources(root, resources.read_image))
    except BaseException as exc:
        results.append(
            CheckResult(
                False,
                "resource_check_failed",
                "Не удалось проверить изображения программы.",
                detail=str(exc) or type(exc).__name__,
            )
        )

    try:
        dxcam = importlib.import_module("dxcam")
        results.append(
            check_screen_capture(lambda: dxcam.create(device_idx=0, output_color="BGRA"))
        )
    except BaseException as exc:
        results.append(
            CheckResult(
                False,
                "screen_capture_failed",
                "Не удалось загрузить компонент захвата экрана DXcam.",
                detail=str(exc) or type(exc).__name__,
            )
        )

    try:
        results.append(check_vjoy(PyVJoyApi()))
    except BaseException as exc:
        results.append(
            CheckResult(
                False,
                "vjoy_not_installed",
                "vJoy не установлен, отключён или требует перезапуска Windows.",
                detail=str(exc) or type(exc).__name__,
            )
        )

    try:
        game_state = get_game_state()
        game_result = check_war_thunder(game_state)
        results.append(game_result)
        if game_state.process_running:
            requests = importlib.import_module("requests")
            results.append(check_war_thunder_api(requests.get))
        else:
            results.append(
                CheckResult(
                    False,
                    "game_api_not_checked",
                    "Локальный API War Thunder не проверялся, потому что игра не запущена.",
                    warning=True,
                )
            )
    except BaseException as exc:
        results.append(
            CheckResult(
                False,
                "game_check_failed",
                "Не удалось проверить состояние War Thunder.",
                detail=str(exc) or type(exc).__name__,
            )
        )

    append_technical_details(results)
    return results
