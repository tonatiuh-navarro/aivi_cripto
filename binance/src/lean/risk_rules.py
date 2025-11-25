from __future__ import annotations


def stop_loss(entry: float, pct: float) -> float:
    return entry * (1.0 - pct)


__all__ = ["stop_loss"]
