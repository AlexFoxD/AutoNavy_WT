"""Validate the Windows environment required by AutoNavy_WT."""

from __future__ import annotations

import argparse
import importlib
import re
import struct
import sys
from pathlib import Path
from typing import NamedTuple


SUPPORTED_PYTHON = (3, 11)
REQUIRED_IMPORTS = (
    ("cv2", "opencv-python"),
    ("dxcam", "dxcam"),
    ("keyboard", "keyboard"),
    ("matplotlib", "matplotlib"),
    ("numpy", "numpy"),
    ("pydirectinput", "PyDirectInput"),
    ("pyvjoy", "pyvjoy"),
    ("requests", "requests"),
    ("scipy", "scipy"),
    ("simple_pid", "simple-pid"),
    ("win32api", "pywin32"),
    ("win32gui", "pywin32"),
    ("toolkit.way_search", "bundled CPython extension"),
)
REQUIRED_FILES = (
    "start_prog.py",
    "path.json",
    "toolkit/way_search.cp311-win_amd64.pyd",
    "src/origin_map.png",
    "src/cir.png",
    "src/crash_warning.png",
    "src/crashed.png",
    "src/game_image/start.png",
)


class CheckResult(NamedTuple):
    ok: bool
    message: str


def configure_utf8_output(stream) -> None:
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def check_platform(platform_name: str) -> CheckResult:
    if platform_name != "win32":
        return CheckResult(False, "Поддерживается только Windows (win32).")
    return CheckResult(True, "Операционная система: Windows.")


def check_python_version(version_info) -> CheckResult:
    actual = tuple(version_info[:2])
    if actual != SUPPORTED_PYTHON:
        return CheckResult(False, f"Требуется CPython 3.11, обнаружен Python {actual[0]}.{actual[1]}.")
    return CheckResult(True, "Версия Python: CPython 3.11.")


def check_python_architecture(pointer_size: int) -> CheckResult:
    bits = pointer_size * 8
    if bits != 64:
        return CheckResult(False, f"Требуется 64-битный Python, обнаружен {bits}-битный.")
    return CheckResult(True, "Архитектура Python: 64 бита.")


def check_required_file(repo_root: Path, relative_path: str) -> CheckResult:
    if not (repo_root / relative_path).is_file():
        return CheckResult(False, f"Отсутствует обязательный файл: {relative_path}")
    return CheckResult(True, f"Файл найден: {relative_path}")


def check_image_resources(repo_root: Path) -> CheckResult:
    """Verify that every PNG referenced by cv2.imread can be decoded."""
    try:
        cv2 = importlib.import_module("cv2")
    except Exception as exc:
        return CheckResult(False, f"OpenCV недоступен для проверки изображений: {exc}")

    image_paths: set[Path] = set()
    pattern = re.compile(r"cv2\.imread\(\s*['\"]([^'\"]+\.png)['\"]")
    for source_path in repo_root.rglob("*.py"):
        if ".venv" in source_path.parts:
            continue
        source = source_path.read_text(encoding="utf-8-sig")
        image_paths.update(repo_root / match for match in pattern.findall(source))
    if not image_paths:
        return CheckResult(False, "В исходном коде не найдены ссылки на PNG-ресурсы.")
    invalid = [path.relative_to(repo_root) for path in sorted(image_paths) if cv2.imread(str(path)) is None]
    if invalid:
        names = ", ".join(str(path) for path in invalid)
        return CheckResult(False, f"Не удалось прочитать изображения: {names}")
    return CheckResult(True, f"PNG-ресурсы OpenCV проверены: {len(image_paths)}.")


def check_import(module_name: str, package_name: str) -> CheckResult:
    try:
        importlib.import_module(module_name)
    except Exception as exc:  # Import failures can include missing native DLLs.
        return CheckResult(False, f"Не удалось загрузить {package_name} ({module_name}): {exc}")
    return CheckResult(True, f"Модуль загружен: {module_name}")


def check_vjoy_driver() -> CheckResult:
    try:
        pyvjoy = importlib.import_module("pyvjoy")
        pyvjoy.VJoyDevice(1)
    except Exception as exc:
        detail = str(exc) or type(exc).__name__
        return CheckResult(False, f"Устройство vJoy № 1 недоступно: {detail}")
    return CheckResult(True, "Драйвер vJoy и устройство № 1 доступны.")


def run_checks(repo_root: Path, installation_only: bool = False) -> list[CheckResult]:
    repo_root_string = str(repo_root)
    if repo_root_string not in sys.path:
        sys.path.insert(0, repo_root_string)
    results = [
        check_platform(sys.platform),
        check_python_version(sys.version_info),
        check_python_architecture(struct.calcsize("P")),
    ]
    results.extend(check_required_file(repo_root, path) for path in REQUIRED_FILES)
    results.extend(check_import(module, package) for module, package in REQUIRED_IMPORTS)
    results.append(check_image_resources(repo_root))
    if not installation_only:
        results.append(check_vjoy_driver())
    return results


def main() -> int:
    configure_utf8_output(sys.stdout)
    configure_utf8_output(sys.stderr)
    parser = argparse.ArgumentParser(description="Проверка среды AutoNavy_WT")
    parser.add_argument(
        "--installation-only",
        action="store_true",
        help="не проверять системный драйвер и устройство vJoy",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    results = run_checks(repo_root, installation_only=args.installation_only)
    for result in results:
        marker = "OK" if result.ok else "ОШИБКА"
        print(f"[{marker}] {result.message}")

    failures = sum(not result.ok for result in results)
    if failures:
        print(f"\nПроверка завершена: ошибок — {failures}.")
        return 1
    print("\nПроверка завершена успешно.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
