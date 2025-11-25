from __future__ import annotations

import polars as pl


def apply(df: pl.DataFrame, period: int = 20, column: str = "close", **_: int) -> pl.DataFrame:
    series = df[column].cast(pl.Float64)
    mean = series.rolling_mean(period)
    std = series.rolling_std(period)
    z = (series - mean) / std
    return df.with_columns(z.alias(f"zscore_{column}_{period}"))


__all__ = ["apply"]
