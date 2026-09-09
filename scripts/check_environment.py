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
    "autonavy.py",
    "runtime_preflight.py",
    "start_prog.py",
    "path.json",
    "ЗАПУСТИТЬ.bat",
    "scripts/launcher.ps1",
    "toolkit/way_search.cp311-win_amd64.pyd",
    "src/origin_map.png",
    "src/cir.png",
    "src/crash_warning.png",
    "src/crashed.png",
    "src/game_image/start.png",
)
IGNORED_SOURCE_DIRECTORIES = {".venv", ".output", "__pycache__", "tests"}


class CheckResult(NamedTuple):
    ok: bool
    message: str


def configure_utf8_output(stream) -> None:
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def check_platform(platform_name: str) -> CheckResult:
    if platform_name != "win32":
        return CheckResult(False, "Windows (win32) is required for this mode.")
    return CheckResult(True, "Operating system: Windows.")


def check_python_version(version_info) -> CheckResult:
    actual = tuple(version_info[:2])
    if actual != SUPPORTED_PYTHON:
        return CheckResult(False, f"CPython 3.11 required; detected Python {actual[0]}.{actual[1]}.")
    return CheckResult(True, "Python version: CPython 3.11.")


def check_python_architecture(pointer_size: int) -> CheckResult:
    bits = pointer_size * 8
    if bits != 64:
        return CheckResult(False, f"64-bit Python required; detected {bits}-bit.")
    return CheckResult(True, "Python architecture: 64-bit.")


def check_required_file(repo_root: Path, relative_path: str) -> CheckResult:
    if not (repo_root / relative_path).is_file():
        return CheckResult(False, f"Missing required file: {relative_path}")
    return CheckResult(True, f"File found: {relative_path}")


def check_image_resources(repo_root: Path) -> CheckResult:
    """Verify that every PNG referenced by cv2.imread can be decoded."""
    try:
        read_image = importlib.import_module("toolkit.resources").read_image
    except Exception as exc:
        return CheckResult(False, f"OpenCV недоступен для проверки изображений: {exc}")

    image_paths: set[Path] = set()
    pattern = re.compile(r"(?:cv2\.imread|read_image)\(\s*['\"]([^'\"]+\.png)['\"]")
    for source_path in repo_root.rglob("*.py"):
        relative_parts = source_path.relative_to(repo_root).parts[:-1]
        if any(
            part in IGNORED_SOURCE_DIRECTORIES
            or part.endswith((".build", ".dist", ".onefile-build"))
            for part in relative_parts
        ):
            continue
        source = source_path.read_text(encoding="utf-8-sig")
        image_paths.update(repo_root / match for match in pattern.findall(source))
    if not image_paths:
        return CheckResult(False, "В исходном коде не найдены ссылки на PNG-ресурсы.")
    invalid = [path.relative_to(repo_root) for path in sorted(image_paths) if read_image(path) is None]
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
        preflight = importlib.import_module("runtime_preflight")
        result = preflight.check_vjoy(preflight.PyVJoyApi())
    except BaseException as exc:
        detail = str(exc) or type(exc).__name__
        return CheckResult(False, f"vJoy не установлен, отключён или требует перезапуска Windows: {detail}")
    return CheckResult(result.ok, result.message)


def check_pins(requirements: Path) -> list[CheckResult]:
    """Read installed metadata only; importing DXcam enumerates native adapters."""
    from importlib import metadata
    results = []
    for line in requirements.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('-r '):
            results.extend(check_pins(requirements.parent / line[3:].strip()))
            continue
        name, expected = line.split('==')
        try:
            actual = metadata.version(name)
        except metadata.PackageNotFoundError:
            actual = 'missing'
        results.append(CheckResult(actual == expected, f'{name}: expected {expected}, installed {actual}'))
    return results


def run_checks(repo_root: Path, installation_only: bool = False, *, mode: str = 'core') -> list[CheckResult]:
    """Device-free source readiness; hardware diagnostics are a separate command."""
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    if installation_only:
        mode = 'runtime'  # Legacy alias now checks metadata, never native imports.
    results = [check_python_version(sys.version_info), check_python_architecture(struct.calcsize('P'))]
    if mode != 'core':
        results.append(check_platform(sys.platform))
    requirements = {'core': 'requirements-core.txt', 'runtime': 'requirements.txt', 'build': 'requirements-build.txt'}[mode]
    results.extend(check_pins(repo_root / requirements))
    results.extend(check_required_file(repo_root, path) for path in REQUIRED_FILES)
    results.append(check_required_file(repo_root, 'configs/default.toml'))
    try:
        from autonavy.config import load_settings
        load_settings(repo_root / 'configs/default.toml')
        results.append(CheckResult(True, 'Default configuration and resources valid (no devices opened).'))
    except Exception as exc:
        results.append(CheckResult(False, f'Default configuration invalid: {exc}'))
    if mode != 'core':
        results.append(check_required_file(repo_root, 'third_party/vjoy/2.1.9.1/x64/vJoyInterface.dll'))
    return results


def main() -> int:
    configure_utf8_output(sys.stdout)
    configure_utf8_output(sys.stderr)
    parser = argparse.ArgumentParser(description='Device-free source dependency/resource readiness')
    parser.add_argument('--mode', choices=('core', 'runtime', 'build'), default='core')
    parser.add_argument('--installation-only', action='store_true', help='Legacy alias for static runtime readiness')
    args = parser.parse_args()
    results = run_checks(Path(__file__).resolve().parents[1], args.installation_only, mode=args.mode)
    for result in results:
        print(f"[{'OK' if result.ok else 'ERROR'}] {result.message}")
    print('Full hardware diagnostics are manual: python -m autonavy --preflight')
    return int(any(not result.ok for result in results))


if __name__ == '__main__':
    raise SystemExit(main())
