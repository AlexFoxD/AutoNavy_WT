"""Lazy legacy asset names; importing this module performs no resource reads."""
from autonavy.config import load_settings
from autonavy.vision.templates import GAME_ASSETS, TemplateRegistry

_registry = None


def load(settings=None):
    """Explicitly prepare a registry for legacy callers that still require image arrays."""
    global _registry
    _registry = TemplateRegistry.from_settings(settings or load_settings())
    return _registry


def __getattr__(name):
    if name not in GAME_ASSETS and name not in ('crash_warning','crashed'):
        raise AttributeError(name)
    registry = _registry if _registry is not None else load()
    return registry.prepared_image(name)
