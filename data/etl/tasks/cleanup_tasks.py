from __future__ import annotations

import logging

from airflow.decorators import task

from data.etl.state_manager import cleanup_etl_state, cleanup_alerts_state


@task
def cleanup_old_states(retention_days: int = 30) -> dict:
    """
    Purge old entries from state files.

    Removes entries older than retention_days from:
    1. data/etl_schedule_state.json (ETL execution timestamps)
    2. data/alerts_state.json (alert signal history)

    Args:
        retention_days: Delete entries with timestamps older than this (default 30)

    Returns:
        Dict with cleanup results:
        {
            "etl_state_entries_removed": int,
            "alerts_state_entries_removed": int,
            "total_entries_removed": int,
            "retention_days": int
        }

    Example:
        cleanup_old_states(retention_days=30)
        # Removes all entries older than 30 days
        # Returns: {"etl_state_entries_removed": 5, "alerts_state_entries_removed": 3, ...}

    This task helps prevent state files from growing indefinitely.
    It's safe to run regularly as it only removes very old entries.
    """
    logger = logging.getLogger("airflow.task.cleanup_old_states")

    logger.info(
        f"Cleaning up state files (retention: {retention_days} days)"
    )

    # Cleanup ETL state
    etl_removed = cleanup_etl_state(retention_days)
    logger.info(f"Removed {etl_removed} entries from etl_schedule_state.json")

    # Cleanup alerts state
    alerts_removed = cleanup_alerts_state(retention_days)
    logger.info(f"Removed {alerts_removed} entries from alerts_state.json")

    # Total
    total_removed = etl_removed + alerts_removed

    result = {
        "etl_state_entries_removed": etl_removed,
        "alerts_state_entries_removed": alerts_removed,
        "total_entries_removed": total_removed,
        "retention_days": retention_days,
    }

    logger.info(
        f"Cleanup complete: removed {total_removed} total entries "
        f"(ETL: {etl_removed}, Alerts: {alerts_removed})"
    )

    return result
