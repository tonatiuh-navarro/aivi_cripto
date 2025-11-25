from __future__ import annotations

import polars as pl


def ensure_sorted(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.sort(column)


__all__ = ["ensure_sorted"]
