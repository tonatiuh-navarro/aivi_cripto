from __future__ import annotations

import logging
import time
from typing import Any

import pendulum
from airflow.decorators import task


# Store DAG start time for duration calculation
_dag_start_time = None


@task
def aggregate_metrics(ticker_results: list[dict]) -> dict:
    """
    Consolidate execution statistics across all tickers.

    Aggregates XCom results from all ticker_processing_group instances.

    Args:
        ticker_results: List of persist_data outputs from Dynamic Task Mapping.
            Each element is a dict with keys:
            - status: "updated" | "up_to_date" | "skipped_interval"
            - ticker: str
            - freq: str
            - rows_added: int
            - total_rows: int

    Returns:
        Dict with aggregated metrics:
        {
            "total_tickers_processed": int,
            "total_rows_added": int,
            "total_alerts_sent": int,
            "success_count": int,
            "skip_count": int,
            "failure_count": int,
            "execution_time_seconds": float
        }

    Example input:
        [
            {"status": "updated", "ticker": "BTCUSDT", "freq": "1h", "rows_added": 100, "total_rows": 1000},
            {"status": "skipped_interval", "ticker": "ETHUSDT", "freq": "15m", "rows_added": 0, "total_rows": 0}
        ]

    Example output:
        {
            "total_tickers_processed": 2,
            "total_rows_added": 100,
            "total_alerts_sent": 0,
            "success_count": 1,
            "skip_count": 1,
            "failure_count": 0,
            "execution_time_seconds": 45.3
        }
    """
    logger = logging.getLogger("airflow.task.aggregate_metrics")

    # Calculate execution time
    global _dag_start_time
    if _dag_start_time is None:
        _dag_start_time = time.time()

    execution_time = time.time() - _dag_start_time

    # Initialize metrics
    total_tickers = len(ticker_results) if ticker_results else 0
    total_rows_added = 0
    total_alerts_sent = 0
    success_count = 0
    skip_count = 0
    failure_count = 0

    logger.info(f"Aggregating metrics from {total_tickers} ticker results")

    # Aggregate results
    if ticker_results:
        for result in ticker_results:
            if not isinstance(result, dict):
                logger.warning(f"Invalid result type: {type(result)}. Skipping.")
                continue

            status = result.get("status", "unknown")
            rows_added = result.get("rows_added", 0)

            # Accumulate rows
            total_rows_added += rows_added

            # Count statuses
            if status == "updated":
                success_count += 1
            elif status == "up_to_date":
                success_count += 1  # Still a successful run
            elif status == "skipped_interval":
                skip_count += 1
            else:
                failure_count += 1

    # Note: total_alerts_sent requires parsing signal_results
    # For simplicity, we'll set it to 0 here
    # (signal analysis happens in parallel to persist_data)
    # To get accurate alerts count, would need to pull from analyze_signals XCom

    metrics = {
        "total_tickers_processed": total_tickers,
        "total_rows_added": total_rows_added,
        "total_alerts_sent": total_alerts_sent,  # TODO: pull from analyze_signals
        "success_count": success_count,
        "skip_count": skip_count,
        "failure_count": failure_count,
        "execution_time_seconds": round(execution_time, 1),
    }

    logger.info(
        f"Aggregated metrics: "
        f"tickers={total_tickers}, "
        f"rows={total_rows_added}, "
        f"success={success_count}, "
        f"skip={skip_count}, "
        f"duration={metrics['execution_time_seconds']}s"
    )

    return metrics


# Initialize DAG start time when module loads
_dag_start_time = time.time()
