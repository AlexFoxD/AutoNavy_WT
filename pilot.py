"""Compatibility launcher; navigation runs through the single v2 application."""
from autonavy.cli import main


def pathfinder(*args,**kwargs):
    raise RuntimeError('Standalone pilot is retired; use python -m autonavy')


if __name__=='__main__':
    raise SystemExit(main())
