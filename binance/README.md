# Binance Pipeline

Directorio `binance/` contiene el flujo completo propuesto en los sprints:

1. **ETL** (`src/etl/etl.py`)
   - `python src/etl/etl.py --symbol BTCUSDT --mode history --start 2020-01 --end 2020-03`
   - `python src/etl/etl.py --symbol BTCUSDT --mode incremental --lookback 36h`
2. **Features** (`src/features/build_features.py`):
   - `python src/features/build_features.py BTCUSDT`
3. **Research** (`src/research/*.ipynb`, DuckDB helpers).
4. **LEAN** (`src/lean/Algorithm.py`, `run_backtest.sh`).
5. **Evaluación** (`src/eval/*.py`, MLflow + reportes).

`data/` y `mlruns/` almacenan artefactos (agregue a `.gitignore`).
`env/.env.example` documenta variables necesarias (Binance keys, MLflow URI).
