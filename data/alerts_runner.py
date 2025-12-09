from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

import polars as pl

from utils.logging_utils import setup_logger_for_child
from utils.strategy_utils import apply_pipeline


def load_alerts_config(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r") as f:
        return json.load(f)


def load_alerts_state(path: Path) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r") as f:
        raw = json.load(f)
    out = {}
    for key, val in raw.items():
        parts = key.split(",")
        if len(parts) != 3:
            continue
        out[(parts[0], parts[1], parts[2])] = val
    return out


def save_alerts_state(path: Path, state: Dict[Tuple[str, str, str], Dict[str, Any]]) -> None:
    payload = {f"{k[0]},{k[1]},{k[2]}": v for k, v in state.items()}
    with path.open("w") as f:
        json.dump(payload, f, indent=2)


def send_telegram(text: str, chat_id: str, token: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    subprocess.run(
        ["curl", "-s", "-X", "POST", url, "-d", f"chat_id={chat_id}", "-d", f"text={text}"],
        check=False,
        capture_output=True,
        text=True,
    )


def build_stages(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    stages = []
    entry = cfg.get("entry")
    tp = cfg.get("target_price")
    sl = cfg.get("stop_loss")
    if entry:
        stages.append({"kind": "entry", "name": entry["name"], "params": entry.get("params", {})})
    if tp:
        stages.append({"kind": "target_price", "name": tp["name"], "params": tp.get("params", {})})
    if sl:
        stages.append({"kind": "stop_loss", "name": sl["name"], "params": sl.get("params", {})})
    stages.append({"kind": "general_transformations", "name": "simulate_trades", "params": {}})
    return stages


def detect_signal(df: pl.DataFrame) -> Tuple[bool, int, Any, Any]:
    if df.is_empty():
        return False, 0, None, None
    last = df.tail(1)
    signal = last["signal"][0] if "signal" in last.columns else None
    trade_event = last["trade_event"][0] if "trade_event" in last.columns else None
    time = last["open_time"][0] if "open_time" in last.columns else None
    return bool(trade_event), signal, time, last


def run_signal_check(ticker: str, freq: str, config_path: Path, state_path: Path, logger=None) -> None:
    log = logger or setup_logger_for_child(
        parent_name="alerts",
        child_name="runner",
        log_level="INFO",
        console=True,
    )
    cfgs = load_alerts_config(config_path)
    cfgs = [c for c in cfgs if c.get("enabled") and c.get("ticker") == ticker and c.get("freq") == freq]
    if not cfgs:
        return
    parquet_path = Path(f"data/market_data_{ticker.lower()}_{freq.lower()}.parquet")
    if not parquet_path.exists():
        log.warning(f"Parquet no encontrado para {ticker} {freq}")
        return
    try:
        df = pl.read_parquet(parquet_path)
    except Exception as exc:
        log.error(f"No se pudo leer parquet {parquet_path}: {exc}")
        return
    state = load_alerts_state(state_path)
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        log.warning("TELEGRAM_BOT_TOKEN no definido; no se enviarán alertas")
    for cfg in cfgs:
        stages = build_stages(cfg)
        window = df.tail(500)
        res = apply_pipeline(df=window, stages=stages)
        if not isinstance(res, pl.DataFrame):
            continue
        has_signal, signal, open_time, _ = detect_signal(res)
        if not has_signal or signal is None:
            continue
        key = (cfg["ticker"], cfg["freq"], cfg["entry"]["name"])
        last_entry = state.get(key, {})
        last_signal = last_entry.get("last_signal")
        last_time = last_entry.get("last_time")
        throttle = int(cfg.get("throttle_seconds") or 0)
        if last_signal == signal and last_time == str(open_time):
            continue
        if throttle and last_time:
            try:
                last_dt = pl.datetime.strptime(last_time, "%Y-%m-%dT%H:%M:%S").to_python()
                if open_time and (open_time - last_dt).total_seconds() < throttle:
                    continue
            except Exception:
                pass
        text = (
            f"{cfg['ticker']} {cfg['freq']} señal "
            f"{'LONG' if signal == 1 else 'SHORT'}\n"
            f"Precio: {res.tail(1)['close'][0] if 'close' in res.columns else ''}\n"
            f"Hora: {open_time}"
        )
        if token and cfg.get("chat_id"):
            send_telegram(text, cfg["chat_id"], token)
        state[key] = {"last_signal": signal, "last_time": str(open_time)}
    save_alerts_state(state_path, state)
