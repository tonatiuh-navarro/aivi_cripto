from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

import polars as pl
from airflow.decorators import task


@task
def send_notification(persist_result: dict, signal_result: dict, entry: dict) -> None:
    """
    Send per-ticker ETL notification via Telegram.

    Args:
        persist_result: Output from persist_data with keys:
            - status: "updated" | "up_to_date"
            - ticker: str
            - freq: str
            - rows_added: int
            - total_rows: int
        signal_result: Output from analyze_signals with keys:
            - signals_detected: int
            - alerts_sent: int
        entry: Ticker config

    Message format:
        ETL BTCUSDT 1h | Status: updated | Rows: +150/1000 | Signals: 1

    Uses subprocess + curl to send via Telegram Bot API.
    Fails silently if credentials not configured.
    """
    logger = logging.getLogger("airflow.task.send_notification")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("ALERT_CHAT_ID", "")

    if not token or not chat_id:
        logger.info(
            f"Skipping notification for {persist_result.get('ticker')} "
            f"{persist_result.get('freq')} - no Telegram credentials configured"
        )
        return

    # Extract basic info
    ticker = persist_result.get("ticker", "unknown")
    freq = persist_result.get("freq", "unknown")
    status = persist_result.get("status", "unknown")
    datasource = persist_result.get("datasource", "binance")
    rows_added = persist_result.get("rows_added", 0)
    total_rows = persist_result.get("total_rows", 0)
    signals_detected = signal_result.get("signals_detected", 0)
    parquet_path = persist_result.get("parquet_path", "")

    # Read parquet file for detailed stats
    date_range = "N/A"
    last_price = "N/A"
    file_size = "N/A"
    period_desc = ""

    try:
        if parquet_path and Path(parquet_path).exists():
            df = pl.read_parquet(parquet_path)

            # Get date range
            if "open_time" in df.columns and df.height > 0:
                min_time = df["open_time"].min()
                max_time = df["open_time"].max()

                # Convert to datetime if needed
                if isinstance(min_time, int):
                    min_dt = datetime.fromtimestamp(min_time / 1000)
                    max_dt = datetime.fromtimestamp(max_time / 1000)
                else:
                    min_dt = min_time
                    max_dt = max_time

                date_range = f"{min_dt.strftime('%b %d')} → {max_dt.strftime('%b %d, %Y %H:%M')}"

                # Calculate period in months/days
                days = (max_dt - min_dt).days
                if days >= 60:
                    months = round(days / 30)
                    period_desc = f"{total_rows:,} filas ({months} meses de datos)"
                else:
                    period_desc = f"{total_rows:,} filas ({days} días de datos)"

            # Get last price
            if "close" in df.columns and df.height > 0:
                last_close = df["close"][-1]
                last_price = f"${last_close:,.2f}"

            # Get file size
            file_size_bytes = Path(parquet_path).stat().st_size
            if file_size_bytes < 1024:
                file_size = f"{file_size_bytes}B"
            elif file_size_bytes < 1024 * 1024:
                file_size = f"{file_size_bytes / 1024:.1f}KB"
            else:
                file_size = f"{file_size_bytes / (1024 * 1024):.1f}MB"

    except Exception as e:
        logger.warning(f"Failed to read parquet for detailed stats: {e}")

    # Format rich notification message
    text = (
        f"✅ ETL {ticker.upper()} {freq} ({datasource})\n"
        f"Status: {status} | +{rows_added} filas\n"
        f"{period_desc}\n"
        f"Rango: {date_range}\n"
        f"Último precio: {last_price}\n"
        f"Archivo: {parquet_path} ({file_size})\n"
        f"Señales: {signals_detected}"
    )

    logger.info(f"Sending notification: {text}")

    # Send via curl subprocess
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X", "POST",
                url,
                "-d", f"chat_id={chat_id}",
                "-d", f"text={text}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            logger.info(f"Notification sent successfully for {ticker} {freq}")
        else:
            logger.warning(
                f"Notification failed for {ticker} {freq}. "
                f"Return code: {result.returncode}"
            )
    except subprocess.TimeoutExpired:
        logger.warning(f"Notification timed out for {ticker} {freq}")
    except Exception as e:
        logger.warning(f"Failed to send notification for {ticker} {freq}: {e}")


@task
def send_dag_completion_notification(metrics: dict) -> None:
    """
    Send DAG-level completion summary via Telegram.

    Args:
        metrics: Output from aggregate_metrics with keys:
            - total_tickers_processed: int
            - total_rows_added: int
            - total_alerts_sent: int
            - success_count: int
            - skip_count: int
            - failure_count: int
            - execution_time_seconds: float

    Message format:
        ✅ DAG SUCCESS: etl_signals_refactored
        Tickers: 2 | Rows: +150 | Alerts: 1
        Success: 2 | Skipped: 0 | Failed: 0
        Duration: 45.3s

    Fails silently if credentials not configured.
    """
    logger = logging.getLogger("airflow.task.send_dag_completion_notification")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("ALERT_CHAT_ID", "")

    if not token or not chat_id:
        logger.info("Skipping DAG completion notification - no Telegram credentials")
        return

    # Format message
    total_tickers = metrics.get("total_tickers_processed", 0)
    total_rows = metrics.get("total_rows_added", 0)
    total_alerts = metrics.get("total_alerts_sent", 0)
    success = metrics.get("success_count", 0)
    skip = metrics.get("skip_count", 0)
    failure = metrics.get("failure_count", 0)
    duration = metrics.get("execution_time_seconds", 0)

    text = (
        f"✅ DAG SUCCESS: etl_signals_refactored\n"
        f"Tickers: {total_tickers} | Rows: +{total_rows} | Alerts: {total_alerts}\n"
        f"Success: {success} | Skipped: {skip} | Failed: {failure}\n"
        f"Duration: {duration:.1f}s"
    )

    logger.info(f"Sending DAG completion notification: {text}")

    # Send via curl subprocess
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X", "POST",
                url,
                "-d", f"chat_id={chat_id}",
                "-d", f"text={text}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            logger.info("DAG completion notification sent successfully")
        else:
            logger.warning(
                f"DAG completion notification failed. "
                f"Return code: {result.returncode}"
            )
    except subprocess.TimeoutExpired:
        logger.warning("DAG completion notification timed out")
    except Exception as e:
        logger.warning(f"Failed to send DAG completion notification: {e}")
