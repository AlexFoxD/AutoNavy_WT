"""Shared command-line entrypoint. Parsing and diagnostics do not open devices."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path
import sys

from autonavy.config import ConfigurationError, load_settings, resource_root

LOG = logging.getLogger(__name__)


class _ArgumentError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ArgumentError(message)


def _preflight(status_file: Path | None) -> int:
    # Full hardware diagnostics stay explicit; normal safe CLI never imports them.
    import runtime_preflight
    results = runtime_preflight.run_preflight(resource_root())
    for result in results:
        marker = 'OK' if result.ok else ('WARNING' if result.warning else 'ERROR')
        print(f'[{marker}] {result.message}')
    code, summary = runtime_preflight.summarize_results(results)
    print(summary)
    if status_file is not None:
        runtime_preflight.write_status_file(status_file, results, code)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description='AutoNavy_WT safe runtime and offline diagnostics')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--check-config', action='store_true', help='Validate settings without opening devices')
    parser.add_argument('--capture', choices=('dxcam', 'obs', 'replay'))
    parser.add_argument('--fixture', type=Path, help='Finite replay fixture directory')
    parser.add_argument('--max-frames', type=int)
    parser.add_argument('--dry-run', action='store_true', help='Observe without physical input (default)')
    parser.add_argument('--enable-input', action='store_true', help='Explicitly opt into physical input on a validated live backend')
    parser.add_argument('--preflight', action='store_true', help='Run the existing full environment diagnostics')
    parser.add_argument('--status-file', type=Path, help='Write explicit preflight results')
    parser.add_argument('--run', action='store_true', help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(argv)
        if args.dry_run and args.enable_input:
            raise ConfigurationError('--dry-run and --enable-input are mutually exclusive')
        if args.status_file is not None and not args.preflight:
            raise ConfigurationError('--status-file requires --preflight')
        if args.preflight:
            if any((args.check_config, args.config is not None, args.capture is not None,
                    args.fixture is not None, args.max_frames is not None,
                    args.dry_run, args.enable_input, args.run)):
                raise ConfigurationError('--preflight is a standalone diagnostic mode; only --status-file may accompany it')
            return _preflight(args.status_file)
        capture = {key: value for key, value in {'backend': args.capture, 'fixture': args.fixture, 'max_frames': args.max_frames}.items() if value is not None}
        overrides = {'capture': capture}
        if args.enable_input:
            overrides['input'] = {'enable_input': True}
        elif args.dry_run:
            overrides['input'] = {'enable_input': False}
        settings = load_settings(args.config, overrides)
        if settings.input.enable_input and not args.enable_input:
            raise ConfigurationError('Physical input requires explicit --enable-input; config alone cannot enable it')
        resolved = json.dumps(asdict(settings), default=str, sort_keys=True)
        if args.check_config:
            print(f'Configuration valid: {resolved}')
            return 0
        from autonavy.diagnostics import runtime_logging
        with runtime_logging(settings):
            LOG.info('resolved_settings=%s', resolved)
            from autonavy.app import Application
            app = Application(settings)
            result = app.run()
            if app.last_error:
                print(f'Application error: {app.last_error}', file=sys.stderr)
            print(f'AutoNavy_WT stopped: backend={settings.capture.backend} frames={app.frames_processed} state={app.state.value}')
            return result
    except SystemExit as exc:
        # argparse help is successful; reusable main never terminates its caller.
        return int(exc.code or 0)
    except (_ArgumentError, ConfigurationError) as exc:
        print(f'Configuration error: {exc}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        LOG.exception('Startup failed: %s', exc)
        return 3
