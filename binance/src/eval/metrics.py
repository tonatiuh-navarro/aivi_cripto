from __future__ import annotations

from typing import Sequence


def cumulative_return(series: Sequence[float]) -> float:
    result = 1.0
    for value in series:
        result *= 1.0 + value
    return result - 1.0


__all__ = ["cumulative_return"]
