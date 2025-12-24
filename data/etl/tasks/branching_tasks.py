from __future__ import annotations

import logging

from airflow.decorators import task

from data.etl.state_manager import should_run_etl


@task.branch
def check_rate_limit(entry: dict) -> str:
    """
    Branch operator to decide ETL execution based on interval throttling.

    Uses @task.branch decorator to conditionally skip ETL if interval not met.

    Args:
        entry: Ticker config with keys:
            - ticker: str
            - freq: str
            - interval_minutes: int
            - datasource: str ("binance" | "yfinance")

    Returns:
        str: Task ID to execute next:
            - "etl_pipeline.select_datasource" if should run ETL
            - "skip_etl" if should skip (interval not met)

    Logic:
        1. Load etl_schedule_state.json
        2. Check last execution time for ticker,freq key
        3. If (now - last_run) < interval_minutes: return "skip_etl"
        4. Else: return "fetch_data"

    Example:
        Entry: {"ticker": "BTCUSDT", "freq": "1h", "interval_minutes": 60, "datasource": "yfinance"}
        Last run: 2025-12-23T14:00:00
        Now: 2025-12-23T14:30:00
        Elapsed: 30 minutes < 60 minutes
        Returns: "skip_etl"
    """
    logger = logging.getLogger("airflow.task.check_rate_limit")

    ticker = entry["ticker"]
    freq = entry["freq"]
    interval_minutes = entry["interval_minutes"]

    logger.info(
        f"Checking rate limit for {ticker} {freq} "
        f"(interval: {interval_minutes} minutes)"
    )

    # Check if should run based on state
    datasource = entry.get("datasource")
    should_run = should_run_etl(ticker, freq, interval_minutes, datasource=datasource)

    if should_run:
        logger.info(
            f"✓ Rate limit OK for {ticker} {freq} - proceeding with ETL"
        )
        return "etl_pipeline.select_datasource"
    else:
        logger.info(
            f"⊘ Rate limit not met for {ticker} {freq} - skipping ETL"
        )
        return "skip_etl"


@task
def skip_etl(entry: dict) -> dict:
    """
    Handle skip path when rate limit not met.

    Logs skip reason and returns status dict.

    Args:
        entry: Ticker config

    Returns:
        Dict with skip status:
        {
            "status": "skipped_interval",
            "ticker": str,
            "freq": str,
            "reason": str
    }

    This task is the target of the skip branch from check_rate_limit.
    It provides a clean termination point for the skip path.
    """
    logger = logging.getLogger("airflow.task.skip_etl")

    ticker = entry["ticker"]
    freq = entry["freq"]
    interval_minutes = entry.get("interval_minutes", 0)

    reason = f"Interval not met ({interval_minutes} minutes)"

    logger.info(
        f"Skipping ETL for {ticker} {freq}: {reason}"
    )

    return {
        "status": "skipped_interval",
        "ticker": ticker,
        "freq": freq,
        "reason": reason,
    }


@task.branch
def select_datasource(entry: dict) -> str:
    """
    Branch to the correct datasource fetch task.

    Returns:
        Full task path within etl_pipeline group
    """
    datasource = str(entry.get("datasource", "binance")).lower()
    if datasource == "yfinance":
        return "ticker_processing_group.etl_pipeline.fetch_yfinance_data"
    return "ticker_processing_group.etl_pipeline.fetch_binance_data"
