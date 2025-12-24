from __future__ import annotations

import json
import sys
from pathlib import Path

import pendulum
from airflow import DAG
from airflow.decorators import task, task_group
from airflow.models import Variable
from airflow.utils.dates import days_ago

# Add repo root to sys.path for imports
_resolved = Path(__file__).resolve()
_repo_root = None
for candidate in _resolved.parents:
    if (candidate / "data" / "etl" / "pipeline.py").exists():
        _repo_root = candidate
        break
if not _repo_root:
    _repo_root = _resolved.parents[2]
if str(_repo_root) not in sys.path:
    sys.path.append(str(_repo_root))

# Import callbacks
from data.etl.callbacks import (
    task_failure_callback,
    task_retry_callback,
    dag_success_callback,
)

# Import task modules
from data.etl.tasks.validation_tasks import (
    validate_config,
    pre_flight_check,
    validate_data_quality,
)
from data.etl.tasks.extraction_tasks import (
    fetch_binance_data,
    fetch_yfinance_data,
)
from data.etl.tasks.processing_tasks import transform_data
from data.etl.tasks.persistence_tasks import persist_data
from data.etl.tasks.signal_tasks import analyze_signals
from data.etl.tasks.notification_tasks import (
    send_notification,
    send_dag_completion_notification,
)
from data.etl.tasks.metrics_tasks import aggregate_metrics
from data.etl.tasks.cleanup_tasks import cleanup_old_states

# Frequency mapping
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


def freq_to_minutes(freq: str) -> int:
    """Convert frequency string to minutes."""
    key = freq.lower()
    if key not in FREQ_MINUTES:
        raise ValueError(f"Unsupported frequency: {freq}")
    return FREQ_MINUTES[key]


def load_etl_configs() -> list[dict]:
    """
    Load enabled ticker configs from etl_schedule.json at parse time.

    Returns:
        List of enabled ticker configurations.
    """
    cfg_path = Path("data/etl_schedule.json")
    default_datasource = Variable.get("DATASOURCE", default_var="yfinance").lower()

    if not cfg_path.exists():
        return []

    entries = json.loads(cfg_path.read_text())
    out = []

    for e in entries:
        # Skip disabled entries
        if not e.get("enabled", True):
            continue

        # Skip entries without freq
        freq = e.get("freq")
        if not freq:
            continue

        # Compute interval_minutes if not present
        if not e.get("interval_minutes"):
            e["interval_minutes"] = freq_to_minutes(freq)

        # Apply datasource default
        e["datasource"] = str(e.get("datasource") or default_datasource).lower()

        out.append(e)

    return out


# DAG definition
with DAG(
    dag_id="etl_signals_refactored",
    description="Refactored ETL pipeline using traditional loops (no dynamic mapping)",
    schedule=None,  # "*/15 * * * *",  # Every 15 minutes
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": pendulum.duration(minutes=5),
        "retry_exponential_backoff": True,
        "max_retry_delay": pendulum.duration(minutes=30),
        "on_failure_callback": task_failure_callback,
        "on_retry_callback": task_retry_callback,
    },
    on_success_callback=dag_success_callback,
    tags=["etl", "signals", "crypto", "refactored", "loop"],
) as dag:

    # Step 1: Pre-flight checks
    preflight = pre_flight_check()

    # Load configs at parse time
    etl_configs = load_etl_configs()

    ticker_results = []

    # Create a TaskGroup for each ticker (loop instead of .expand())
    for entry in etl_configs:
        ticker = entry["ticker"]
        freq = entry["freq"]
        datasource = entry.get("datasource", "binance").lower()

        # Create unique group_id for this ticker+freq combination
        group_id = f"{ticker}_{freq}".replace("/", "_").replace("-", "_")

        @task_group(group_id=group_id)
        def process_ticker(config: dict):
            """
            Process single ticker through full ETL pipeline.

            Pipeline flow:
                validate_config
                ↓
                fetch_data (with built-in rate limit check and skip)
                ↓
                transform → persist → validate_quality
                ↓
                analyze_signals → send_notification
            """
            # Step 1: Validate config
            validated_entry = validate_config(config)

            # Step 2: Fetch data - choose datasource at parse time
            # Fetch tasks include rate limit check and will skip if needed
            if config.get("datasource", "binance").lower() == "yfinance":
                raw_df = fetch_yfinance_data(validated_entry)
            else:
                raw_df = fetch_binance_data(validated_entry)

            # Step 3: Transform data (allow upstream skip)
            processed_df = transform_data(raw_df, validated_entry)

            # Step 4: Persist to parquet and update state
            persist_result = persist_data(processed_df, validated_entry)

            # Step 5: Validate data quality
            quality_result = validate_data_quality(persist_result)

            # Step 6: Analyze signals
            signal_result = analyze_signals(validated_entry, quality_result)

            # Step 7: Send notification
            send_notification(persist_result, signal_result, validated_entry)

            return persist_result

        # Create the task group instance for this ticker
        result = process_ticker(entry)
        ticker_results.append(result)

    # Step 4: Aggregate metrics from all tickers
    if ticker_results:
        metrics = aggregate_metrics(ticker_results)
    else:
        # If no tickers, create a dummy metrics task
        @task
        def empty_metrics() -> dict:
            return {"status": "no_tickers", "total": 0}

        metrics = empty_metrics()

    # Step 5: Cleanup old state entries
    cleanup = cleanup_old_states()

    # Step 6: Send DAG completion notification
    notify = send_dag_completion_notification(metrics)

    # Wire global dependencies
    preflight >> ticker_results

    if ticker_results:
        ticker_results >> metrics >> [cleanup, notify]
    else:
        preflight >> metrics >> [cleanup, notify]
