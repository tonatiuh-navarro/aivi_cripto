from __future__ import annotations


def calculate_fee(notional: float, rate: float) -> float:
    return notional * rate


__all__ = ["calculate_fee"]
