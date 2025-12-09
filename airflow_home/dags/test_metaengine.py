from __future__ import annotations

import sys
from pathlib import Path

import pendulum
import polars as pl
from airflow import DAG
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv
from airflow.configuration import conf

_resolved = Path(__file__).resolve()
_repo_root = _resolved.parents[1]
if str(_repo_root) not in sys.path:
    sys.path.append(str(_repo_root))
# también añadimos un nivel arriba por si el dags_folder está dentro de airflow_home
if str(_repo_root.parent) not in sys.path:
    sys.path.append(str(_repo_root.parent))
load_dotenv(_repo_root / ".env")

from utils.logging_utils import build_task_log_path  # noqa: E402
from utils.performance_utils import MetaEngine  # noqa: E402


class DummyStage(metaclass=MetaEngine, log_level="INFO"):
    log_file: str | None = None

    def transform(self, frame: pl.DataFrame) -> pl.DataFrame:
        # simple operation to trigger logging
        return frame.with_columns(pl.col("value") * 2)


def run_dummy(ti=None):
    df = pl.DataFrame({"value": [1, 2, 3]})
    if ti:
        exec_str = ti.execution_date.isoformat().replace(":", "-").replace("+", "-")
        filename = f"attempt={exec_str}_{ti.try_number}.log"
        base_dir = Path(conf.get("logging", "base_log_folder", fallback=_repo_root / "airflow_home" / "logs"))
        log_path = build_task_log_path(
            base_dir=base_dir,
            dag_id=ti.dag_id,
            run_id=ti.run_id,
            task_id=ti.task_id,
            filename=filename,
        )
        stage = DummyStage()
        stage.log_file = str(log_path)
    else:
        stage = DummyStage()
    stage.transform(df)
    return None


tz = pendulum.local_timezone()

with DAG(
    dag_id="test_metaengine",
    schedule="@once",
    start_date=pendulum.datetime(2025, 12, 6, 8, 0, 0, tz=tz),
    catchup=False,
) as dag:
    PythonOperator(
        task_id="dummy_task",
        python_callable=run_dummy,
    )
