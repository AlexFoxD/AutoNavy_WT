"""Explicit runtime logging/display and bounded fault diagnostics; inert on import."""

from collections import OrderedDict
from contextlib import contextmanager
import logging
from logging.handlers import RotatingFileHandler
import time
import traceback


class FaultThrottle:
    def __init__(self, interval_s, *, clock=time.monotonic, max_keys=32):
        import math

        if (
            not math.isfinite(interval_s)
            or interval_s <= 0
            or type(max_keys) is not int
            or max_keys < 1
        ):
            raise ValueError("Fault throttle limits must be positive")
        self.interval_s, self.clock, self.max_keys = interval_s, clock, max_keys
        self._next = OrderedDict()

    @property
    def key_count(self):
        return len(self._next)

    def allow(self, key):
        if not isinstance(key, str) or len(key) > 80:
            raise ValueError("Fault key must be bounded text")
        now = self.clock()
        if key in self._next and now < self._next[key]:
            return False
        self._next[key] = now + self.interval_s
        self._next.move_to_end(key)
        if len(self._next) > self.max_keys:
            self._next.popitem(last=False)
        return True


def exception_text(exc, limit=4096, *, context=""):
    """Bound IPC bytes, retaining context/type and the final exception reason."""
    if type(limit) is not int or limit < 128:
        raise ValueError("Exception byte limit must be at least 128")
    context_bytes = context.encode("utf-8", errors="replace")[: min(160, limit // 3)]
    data = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    ).encode("utf-8", errors="replace")
    prefix = context_bytes + b"\n" if context_bytes else b""
    if len(prefix) + len(data) <= limit:
        return prefix + data
    marker = (
        b"[traceback truncated]\n" + type(exc).__name__.encode()[:60] + b": " + prefix
    )
    return marker + data[-(limit - len(marker)) :]


@contextmanager
def runtime_logging(settings):
    """Own only our handlers; configuration validation never creates log files."""
    logger = logging.getLogger("autonavy")
    previous_level, previous_propagate = logger.level, logger.propagate
    handlers = []
    try:
        settings.paths.logs.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                settings.paths.logs / "autonavy.log",
                maxBytes=settings.diagnostics.log_max_bytes,
                backupCount=settings.diagnostics.log_backups,
                encoding="utf-8",
            )
        )
        handlers.append(logging.StreamHandler())
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        for handler in handlers:
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(settings.diagnostics.log_level)
        logger.propagate = False
        yield
    except Exception:
        logger.exception("Runtime startup or execution failed")
        raise
    finally:
        for handler in handlers:
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


class Preview:
    """Native GUI calls occur only when explicit preview has a new debug image."""

    def __init__(self):
        self.opened = False

    def show(self, image):
        import cv2

        cv2.imshow("AutoNavy diagnostics", image)
        self.opened = True
        cv2.waitKey(1)

    def close(self):
        if self.opened:
            import cv2

            cv2.destroyWindow("AutoNavy diagnostics")
            self.opened = False
