from __future__ import annotations

from collections.abc import Iterable


def divide(a: float, b: float) -> float:
    """Return a / b.

    NOTE: intentionally minimal v0.0 behavior; edge-cases are part of the lab.
    """
    return a / b


def percentage(value: float, total: float) -> float:
    """Return (value / total) * 100.

    NOTE: intentionally does not define behavior for total == 0 in this lab.
    """
    return (value / total) * 100.0


def moving_average(values: Iterable[float], window: int) -> list[float]:
    """Compute simple moving average over an iterable.

    Rules (intentionally incomplete for the lab):
    - window must be > 0
    - if window > len(values): behavior should be decided by tests/spec later
    """
    vals = list(values)
    if window <= 0:
        raise ValueError("window must be > 0")
    out: list[float] = []
    for i in range(0, len(vals) - window + 1):
        chunk = vals[i : i + window]
        out.append(sum(chunk) / float(window))
    return out
