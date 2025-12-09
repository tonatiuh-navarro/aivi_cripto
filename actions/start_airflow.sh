#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export AIRFLOW_HOME="$ROOT/airflow_home"
export AIRFLOW__CORE__DAGS_FOLDER="$AIRFLOW_HOME/dags"

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT/.env"
  set +a
fi

mkdir -p "$ROOT/actions/.pids"

PORT="${AIRFLOW_WEBSERVER_PORT:-8084}"

if command -v lsof >/dev/null 2>&1; then
  if lsof -i :"$PORT" >/dev/null 2>&1; then
    echo "Puerto $PORT en uso; define AIRFLOW_WEBSERVER_PORT o libera el puerto." >&2
    exit 1
  fi
fi

airflow scheduler >/dev/null 2>&1 &
echo $! > "$ROOT/actions/.pids/scheduler.pid"

airflow webserver -p "$PORT" >/dev/null 2>&1 &
echo $! > "$ROOT/actions/.pids/webserver.pid"
