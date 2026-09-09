"""Command-line entry point for source and standalone AutoNavy_WT runs."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

import runtime_preflight


def configure_utf8_output(stream) -> None:
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def application_root() -> Path:
    if "__compiled__" in globals():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def append_exception(log_path: Path | None) -> None:
    if log_path is None:
        value = os.environ.get("AUTONAVY_LOG_PATH")
        log_path = Path(value) if value else None
    if log_path is None:
        return
    try:
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write("Unexpected application exception:\n")
            traceback.print_exc(file=stream)
    except OSError:
        pass


def load_application_main():
    import start_prog

    return start_prog.main


def run_application(application_loader=load_application_main, output=print, log_path: Path | None = None) -> int:
    try:
        application_main = application_loader()
        application_main()
    except KeyboardInterrupt:
        output("AutoNavy_WT остановлен пользователем.")
        return 0
    except BaseException:
        output(
            "Не удалось запустить AutoNavy_WT. Проверьте журнал запуска и повторите диагностику."
        )
        append_exception(log_path)
        return 3
    return 0


class RussianArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"Ошибка параметров запуска: {message}\n")


def run_preflight(root: Path, status_file: Path | None = None) -> int:
    results = runtime_preflight.run_preflight(root)
    for result in results:
        marker = "OK" if result.ok else ("ПРЕДУПРЕЖДЕНИЕ" if result.warning else "ОШИБКА")
        print(f"[{marker}] {result.message}")
    exit_code, summary = runtime_preflight.summarize_results(results)
    print(f"\n{summary}")
    if status_file is not None:
        try:
            runtime_preflight.write_status_file(status_file, results, exit_code)
        except OSError as exc:
            print(f"[ОШИБКА] Не удалось записать результат диагностики: {exc}")
            return 3
    return exit_code


def main(argv: list[str] | None = None) -> int:
    configure_utf8_output(sys.stdout)
    configure_utf8_output(sys.stderr)
    parser = RussianArgumentParser(description="Запуск и безопасная диагностика AutoNavy_WT")
    parser.add_argument("--preflight", action="store_true", help="только безопасная проверка без ввода")
    parser.add_argument("--run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--status-file", type=Path, help="файл результата диагностики")
    args = parser.parse_args(argv)

    root = application_root()
    if args.preflight:
        return run_preflight(root, args.status_file)
    if not args.run:
        preflight_exit = run_preflight(root, args.status_file)
        if preflight_exit:
            return preflight_exit
    return run_application()


if __name__ == "__main__":
    raise SystemExit(main())
