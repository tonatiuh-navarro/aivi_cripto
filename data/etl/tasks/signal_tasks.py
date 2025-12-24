from __future__ import annotations

import json
import logging
from pathlib import Path

from airflow.decorators import task

from data.alerts_runner import run_signal_check


@task
def analyze_signals(entry: dict, quality_result: dict) -> dict:
    """
    Run signal detection on processed market data.

    Wrapper around run_signal_check from data.alerts_runner that:
    1. Detects trading signals based on alerts_config.json
    2. Sends Telegram notifications for new signals
    3. Updates alerts_state.json to prevent duplicate alerts

    Args:
        entry: Ticker config with keys:
            - ticker: str
            - freq: str
        quality_result: Output from validate_data_quality
            (ensures signals only run on quality-validated data)

    Returns:
        Dict with signal detection stats:
        {
            "signals_detected": int,
            "alerts_sent": int,
            "last_signal": int | None,
            "last_signal_time": str | None,
            "quality_passed": bool
        }

    Implementation:
        - Calls run_signal_check from data.alerts_runner
        - Parses alerts_state.json to count signals detected
        - Returns signal stats for aggregate_metrics
    """
    logger = logging.getLogger("airflow.task.analyze_signals")

    ticker = entry["ticker"]
    freq = entry["freq"]

    # Pass through quality check status
    quality_passed = quality_result.get("quality_passed", True)

    logger.info(
        f"Analyzing signals for {ticker} {freq} "
        f"(quality_passed: {quality_passed})"
    )

    # Config and state paths
    config_path = Path("data/alerts_config.json")
    state_path = Path("data/alerts_state.json")

    # Load state before signal check
    state_before = {}
    if state_path.exists():
        try:
            state_before = json.loads(state_path.read_text())
        except Exception:
            state_before = {}

    # Run signal check
    # This will:
    # 1. Load alerts from alerts_config.json matching ticker/freq
    # 2. Apply strategy pipeline to last 500 candles
    # 3. Detect signals from last row
    # 4. Send Telegram notifications if new signals
    # 5. Update alerts_state.json
    run_signal_check(ticker, freq, config_path, state_path, logger)

    # Load state after signal check
    state_after = {}
    if state_path.exists():
        try:
            state_after = json.loads(state_path.read_text())
        except Exception:
            state_after = {}

    # Count signals detected (new entries in state)
    # State keys are: "ticker,freq,entry_name"
    state_keys_before = set(state_before.keys())
    state_keys_after = set(state_after.keys())

    new_signals = state_keys_after - state_keys_before
    signals_detected = len(new_signals)

    # Get last signal info (if any)
    last_signal = None
    last_signal_time = None

    # Find state entries matching this ticker/freq
    prefix = f"{ticker},{freq},"
    matching_keys = [k for k in state_after.keys() if k.startswith(prefix)]

    if matching_keys:
        # Get most recent signal
        latest_key = max(
            matching_keys,
            key=lambda k: state_after[k].get("last_time", ""),
        )
        last_signal = state_after[latest_key].get("last_signal")
        last_signal_time = state_after[latest_key].get("last_time")

    logger.info(
        f"Signal analysis complete for {ticker} {freq}: "
        f"signals_detected={signals_detected}, "
        f"last_signal={last_signal}"
    )

    return {
        "signals_detected": signals_detected,
        "alerts_sent": signals_detected,  # 1:1 mapping (each signal sends alert)
        "last_signal": last_signal,
        "last_signal_time": last_signal_time,
        "quality_passed": quality_passed,
    }
