from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


default_args = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=1),
}


def diagnose(**_):
    import os
    import socket
    import httpx

    results = {}
    try:
        results["getaddrinfo"] = socket.getaddrinfo("api.binance.com", 443)
    except Exception as exc:  # pragma: no cover
        results["getaddrinfo_error"] = repr(exc)
    try:
        resp = httpx.get("https://api.binance.com/api/v3/time", timeout=10)
        results["httpx_status"] = resp.status_code
        results["httpx_body"] = resp.text[:120]
    except Exception as exc:  # pragma: no cover
        results["httpx_error"] = repr(exc)
    results["env_proxy"] = {
        k: v for k, v in os.environ.items() if "proxy" in k.lower()
    }
    print(results)
    return results


with DAG(
    dag_id="diagnose_dns",
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False,
    default_args=default_args,
    tags=["diagnostic"],
) as dag:
    PythonOperator(
        task_id="check_dns_httpx",
        python_callable=diagnose,
    )
