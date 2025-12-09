# Binance Pipeline

Toolkit para descargar OHLCV 1m desde Binance Vision/REST, generar features y correr backtests (Lean/Polars). No hay una CLI empaquetada; importa las funciones o usa los scripts indicados abajo.

## Estructura
- `src/etl/etl.py`: funciones `run_history` (Vision) y `run_incremental` (REST) que escriben en `data/spot/<symbol>/ohlcv_1m/year=*/month=*/data.parquet` y registran `data/ingestion_log.parquet`.
- `src/features/`: `build_features.py` aplica features de `config/features.yaml` (EMA, RSI, ATR, Z-score) y guarda en `data/features/<feature>/<symbol>/data.parquet`.
- `src/eval/`: helpers ligeros para MLflow/HTML (`log_run`, `render_report`).
- `src/lean/`: ejemplo EMA crossover para Lean (`Algorithm.py`), utilidades de comisiones/riesgo y `run_backtest.sh`.
- `src/research/`: notebooks (`sanity_checks`, `report_template`) y consultas (`queries_duckdb.sql`).
- Estrategias: los stages y `strategy_utils` viven en `../trading/strategies` y `../utils/strategy_utils.py` (no existe `binance/strategies`).
- Artefactos: `data/`, `mlruns/` opcional; dependencias en `../requirements.txt`.

## Setup
1) `python -m venv .venv && source .venv/bin/activate`  
2) `pip install -r ../requirements.txt`  
3) Define `MLFLOW_TRACKING_URI` si vas a loggear en MLflow; no hay `env/.env.example` en esta carpeta.

## ETL 1m (uso desde Python)
Añade `binance` al `PYTHONPATH` y llama a las funciones exportadas:
```bash
PYTHONPATH="$(pwd)/binance" python - <<'PY'
from datetime import timedelta
from src.etl.etl import run_history, run_incremental, parse_month, run

run_history("BTCUSDT", parse_month("2020-01"), parse_month("2020-03"))
run_incremental("BTCUSDT", timedelta(hours=36))
run(symbol="ETHUSDT", mode="incremental", lookback="24h")
PY
```

## Features y backtests
- Generar features: `PYTHONPATH="$(pwd)/binance" python -m src.features.build_features BTCUSDT`
- Backtest Lean: `bash binance/src/lean/run_backtest.sh` (requiere CLI de Lean y credenciales configuradas).
- Logs/reportes: usa `src/eval/export_report.py` para loggear en MLflow y generar HTMLs rápidos.
