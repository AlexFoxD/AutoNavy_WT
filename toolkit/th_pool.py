"""Retired asynchronous worker API; runtime policy advances cooperatively on ticks."""
class thread_control:
    @staticmethod
    def submit(*args, **kwargs):
        raise RuntimeError('Legacy thread workers are retired; use the cancellable Application tick lifecycle')
    once = submit


def attempt(func, *args, **kwargs):
    """Explicit compatibility call; errors propagate to the resource owner."""
    return func(*args, **kwargs)
