from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pendulum
import polars as pl
from airflow import DAG
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv
from airflow.configuration import conf

# Resolver raíz del repo buscando carpeta con data/etl/pipeline.py
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
DATA_DIR = _repo_root / "data"
load_dotenv(_repo_root / ".env")

from data.etl.pipeline import build_market_etl_pipeline  # noqa: E402
from data.alerts_runner import run_signal_check  # noqa: E402
from utils.logging_utils import build_task_log_path  # noqa: E402


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
    key = freq.lower()
    if key not in FREQ_MINUTES:
        raise ValueError(f"Frecuencia no soportada: {freq}")
    return FREQ_MINUTES[key]


def load_entries() -> list[dict]:
    cfg_path = DATA_DIR / "etl_schedule.json"
    if not cfg_path.exists():
        return []
    entries = json.loads(cfg_path.read_text())
    out = []
    for e in entries:
        if not e.get("enabled", True):
            continue
        freq = e.get("freq")
        if not freq:
            continue
        if not e.get("interval_minutes"):
            e["interval_minutes"] = freq_to_minutes(freq)
        out.append(e)
    return out


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def run_etl(entry: dict, ti=None) -> None:
    logger = logging.getLogger("etl_signals.etl")
    if ti:
        exec_str = ti.execution_date.isoformat()
        safe_exec = exec_str.replace(":", "-").replace("+", "-")
        filename = f"attempt={safe_exec}_{ti.try_number}.log"
        base_dir = Path(conf.get("logging", "base_log_folder", fallback=_repo_root / "airflow_home" / "logs"))
        log_path = build_task_log_path(
            base_dir=base_dir,
            dag_id=ti.dag_id,
            run_id=ti.run_id,
            task_id=ti.task_id,
            filename=filename,
        )
        os.environ["METAENGINE_LOG_FILE"] = str(log_path)
    state_path = Path("data/etl_schedule_state.json")
    state = load_state(state_path)
    key = f"{entry['ticker']},{entry['freq']}"
    interval = int(entry.get("interval_minutes") or freq_to_minutes(entry["freq"]))
    now = pendulum.now()
    last = state.get(key)
    if last:
        try:
            last_dt = pendulum.parse(last)
            if (now - last_dt).total_minutes() < interval:
                logger.info(f"Skip {key} por intervalo")
                return {"status": "skipped_interval", "ticker": entry["ticker"], "freq": entry["freq"]}
        except Exception:
            pass
    parquet_path = Path(entry.get("output") or f"data/market_data_{entry['ticker'].lower()}_{entry['freq'].lower()}.parquet")
    existing_rows = 0
    if parquet_path.exists():
        try:
            existing_rows = pl.read_parquet(parquet_path).height
        except Exception:
            existing_rows = 0
    pipe = build_market_etl_pipeline(
        ticker=entry["ticker"],
        frequency=entry["freq"],
        output_path=entry.get("output"),
        limit=int(entry.get("limit") or 1000),
        start=entry.get("start"),
        end=entry.get("end"),
        atr_period=int(entry.get("atr_period") or 14),
        months=int(entry.get("months") or 6),
    )
    result = pipe.fit_transform(None)
    final_rows = result.height if hasattr(result, "height") else existing_rows
    delta = max(0, final_rows - existing_rows)
    state[key] = now.to_iso8601_string()
    save_state(state_path, state)
    status = "updated" if delta > 0 else "up_to_date"
    return {
        "status": status,
        "ticker": entry["ticker"],
        "freq": entry["freq"],
        "rows_added": delta,
        "total_rows": final_rows,
    }


def run_signal(entry: dict) -> None:
    logger = logging.getLogger("etl_signals.signal")
    alerts_cfg = DATA_DIR / "alerts_config.json"
    alerts_state = DATA_DIR / "alerts_state.json"
    run_signal_check(entry["ticker"], entry["freq"], alerts_cfg, alerts_state, logger)


def notify_status(entry: dict, ti=None) -> None:
    logger = logging.getLogger("etl_signals.notify")
    res = ti.xcom_pull(
        task_ids=f"etl_{entry['ticker'].lower()}_{entry['freq']}",
        key="return_value",
    )
    if not res:
        logger.info("Sin retorno de ETL; no se notifica")
        return
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("ALERT_CHAT_ID", "")
    text = (
        f"ETL {res.get('ticker')} {res.get('freq')} "
        f"status={res.get('status')} "
        f"rows_added={res.get('rows_added')} "
        f"total={res.get('total_rows')}"
    )
    logger.info(text)
    if not token or not chat_id:
        logger.warning("Sin token o chat_id; no se envía notificación")
        return
    rc = subprocess_run(token, chat_id, text)
    if rc != 0:
        logger.warning("Fallo al enviar notificación a Telegram; rc=%s", rc)
    else:
        logger.info("Notificación enviada a Telegram")


def subprocess_run(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        completed = subprocess.run(
            ["curl", "-s", "-X", "POST", url, "-d", f"chat_id={chat_id}", "-d", f"text={text}"],
            check=False,
        )
        return completed.returncode
    except Exception:
        return 1


tz = pendulum.local_timezone()

with DAG(
    dag_id="etl_signals_quarter_hour",
    schedule="*/15 * * * *",
    start_date=pendulum.datetime(2025, 12, 6, 8, 0, 0, tz=tz),
    catchup=False,
    max_active_runs=1,
    concurrency=3,
    default_args={"retries": 1, "retry_delay": pendulum.duration(minutes=5)},
) as dag:
    entries = load_entries()
    for entry in entries:
        etl_task = PythonOperator(
            task_id=f"etl_{entry['ticker'].lower()}_{entry['freq']}",
            python_callable=run_etl,
            op_kwargs={"entry": entry},
        )
        signal_task = PythonOperator(
            task_id=f"signal_{entry['ticker'].lower()}_{entry['freq']}",
            python_callable=run_signal,
            op_kwargs={"entry": entry},
        )
        notify_task = PythonOperator(
            task_id=f"notify_{entry['ticker'].lower()}_{entry['freq']}",
            python_callable=notify_status,
            op_kwargs={"entry": entry},
        )
        etl_task >> [signal_task, notify_task]
