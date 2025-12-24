from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict
import json

import polars as pl
from airflow.decorators import task
from airflow.exceptions import AirflowException
from airflow.models import Variable


# Mapping of frequency strings to minutes
FREQ_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "45m": 45,
    "1h": 60,
    "4h": 240,
    "6h": 360,
    "12h": 720,
    "1d": 1440,
    "1w": 10080,
    "1month": 43200,
}


@task
def validate_config(entry: dict) -> dict:
    """
    Validate ticker configuration parameters.

    Args:
        entry: Ticker config from load_configs

    Returns:
        Validated config with computed interval_minutes

    Raises:
        ValueError: If ticker/freq invalid or missing required params

    Example input:
        {
            "ticker": "BTCUSDT",
            "freq": "1h",
            "atr_period": 14,
            "months": 6,
            "enabled": true
        }

    Example output:
        {
            "ticker": "BTCUSDT",
            "freq": "1h",
            "interval_minutes": 60,
            "atr_period": 14,
            "months": 6,
            "enabled": true
        }
    """
    logger = logging.getLogger("airflow.task.validate_config")

    # Check required fields
    if "ticker" not in entry:
        raise ValueError("Config missing required field: ticker")
    if "freq" not in entry:
        raise ValueError("Config missing required field: freq")

    ticker = entry["ticker"]
    freq = entry["freq"]

    # Validate frequency
    freq_key = freq.lower()
    if freq_key not in FREQ_MINUTES:
        raise ValueError(
            f"Unsupported frequency: {freq}. "
            f"Supported: {list(FREQ_MINUTES.keys())}"
        )

    # Compute interval_minutes if not present
    if "interval_minutes" not in entry:
        entry["interval_minutes"] = FREQ_MINUTES[freq_key]

    # Validate numeric fields
    if "atr_period" in entry and entry["atr_period"] <= 0:
        raise ValueError(f"atr_period must be > 0, got {entry['atr_period']}")

    if "months" in entry and entry["months"] <= 0:
        raise ValueError(f"months must be > 0, got {entry['months']}")

    # Datasource handling
    default_source = Variable.get("DATASOURCE", default_var="yfinance")
    datasource = str(entry.get("datasource") or default_source).lower()
    if datasource not in {"binance", "yfinance"}:
        raise ValueError("datasource must be 'binance' or 'yfinance'")
    entry["datasource"] = datasource

    logger.info(
        f"Validated config for {ticker} {freq} "
        f"(interval: {entry['interval_minutes']} minutes, source: {datasource})"
    )

    return entry


@task
def pre_flight_check() -> dict:
    """
    Validate system readiness before ETL execution.

    Checks:
        1. Required datasource reachability (Binance if used)
        2. Config files exist (etl_schedule.json, alerts_config.json)
        3. Data directory is writable
        4. Environment variables set (TELEGRAM_BOT_TOKEN, ALERT_CHAT_ID)

    Returns:
        Dict with check results:
        {
            "binance_api_ok": bool,
            "yfinance_ok": bool,
            "config_files_exist": bool,
            "data_dir_writable": bool,
            "env_vars_set": bool,
            "checks_passed": bool
        }

    Raises:
        AirflowException: If critical checks fail
    """
    logger = logging.getLogger("airflow.task.pre_flight_check")

    results = {
        "binance_api_ok": False,
        "yfinance_ok": True,  # assume OK unless proven otherwise
        "config_files_exist": False,
        "data_dir_writable": False,
        "env_vars_set": False,
        "checks_passed": False,
    }

    # Figure out datasources in use (config file entries or default variable)
    default_source = Variable.get("DATASOURCE", default_var="yfinance").lower()
    datasources = {default_source}
    schedule_path = Path("data/etl_schedule.json")
    if schedule_path.exists():
        try:
            entries = json.loads(schedule_path.read_text())
            for e in entries or []:
                ds = str(e.get("datasource") or default_source).lower()
                datasources.add(ds)
        except Exception as exc:
            logger.warning(f"No se pudo leer data/etl_schedule.json para fuentes: {exc}")

    # Check 1: Source reachability
    if "binance" in datasources:
        try:
            result = subprocess.run(
                ["curl", "-s", "-f", "https://api.binance.com/api/v3/ping"],
                check=False,
                capture_output=True,
                timeout=10,
            )
            results["binance_api_ok"] = result.returncode == 0

            if results["binance_api_ok"]:
                logger.info("✓ Binance API reachable")
            else:
                logger.error(
                    f"✗ Binance API unreachable. Return code: {result.returncode}"
                )
        except subprocess.TimeoutExpired:
            logger.error("✗ Binance API ping timed out")
        except Exception as e:
            logger.error(f"✗ Binance API check failed: {e}")
    else:
        # Not required for this run
        results["binance_api_ok"] = True
        logger.info("✓ Binance API check skipped (datasource != binance)")

    # yfinance reachability (lightweight import check)
    if "yfinance" in datasources:
        try:
            import yfinance  # noqa: F401
            results["yfinance_ok"] = True
            logger.info("✓ yfinance available")
        except Exception as exc:
            results["yfinance_ok"] = False
            logger.error(f"✗ yfinance unavailable: {exc}")

    # Check 2: Config files exist
    config_files = [
        Path("data/etl_schedule.json"),
        Path("data/alerts_config.json"),
    ]

    all_exist = all(f.exists() for f in config_files)
    results["config_files_exist"] = all_exist

    if all_exist:
        logger.info("✓ All config files exist")
    else:
        missing = [str(f) for f in config_files if not f.exists()]
        logger.error(f"✗ Missing config files: {missing}")

    # Check 3: Data directory writable
    data_dir = Path("data")
    test_file = data_dir / ".test_write"

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        test_file.write_text("test")
        test_file.unlink()
        results["data_dir_writable"] = True
        logger.info("✓ Data directory writable")
    except Exception as e:
        logger.error(f"✗ Data directory not writable: {e}")

    # Check 4: Environment variables
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("ALERT_CHAT_ID", "")

    if token and chat_id:
        results["env_vars_set"] = True
        logger.info("✓ Telegram credentials configured")
    else:
        # Warning only (not critical for ETL execution)
        logger.warning(
            "⚠ Telegram credentials not set. "
            "Notifications will be disabled. "
            "Set TELEGRAM_BOT_TOKEN and ALERT_CHAT_ID to enable."
        )
        results["env_vars_set"] = False

    # Overall check status
    critical_checks = [
        results["binance_api_ok"],
        results["config_files_exist"],
        results["data_dir_writable"],
    ]
    if "yfinance" in datasources:
        critical_checks.append(results["yfinance_ok"])

    results["checks_passed"] = all(critical_checks)

    if not results["checks_passed"]:
        raise AirflowException(
            "Pre-flight checks failed. See logs for details. "
            f"Results: {results}"
        )

    logger.info("✓ All pre-flight checks passed")
    return results


@task
def validate_data_quality(persist_result: dict) -> dict:
    """
    Validate data quality of persisted parquet file.

    Args:
        persist_result: Output from persist_data task containing parquet_path

    Returns:
        Dict with quality check results:
        {
            "has_nulls": bool,
            "null_columns": list[str],
            "has_duplicates": bool,
            "duplicate_count": int,
            "price_range_valid": bool,
            "timestamps_monotonic": bool,
            "quality_passed": bool
        }

    Checks:
        1. Nulls in critical columns [open_time, open, high, low, close, volume]
        2. Duplicates on open_time key
        3. Price/volume ranges (prices > 0, volumes >= 0)
        4. Monotonic increasing open_time

    Raises:
        AirflowException: If critical quality issues detected
    """
    logger = logging.getLogger("airflow.task.validate_data_quality")

    parquet_path = Path(persist_result.get("parquet_path", ""))

    if not parquet_path.exists():
        raise AirflowException(f"Parquet file not found: {parquet_path}")

    # Read parquet
    try:
        df = pl.read_parquet(parquet_path)
    except Exception as e:
        raise AirflowException(f"Failed to read parquet: {e}")

    results = {
        "has_nulls": False,
        "null_columns": [],
        "has_duplicates": False,
        "duplicate_count": 0,
        "price_range_valid": True,
        "timestamps_monotonic": True,
        "quality_passed": True,
    }

    # Check 1: Nulls in critical columns
    critical_columns = ["open_time", "open", "high", "low", "close", "volume"]
    existing_columns = [c for c in critical_columns if c in df.columns]

    null_counts = df.select(
        [pl.col(c).is_null().sum().alias(c) for c in existing_columns]
    )

    null_columns = []
    for col in existing_columns:
        null_count = null_counts[col][0]
        if null_count > 0:
            null_columns.append(col)
            logger.warning(f"Found {null_count} nulls in column '{col}'")

    results["has_nulls"] = len(null_columns) > 0
    results["null_columns"] = null_columns

    # Check 2: Duplicates on open_time
    if "open_time" in df.columns:
        total_rows = df.height
        unique_rows = df.select(pl.col("open_time")).n_unique()
        duplicate_count = total_rows - unique_rows

        results["has_duplicates"] = duplicate_count > 0
        results["duplicate_count"] = duplicate_count

        if duplicate_count > 0:
            logger.warning(f"Found {duplicate_count} duplicate open_time values")

    # Check 3: Price/volume ranges
    price_columns = ["open", "high", "low", "close"]
    existing_price_cols = [c for c in price_columns if c in df.columns]

    if existing_price_cols:
        invalid_prices = df.filter(
            pl.any_horizontal([pl.col(c) <= 0 for c in existing_price_cols])
        ).height

        if invalid_prices > 0:
            results["price_range_valid"] = False
            logger.error(f"Found {invalid_prices} rows with prices <= 0")

    if "volume" in df.columns:
        invalid_volumes = df.filter(pl.col("volume") < 0).height

        if invalid_volumes > 0:
            results["price_range_valid"] = False
            logger.error(f"Found {invalid_volumes} rows with volumes < 0")

    # Check 4: Monotonic increasing timestamps
    if "open_time" in df.columns:
        # Check if open_time is sorted
        sorted_df = df.sort("open_time")
        is_monotonic = df["open_time"].equals(sorted_df["open_time"])

        results["timestamps_monotonic"] = is_monotonic

        if not is_monotonic:
            logger.warning("Timestamps are not monotonically increasing")

    # Overall quality assessment
    critical_issues = [
        results["has_nulls"],
        not results["price_range_valid"],
    ]

    results["quality_passed"] = not any(critical_issues)

    if not results["quality_passed"]:
        logger.error(f"Data quality checks failed: {results}")
        raise AirflowException(
            f"Data quality validation failed for {parquet_path}. "
            f"Results: {results}"
        )

    logger.info(
        f"✓ Data quality validation passed for {persist_result.get('ticker')} "
        f"{persist_result.get('freq')}"
    )

    return results
