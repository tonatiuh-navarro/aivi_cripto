from __future__ import annotations

import polars as pl


def apply(df: pl.DataFrame, period: int = 20, column: str = "close", **_: int) -> pl.DataFrame:
    series = df[column].cast(pl.Float64)
    alpha = 2.0 / (period + 1)
    ema = series.ewm_mean(alpha=alpha)
    return df.with_columns(ema.alias(f"ema_{column}_{period}"))


__all__ = ["apply"]
