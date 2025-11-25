from __future__ import annotations

import polars as pl


def apply(df: pl.DataFrame, period: int = 14, **_: int) -> pl.DataFrame:
    high = df["high"].cast(pl.Float64)
    low = df["low"].cast(pl.Float64)
    close = df["close"].cast(pl.Float64)
    prev_close = close.shift(1)
    tr = pl.max_horizontal([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ])
    atr = tr.rolling_mean(period)
    return df.with_columns(atr.alias(f"atr_{period}"))


__all__ = ["apply"]
