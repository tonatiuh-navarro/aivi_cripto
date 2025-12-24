from __future__ import annotations

import logging

import polars as pl
from airflow.decorators import task
from airflow.exceptions import AirflowException
from airflow.operators.python import get_current_context

from data.etl.extraction import ExtractionStage
from data.etl.extraction_yf import YFinanceExtractionStage


def _default_cache_path(entry: dict, datasource: str) -> str:
    ticker_norm = entry["ticker"].lower()
    freq_norm = entry["freq"].lower()
    if datasource == "binance":
        return f"data/market_data_{ticker_norm}_{freq_norm}.parquet"
    return f"data/market_data_{ticker_norm}_{freq_norm}_{datasource}.parquet"


@task
def fetch_binance_data(entry: dict) -> dict:
    """
    Extract market data from Binance API.

    Wrapper around ExtractionStage that fetches OHLCV data.
    Includes rate limit check - skips if interval not met.

    Returns dict with cache_path and row count instead of DataFrame.
    """
    from airflow.exceptions import AirflowSkipException
    from data.etl.state_manager import should_run_etl

    logger = logging.getLogger("airflow.task.fetch_binance_data")

    ticker = entry["ticker"]
    freq = entry["freq"]
    interval_minutes = entry.get("interval_minutes", 0)
    datasource = entry.get("datasource")

    # Check rate limit
    should_run = should_run_etl(ticker, freq, interval_minutes, datasource=datasource)
    if not should_run:
        logger.info(f"⊘ Rate limit not met for {ticker} {freq} - skipping Binance ETL")
        raise AirflowSkipException(f"Interval not met for {ticker} {freq}")

    logger.info(f"✓ Rate limit OK for {ticker} {freq} - proceeding with Binance fetch")

    limit = int(entry.get("limit", 1000))
    start = entry.get("start")
    end = entry.get("end")

    # Determine cache_path from output or default
    output = entry.get("output")
    cache_path = output or _default_cache_path(entry, datasource="binance")

    logger.info(
        f"Fetching data for {ticker} {freq} via Binance "
        f"(limit: {limit}, cache: {cache_path})"
    )

    stage = ExtractionStage(
        ticker=ticker,
        frequency=freq,
        limit=limit,
        start=start,
        end=end,
        cache_path=cache_path,
        log_file=None,  # Use default Airflow logging
    )

    df = stage.transform(None)

    # Write DataFrame to cache file
    df.write_parquet(cache_path)

    logger.info(f"Fetched {df.height} rows for {ticker} {freq} (binance) → {cache_path}")

    # Return path instead of DataFrame to avoid XCom serialization issues
    return {
        "cache_path": cache_path,
        "rows": df.height,
        "ticker": ticker,
        "freq": freq,
        "datasource": "binance",
    }


@task
def fetch_yfinance_data(entry: dict) -> dict:
    """
    Extract market data from yfinance.

    Wrapper around YFinanceExtractionStage that fetches OHLCV data.
    Includes rate limit check - skips if interval not met.

    Returns dict with cache_path and row count instead of DataFrame.
    """
    from airflow.exceptions import AirflowSkipException
    from data.etl.state_manager import should_run_etl

    logger = logging.getLogger("airflow.task.fetch_yfinance_data")

    ticker = entry["ticker"]
    freq = entry["freq"]
    interval_minutes = entry.get("interval_minutes", 0)
    datasource = entry.get("datasource")

    # Check rate limit
    should_run = should_run_etl(ticker, freq, interval_minutes, datasource=datasource)
    if not should_run:
        logger.info(f"⊘ Rate limit not met for {ticker} {freq} - skipping yfinance ETL")
        raise AirflowSkipException(f"Interval not met for {ticker} {freq}")

    logger.info(f"✓ Rate limit OK for {ticker} {freq} - proceeding with yfinance fetch")

    start = entry.get("start")
    end = entry.get("end")

    output = entry.get("output")
    cache_path = output or _default_cache_path(entry, datasource="yfinance")

    logger.info(
        f"Fetching data for {ticker} {freq} via yfinance "
        f"(cache: {cache_path})"
    )

    stage = YFinanceExtractionStage(
        ticker=ticker,
        frequency=freq,
        start=start,
        end=end,
        cache_path=cache_path,
        log_file=None,
    )

    df = stage.transform(None)

    # Write DataFrame to cache file
    df.write_parquet(cache_path)

    logger.info(f"Fetched {df.height} rows for {ticker} {freq} (yfinance) → {cache_path}")

    # Return path instead of DataFrame to avoid XCom serialization issues
    return {
        "cache_path": cache_path,
        "rows": df.height,
        "ticker": ticker,
        "freq": freq,
        "datasource": "yfinance",
    }


@task(trigger_rule="none_failed_min_one_success")
def route_fetch_output(entry: dict) -> pl.DataFrame:
    """
    Pull the DataFrame from the selected datasource branch.

    Uses task_id derived from entry['datasource'] to fetch XCom.
    """
    ctx = get_current_context()
    ti = ctx["ti"]
    datasource = entry.get("datasource", "binance").lower()
    task_map = {
        "binance": "fetch_binance_data",
        "yfinance": "fetch_yfinance_data",
    }
    selected = task_map.get(datasource)
    if not selected:
        raise AirflowException(f"Unsupported datasource: {datasource}")

    upstream_ids = list(ctx["task"].upstream_task_ids)
    candidate_ids = [tid for tid in upstream_ids if selected in tid]
    task_id = candidate_ids[0] if candidate_ids else selected

    df = ti.xcom_pull(task_ids=task_id)
    if df is None:
        raise AirflowException(f"No XCom data from task_id={task_id}")
    return df
