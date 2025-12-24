from __future__ import annotations

import logging
import os
import subprocess
from typing import Any, Dict


def task_failure_callback(context: Dict[str, Any]) -> None:
    """
    Send Telegram alert on task failure.

    Args:
        context: Airflow context dict containing:
            - task_instance: TaskInstance object
            - dag: DAG object
            - execution_date: Execution datetime
            - exception: Exception that caused failure

    Notification format:
        ⚠️ TASK FAILURE
        DAG: etl_signals_refactored
        Task: fetch_data
        Execution: 2025-12-23T14:30:00
        Error: ConnectionError: Failed to...
        Try: 2/3
    """
    ti = context["task_instance"]
    dag_id = context["dag"].dag_id
    task_id = ti.task_id
    execution_date = context["execution_date"]
    exception = context.get("exception")

    logger = logging.getLogger(f"airflow.task.{task_id}.callback")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("ALERT_CHAT_ID", "")

    if not token or not chat_id:
        logger.warning(
            f"Task {task_id} failed but no Telegram credentials configured. "
            f"Set TELEGRAM_BOT_TOKEN and ALERT_CHAT_ID to enable notifications."
        )
        return

    # Format error message (truncate to 200 chars)
    error_msg = str(exception)[:200] if exception else "Unknown error"

    text = (
        f"⚠️ TASK FAILURE\n"
        f"DAG: {dag_id}\n"
        f"Task: {task_id}\n"
        f"Execution: {execution_date}\n"
        f"Error: {error_msg}\n"
        f"Try: {ti.try_number}/{ti.max_tries}"
    )

    _send_telegram(token, chat_id, text, logger)


def task_retry_callback(context: Dict[str, Any]) -> None:
    """
    Log retry attempts with exponential backoff info.

    Args:
        context: Airflow context dict

    Logs warning with retry count and backoff delay information.
    """
    ti = context["task_instance"]
    task = context["task"]
    logger = logging.getLogger(f"airflow.task.{ti.task_id}.callback")

    retry_delay = task.retry_delay

    if task.retry_exponential_backoff:
        # Calculate exponential backoff: delay * 2^(try_number - 1)
        backoff_delay = retry_delay * (2 ** (ti.try_number - 1))
        max_delay = task.max_retry_delay or retry_delay * 10

        # Cap at max_retry_delay
        actual_delay = min(backoff_delay, max_delay)

        logger.warning(
            f"Task {ti.task_id} retry {ti.try_number}/{ti.max_tries}. "
            f"Next retry in {actual_delay} (exponential backoff)"
        )
    else:
        logger.warning(
            f"Task {ti.task_id} retry {ti.try_number}/{ti.max_tries}. "
            f"Next retry in {retry_delay}"
        )


def dag_success_callback(context: Dict[str, Any]) -> None:
    """
    Send DAG-level success notification via Telegram.

    Args:
        context: Airflow context dict containing:
            - dag_run: DagRun object
            - execution_date: Execution datetime

    Attempts to pull metrics from aggregate_metrics task via XCom.
    If metrics available, sends detailed summary. Otherwise sends basic success message.

    Notification format:
        ✅ DAG SUCCESS: etl_signals_refactored
        Execution: 2025-12-23T14:30:00
        Tickers processed: 2
        Rows added: 150
        Alerts sent: 1
        Duration: 45.3s
    """
    dag_run = context["dag_run"]
    execution_date = context["execution_date"]

    logger = logging.getLogger(f"airflow.dag.{dag_run.dag_id}.callback")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("ALERT_CHAT_ID", "")

    if not token or not chat_id:
        logger.info(
            f"DAG {dag_run.dag_id} completed successfully but no Telegram credentials configured."
        )
        return

    # Try to pull metrics from aggregate_metrics task
    try:
        # Get task instance for aggregate_metrics
        ti = context.get("ti")
        if ti:
            # Pull XCom value from aggregate_metrics task
            metrics = ti.xcom_pull(task_ids="aggregate_metrics", key="return_value")

            if metrics and isinstance(metrics, dict):
                text = (
                    f"✅ DAG SUCCESS: {dag_run.dag_id}\n"
                    f"Execution: {execution_date}\n"
                    f"Tickers processed: {metrics.get('total_tickers_processed', 0)}\n"
                    f"Rows added: {metrics.get('total_rows_added', 0)}\n"
                    f"Alerts sent: {metrics.get('total_alerts_sent', 0)}\n"
                    f"Duration: {metrics.get('execution_time_seconds', 0):.1f}s"
                )
            else:
                # Fallback to basic success message
                text = (
                    f"✅ DAG SUCCESS: {dag_run.dag_id}\n"
                    f"Execution: {execution_date}\n"
                    f"Status: Completed"
                )
        else:
            text = (
                f"✅ DAG SUCCESS: {dag_run.dag_id}\n"
                f"Execution: {execution_date}"
            )
    except Exception as e:
        logger.warning(f"Failed to pull metrics from aggregate_metrics: {e}")
        text = (
            f"✅ DAG SUCCESS: {dag_run.dag_id}\n"
            f"Execution: {execution_date}"
        )

    _send_telegram(token, chat_id, text, logger)


def _send_telegram(token: str, chat_id: str, text: str, logger: logging.Logger = None) -> None:
    """
    Send message via Telegram Bot API using subprocess curl.

    Args:
        token: Telegram bot token
        chat_id: Telegram chat ID
        text: Message text to send
        logger: Optional logger for logging success/failure

    Uses curl subprocess with timeout to avoid blocking.
    Fails silently (logs warning but doesn't raise) to prevent callback failures.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    if logger is None:
        logger = logging.getLogger("airflow.callback.telegram")

    try:
        result = subprocess.run(
            [
                "curl",
                "-s",  # Silent mode
                "-X", "POST",
                url,
                "-d", f"chat_id={chat_id}",
                "-d", f"text={text}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,  # 10 second timeout
        )

        if result.returncode == 0:
            logger.info(f"Telegram notification sent successfully to chat {chat_id}")
        else:
            logger.warning(
                f"Telegram notification failed. Return code: {result.returncode}. "
                f"Stderr: {result.stderr[:200]}"
            )
    except subprocess.TimeoutExpired:
        logger.warning("Telegram notification timed out after 10 seconds")
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification: {e}")
