from __future__ import annotations

import fcntl
import json
import tempfile
from pathlib import Path
from typing import Dict

import pendulum


STATE_DIR = Path("data")
ETL_STATE_FILE = STATE_DIR / "etl_schedule_state.json"
ALERTS_STATE_FILE = STATE_DIR / "alerts_state.json"


def load_etl_state() -> Dict[str, str]:
    """
    Load ETL execution state from JSON file.

    Returns:
        Dict mapping "ticker,freq" keys to ISO8601 timestamp strings.
        Returns empty dict if file doesn't exist or on parse errors.

    Example:
        {
            "BTCUSDT,1h": "2025-12-23T10:30:00-06:00",
            "ETHUSDT,15m": "2025-12-23T10:15:00-06:00"
        }
    """
    if not ETL_STATE_FILE.exists():
        return {}

    try:
        with ETL_STATE_FILE.open("r") as f:
            # Acquire shared lock for reading
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                state = json.load(f)
                return state if isinstance(state, dict) else {}
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        return {}


def save_etl_state(state: Dict[str, str]) -> None:
    """
    Save ETL execution state to JSON file with atomic write.

    Args:
        state: Dict mapping "ticker,freq" keys to ISO8601 timestamps

    Uses atomic write pattern:
        1. Write to temporary file
        2. Rename to target (atomic operation)
        3. Prevents corruption from partial writes
    """
    ETL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file first (atomic write pattern)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=ETL_STATE_FILE.parent,
        delete=False,
        suffix=".tmp"
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)
        try:
            # Acquire exclusive lock for writing
            fcntl.flock(tmp_file.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(state, tmp_file, indent=2)
                tmp_file.flush()
            finally:
                fcntl.flock(tmp_file.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            tmp_path.replace(ETL_STATE_FILE)
        except Exception:
            # Clean up temp file on error
            if tmp_path.exists():
                tmp_path.unlink()
            raise


def update_etl_state(ticker: str, freq: str, timestamp: str = None, datasource: str | None = None) -> None:
    """
    Update last execution time for a ticker/freq pair.

    Args:
        ticker: Trading pair symbol (e.g., "BTCUSDT")
        freq: Frequency/timeframe (e.g., "1h", "15m")
        datasource: Source identifier ("binance" | "yfinance")
        timestamp: ISO8601 timestamp string (defaults to now if None)

    Example:
        update_etl_state("BTCUSDT", "1h", datasource="yfinance")
        # Sets "BTCUSDT,1h,yfinance": "2025-12-23T14:30:00-06:00"
    """
    state = load_etl_state()
    suffix = f",{datasource}" if datasource else ""
    key = f"{ticker},{freq}{suffix}"
    state[key] = timestamp or pendulum.now().to_iso8601_string()
    save_etl_state(state)


def should_run_etl(ticker: str, freq: str, interval_minutes: int, datasource: str | None = None) -> bool:
    """
    Check if enough time has passed since last ETL run.

    Args:
        ticker: Trading pair symbol
        freq: Frequency/timeframe
        interval_minutes: Minimum minutes between runs
        datasource: Source identifier ("binance" | "yfinance")

    Returns:
        True if should run ETL (no previous run or interval exceeded)
        False if should skip (too soon since last run)

    Example:
        should_run_etl("BTCUSDT", "1h", 60)
        # Returns True if >60 minutes since last run
    """
    state = load_etl_state()
    suffix = f",{datasource}" if datasource else ""
    key = f"{ticker},{freq}{suffix}"
    last_run = state.get(key)

    if not last_run:
        return True  # No previous run, should execute

    try:
        last_dt = pendulum.parse(last_run)
        now = pendulum.now()
        elapsed_minutes = (now - last_dt).total_minutes()
        return elapsed_minutes >= interval_minutes
    except Exception:
        # If can't parse timestamp, assume we should run
        return True


def cleanup_etl_state(retention_days: int = 30) -> int:
    """
    Remove state entries older than retention period.

    Args:
        retention_days: Delete entries with timestamps older than this

    Returns:
        Number of entries removed

    Example:
        removed = cleanup_etl_state(retention_days=30)
        # Returns: 5  (removed 5 entries older than 30 days)
    """
    state = load_etl_state()
    cutoff = pendulum.now().subtract(days=retention_days)
    removed = 0

    for key, timestamp in list(state.items()):
        try:
            dt = pendulum.parse(timestamp)
            if dt < cutoff:
                del state[key]
                removed += 1
        except Exception:
            # Keep unparseable entries (don't delete due to parse errors)
            continue

    if removed > 0:
        save_etl_state(state)

    return removed


def cleanup_alerts_state(retention_days: int = 30) -> int:
    """
    Remove alert state entries older than retention period.

    Args:
        retention_days: Delete entries with last_time older than this

    Returns:
        Number of entries removed

    Alert state format:
        {
            "BTCUSDT,1h,ma_signal": {
                "last_signal": 1,
                "last_time": "2025-12-23T09:00:00"
            }
        }
    """
    if not ALERTS_STATE_FILE.exists():
        return 0

    try:
        with ALERTS_STATE_FILE.open("r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                raw = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        return 0

    if not isinstance(raw, dict):
        return 0

    cutoff = pendulum.now().subtract(days=retention_days)
    removed = 0

    for key, value in list(raw.items()):
        if not isinstance(value, dict):
            continue

        last_time = value.get("last_time")
        if not last_time:
            continue

        try:
            dt = pendulum.parse(last_time)
            if dt < cutoff:
                del raw[key]
                removed += 1
        except Exception:
            # Keep unparseable entries
            continue

    if removed > 0:
        # Atomic write for alerts state
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=ALERTS_STATE_FILE.parent,
            delete=False,
            suffix=".tmp"
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            try:
                fcntl.flock(tmp_file.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(raw, tmp_file, indent=2)
                    tmp_file.flush()
                finally:
                    fcntl.flock(tmp_file.fileno(), fcntl.LOCK_UN)

                tmp_path.replace(ALERTS_STATE_FILE)
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise

    return removed
