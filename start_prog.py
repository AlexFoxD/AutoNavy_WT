"""Compatibility launcher; all execution goes through the safe v2 CLI."""
from autonavy.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
