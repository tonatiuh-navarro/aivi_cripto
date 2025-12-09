#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT/actions/.pids"

kill_pidfile() {
  local pid_file="$1"
  if [ ! -f "$pid_file" ]; then
    return
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -n "${pid:-}" ] && ps -p "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if ps -p "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi
  rm -f "$pid_file"
}

kill_pidfile "$PID_DIR/scheduler.pid"
kill_pidfile "$PID_DIR/webserver.pid"

# Fallback: mata procesos residuales si siguen vivos
pkill -f "airflow scheduler" >/dev/null 2>&1 || true
pkill -f "airflow webserver" >/dev/null 2>&1 || true

# Mata procesos escuchando en puertos comunes (webserver 8082, dag processor 8793)
for port in 8082 8793; do
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      kill $pids >/dev/null 2>&1 || true
      sleep 1
      kill -9 $pids >/dev/null 2>&1 || true
    fi
  fi
done
