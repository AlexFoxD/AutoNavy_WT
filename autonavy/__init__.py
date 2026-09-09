"""Import-safe compatibility helpers for source and standalone launchers."""
from __future__ import annotations

import os
from pathlib import Path
import traceback


def load_application_main():
    from autonavy.cli import main
    return main


def run_application(application_loader=load_application_main, output=print, log_path: Path | None = None) -> int:
    """Retain the legacy injected-loader contract and localized error messages."""
    try:
        result = application_loader()()
        return result if isinstance(result, int) else 0
    except KeyboardInterrupt:
        output('AutoNavy_WT остановлен пользователем.')
        return 0
    except BaseException:
        output('Не удалось запустить AutoNavy_WT. Проверьте журнал запуска и повторите диагностику.')
        destination = log_path or os.environ.get('AUTONAVY_LOG_PATH')
        if destination:
            try:
                with Path(destination).open('a', encoding='utf-8') as stream:
                    stream.write('Unexpected application exception:\n')
                    traceback.print_exc(file=stream)
            except OSError:
                pass
        return 3
