from __future__ import annotations

import argparse
import json
import subprocess
from configparser import ConfigParser
import datetime as dt
from datetime import timedelta
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
import logging

from utils.logging_utils import setup_logger_for_child
from data.alerts_runner import run_signal_check


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
    freq_norm = freq.lower()
    if freq_norm not in FREQ_MINUTES:
        raise ValueError(f"Frecuencia no soportada: {freq}")
    return FREQ_MINUTES[freq_norm]


def load_config(path: Path) -> List[Dict[str, Any]]:
    if path.suffix.lower() in {".json"}:
        with path.open("r") as f:
            data = json.load(f)
        return data
    parser = ConfigParser()
    parser.read(path)
    entries: List[Dict[str, Any]] = []
    for section in parser.sections():
        entry = {"ticker": section, "freq": parser.get(section, "freq", fallback=None)}
        if not entry["freq"]:
            continue
        for key in ["atr_period", "months", "start", "end", "limit", "output", "interval_minutes", "enabled"]:
            if parser.has_option(section, key):
                entry[key] = parser.get(section, key)
        entries.append(entry)
    return entries


def load_state(path: Path) -> Dict[Tuple[str, str], dt.datetime]:
    if not path.exists():
        return {}
    try:
        with path.open("r") as f:
            raw = json.load(f)
        out = {}
        for key, ts in raw.items():
            if not isinstance(key, str) or "," not in key:
                continue
            ticker, freq = key.split(",", 1)
            out[(ticker, freq)] = dt.datetime.fromisoformat(ts)
        return out
    except Exception:
        return {}


def save_state(path: Path, state: Dict[Tuple[str, str], dt.datetime]) -> None:
    payload = {f"{k[0]},{k[1]}": v.isoformat() for k, v in state.items()}
    with path.open("w") as f:
        json.dump(payload, f, indent=2)


def should_run(entry: Dict[str, Any], state: Dict[Tuple[str, str], dt.datetime], now: dt.datetime) -> bool:
    ticker = entry["ticker"]
    freq = entry["freq"]
    last = state.get((ticker, freq))
    interval = entry.get("interval_minutes")
    interval = int(interval) if interval is not None else freq_to_minutes(freq)
    if last is None:
        return True
    return (now - last) >= timedelta(minutes=interval)


def run_entry(entry: Dict[str, Any]) -> subprocess.CompletedProcess:
    args = [
        "python",
        "-m",
        "data.etl.cli",
        "--ticker",
        entry["ticker"],
        "--freq",
        entry["freq"],
    ]
    for opt in ["start", "end", "limit", "atr_period", "months", "output"]:
        if opt in entry and entry[opt] not in (None, "", "None"):
            args.extend([f"--{opt.replace('_', '-')}", str(entry[opt])])
    return subprocess.run(args, capture_output=True, text=True)


def acquire_lock(lockfile: Path) -> bool:
    if lockfile.exists():
        return False
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    lockfile.touch()
    return True


def release_lock(lockfile: Path) -> None:
    if lockfile.exists():
        lockfile.unlink()


def parse_args():
    parser = argparse.ArgumentParser(description="Scheduler secuencial para ETL de mercado.")
    parser.add_argument("--config", required=True, help="Ruta de config (json o cfg/ini).")
    parser.add_argument("--state", default="data/etl_schedule_state.json", help="Ruta para guardar last_run.")
    parser.add_argument("--lockfile", default="data/etl_schedule.lock", help="Ruta de lockfile.")
    parser.add_argument("--once", action="store_true", help="Ejecuta una pasada y termina.")
    parser.add_argument("--loop", action="store_true", help="Ejecuta en bucle cada 15m alineado a 00/15/30/45.")
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logger_for_child(
        parent_name="data_scheduler",
        child_name="run",
        log_level="INFO",
        console=True,
    )
    # Ajustar formato de tiempo a ISO8601 con offset
    iso_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    iso_formatter.formatTime = lambda record, datefmt=None: dt.datetime.fromtimestamp(
        record.created
    ).astimezone().isoformat(timespec="seconds")
    for handler in logger.handlers:
        handler.setFormatter(iso_formatter)
    cfg_path = Path(args.config)
    state_path = Path(args.state)
    lockfile = Path(args.lockfile)

    def run_once():
        entries = load_config(cfg_path)
        state = load_state(state_path)
        now = dt.datetime.now().astimezone()
        for entry in entries:
            if not entry.get("ticker") or not entry.get("freq"):
                logger.warning(f"Entrada inválida (faltan campos): {entry}")
                continue
            if str(entry.get("enabled")).lower() == "false":
                continue
            if not should_run(entry, state, now):
                logger.info(f"Skip {entry['ticker']} {entry['freq']} (no toca)")
                continue
            logger.info(f"Iniciando {entry['ticker']} {entry['freq']}")
            res = run_entry(entry)
            if res.returncode != 0:
                logger.error(
                    f"Fallo {entry['ticker']} {entry['freq']}: rc={res.returncode} stderr={res.stderr.strip()}"
                )
            else:
                logger.info(f"OK {entry['ticker']} {entry['freq']}")
                state[(entry["ticker"], entry["freq"])] = now
                alerts_cfg = Path("data/alerts_config.json")
                alerts_state = Path("data/alerts_state.json")
                run_signal_check(entry["ticker"], entry["freq"], alerts_cfg, alerts_state, logger)
        save_state(state_path, state)

    def sleep_until_next_quarter():
        now = dt.datetime.now().astimezone()
        next_minute = (now.minute // 15 + 1) * 15
        if next_minute == 60:
            target = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            target = now.replace(minute=next_minute, second=0, microsecond=0)
        delta = (target - now).total_seconds()
        if delta > 0:
            logger.info(f"Dormir {delta:.1f}s hasta {target.isoformat()}")
            time.sleep(delta)

    if not args.loop:
        if not acquire_lock(lockfile):
            logger.warning("Lockfile presente; otra instancia está corriendo. Abortando.")
            return
        try:
            run_once()
        finally:
            release_lock(lockfile)
        return

    while True:
        if not acquire_lock(lockfile):
            logger.warning("Lockfile presente; esperando siguiente tick.")
            sleep_until_next_quarter()
            continue
        try:
            run_once()
        finally:
            release_lock(lockfile)
        sleep_until_next_quarter()


if __name__ == "__main__":
    main()
