"""Bounded numeric runtime metrics; snapshots summarize the retained window."""

from collections import deque
import math
import threading


def summarize(values):
    """Linear-interpolated percentiles over nonempty numeric samples."""
    ordered = sorted(values)
    if not ordered:
        return dict(p50=None, p95=None, mean=None)

    def percentile(fraction):
        position = (len(ordered) - 1) * fraction
        left = int(position)
        right = min(left + 1, len(ordered) - 1)
        return ordered[left] + (ordered[right] - ordered[left]) * (position - left)

    return dict(
        p50=percentile(0.5), p95=percentile(0.95), mean=sum(ordered) / len(ordered)
    )


class Metrics:
    """Bound both history per series and cardinality, without frame/text retention."""

    def __init__(self, *, max_samples=512, max_series=32):
        if any(type(v) is not int or v < 1 for v in (max_samples, max_series)):
            raise ValueError("Metric bounds must be positive integers")
        self.max_samples, self.max_series = max_samples, max_series
        self._samples, self._counts, self._counters = {}, {}, {}
        self._lock = threading.Lock()

    def _name(self, name):
        if not isinstance(name, str) or not name or len(name) > 80:
            raise ValueError("Metric name must be 1 to 80 characters")
        if name not in self._samples and name not in self._counters:
            if len(self._samples) + len(self._counters) >= self.max_series:
                raise ValueError("Metric series capacity exceeded")

    def observe(self, name, value):
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Metric samples must be finite and nonnegative")
        with self._lock:
            self._name(name)
            if name in self._counters:
                raise ValueError("Metric name already denotes a counter")
            if name not in self._samples:
                self._samples[name] = deque(maxlen=self.max_samples)
                self._counts[name] = 0
            self._samples[name].append(value)
            self._counts[name] += 1

    def increment(self, name, count=1):
        if type(count) is not int or count < 0:
            raise ValueError("Counter increments must be nonnegative integers")
        with self._lock:
            self._name(name)
            if name in self._samples:
                raise ValueError("Metric name already denotes samples")
            self._counters[name] = self._counters.get(name, 0) + count

    def snapshot(self):
        with self._lock:
            return dict(
                samples={
                    name: dict(
                        count=self._counts[name],
                        retained=len(values),
                        **summarize(values),
                    )
                    for name, values in self._samples.items()
                },
                counters=dict(self._counters),
            )
