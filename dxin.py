"""Compatibility import for the explicitly retired direct-input API."""
from toolkit.MnK import Mouse, Keyboard

if __name__ == '__main__':
    from autonavy.cli import main
    raise SystemExit(main())
