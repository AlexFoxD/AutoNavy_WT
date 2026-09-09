"""Run the shared CLI with ``python -m autonavy``."""
from autonavy.cli import main

if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    raise SystemExit(main())
