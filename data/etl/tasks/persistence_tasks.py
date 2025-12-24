from __future__ import annotations

import logging
from pathlib import Path

import polars as pl
from airflow.decorators import task

from data.etl.persist import ParquetUpsertStage
from data.etl.state_manager import update_etl_state


@task
def persist_data(transform_result: dict, entry: dict) -> dict:
    """
    Upsert DataFrame to parquet file and update ETL state.

    Wrapper around ParquetUpsertStage that:
    1. Counts existing rows in parquet
    2. Upserts new data (merge, deduplicate, sort)
    3. Updates etl_schedule_state.json with current timestamp
    4. Returns statistics

    Args:
        transform_result: Dict from transform_data with keys:
            - cache_path: str (path to processed parquet file)
            - processed_rows: int
            - ticker: str
            - freq: str
            - datasource: str
        entry: Ticker config with keys:
            - ticker: str
            - freq: str
            - output: str | None (custom parquet path)

    Returns:
        Dict with persistence stats:
        {
            "status": "updated" | "up_to_date",
            "ticker": str,
            "freq": str,
            "rows_added": int,
            "total_rows": int,
            "parquet_path": str
        }

    Implementation:
        - Reads DataFrame from cache_path
        - Reads existing parquet to count rows
        - Instantiates ParquetUpsertStage
        - Calls .transform(df) to upsert data
        - Updates state via state_manager.update_etl_state()
        - Returns stats dict for downstream tasks
    """
    logger = logging.getLogger("airflow.task.persist_data")

    # Read DataFrame from transform result
    cache_path = transform_result["cache_path"]
    df = pl.read_parquet(cache_path)

    ticker = entry["ticker"]
    freq = entry["freq"]
    datasource = entry.get("datasource", "binance").lower()

    # Determine parquet path
    output = entry.get("output")
    if output:
        parquet_path = Path(output)
    else:
        ticker_norm = ticker.lower()
        freq_norm = freq.lower()
        suffix = "" if datasource == "binance" else f"_{datasource}"
        parquet_path = Path(f"data/market_data_{ticker_norm}_{freq_norm}{suffix}.parquet")

    # Count existing rows before upsert
    existing_rows = 0
    if parquet_path.exists():
        try:
            existing_df = pl.read_parquet(parquet_path)
            existing_rows = existing_df.height
        except Exception as e:
            logger.warning(
                f"Failed to read existing parquet for row count: {e}. "
                f"Assuming 0 rows."
            )
            existing_rows = 0

    logger.info(
        f"Persisting {df.height} rows for {ticker} {freq} ({datasource}) "
        f"(existing: {existing_rows}, path: {parquet_path})"
    )

    # Instantiate ParquetUpsertStage
    stage = ParquetUpsertStage(
        path=str(parquet_path),
        key="open_time",  # Deduplicate on open_time
        sort_by="open_time",  # Sort by open_time
        log_file=None,  # Use default Airflow logging
    )

    # Upsert data
    result_df = stage.transform(df)

    # Count final rows
    final_rows = result_df.height if hasattr(result_df, "height") else existing_rows

    # Calculate delta
    delta = max(0, final_rows - existing_rows)

    # Update ETL state with current timestamp
    update_etl_state(ticker, freq, datasource=datasource)

    # Determine status
    status = "updated" if delta > 0 else "up_to_date"

    logger.info(
        f"Persisted {ticker} {freq} ({datasource}): "
        f"status={status}, rows_added={delta}, total_rows={final_rows}"
    )

    return {
        "status": status,
        "ticker": ticker,
        "freq": freq,
        "rows_added": delta,
        "total_rows": final_rows,
        "parquet_path": str(parquet_path),
        "datasource": datasource,
    }
