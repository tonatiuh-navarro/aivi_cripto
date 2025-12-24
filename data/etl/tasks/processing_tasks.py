from __future__ import annotations

import logging

import polars as pl
from airflow.decorators import task

from data.etl.processing import MarketFrameStage


@task
def transform_data(fetch_result: dict, entry: dict) -> dict:
    """
    Transform raw OHLCV into market frame with indicators.

    Wrapper around MarketFrameStage that computes ATR and filters recent data.

    Args:
        fetch_result: Dict from fetch task with keys:
            - cache_path: str (path to parquet file)
            - rows: int (number of rows)
            - ticker: str
            - freq: str
        entry: Ticker config with keys:
            - atr_period: int (rolling window for ATR, default 14)
            - months: int (filter last N months, default 6)

    Returns:
        dict: Updated fetch_result with processed DataFrame info
    """
    logger = logging.getLogger("airflow.task.transform_data")

    # Read DataFrame from cache file
    cache_path = fetch_result["cache_path"]
    df = pl.read_parquet(cache_path)

    ticker = entry.get("ticker", "unknown")
    freq = entry.get("freq", "unknown")
    atr_period = int(entry.get("atr_period", 14))
    months = int(entry.get("months", 6))

    logger.info(
        f"Transforming data for {ticker} {freq} from {cache_path} "
        f"(atr_period: {atr_period}, months: {months})"
    )

    # Instantiate MarketFrameStage
    stage = MarketFrameStage(
        atr_period=atr_period,
        months=months,
        log_file=None,  # Use default Airflow logging
    )

    # Transform data (compute ATR, filter by months)
    processed_df = stage.transform(df)

    # Save processed DataFrame back to same cache file (overwrite)
    processed_df.write_parquet(cache_path)

    logger.info(
        f"Transformed {df.height} → {processed_df.height} rows for {ticker} {freq} "
        f"(filtered to last {months} months) → {cache_path}"
    )

    # Update fetch_result with processed row count (no DataFrame)
    return {
        **fetch_result,
        "processed_rows": processed_df.height,
    }
