from __future__ import annotations

import polars as pl


def apply(df: pl.DataFrame, period: int = 14, **_: int) -> pl.DataFrame:
    delta = df["close"].cast(pl.Float64).diff()
    gain = delta.clip_min(0.0)
    loss = (-delta).clip_min(0.0)
    avg_gain = gain.rolling_mean(period)
    avg_loss = loss.rolling_mean(period)
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return df.with_columns(rsi.alias(f"rsi_{period}"))


__all__ = ["apply"]
