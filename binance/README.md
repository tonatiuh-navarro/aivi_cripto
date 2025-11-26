# Binance Pipeline

Pipeline para descargar OHLCV 1m de Binance, generar features y correr backtests (Lean/Polars) con registro de métricas.

## Estructura
- `src/etl/etl.py`: historia/incremental desde Binance Vision y REST; escribe Parquet particionado en `data/spot/<symbol>/ohlcv_1m/year=*/month=*/data.parquet` y guarda log en `data/ingestion_log.parquet`.
- `src/features/`: `build_features.py` aplica features definidas en `config/features.yaml` (EMA, RSI, ATR, Z-score) y escribe en `data/features/<feature>/<symbol>/data.parquet`.
- `src/eval/`: métricas (`cumulative_return`), plots y helpers de logging/reportes en MLflow (`export_report.py`).
- `src/lean/`: ejemplo de estrategia EMA crossover para Lean (`Algorithm.py`), helpers de comisiones/riesgo y `run_backtest.sh`.
- `src/research/`: notebooks (`sanity_checks`, `report_template`) y `queries_duckdb.sql` para exploración.
- `strategies/`: etapas modulares de entrada/target/stop (MASignal, ATR) y `strategy_utils.py` para simular trades en Polars.
- Artefactos: `data/`, `mlruns/`, notebook de exploración en `../trading/exploration.ipynb`. Configuración: `env/.env.example`, `Makefile`. Dependencias en `../requirements.txt`.

## Setup
1) `python -m venv .venv && source .venv/bin/activate`  
2) `pip install -r ../requirements.txt`  
3) Copia `env/.env.example` a `env/.env` y define `BINANCE_API_KEY`, `BINANCE_SECRET_KEY`, `MLFLOW_TRACKING_URI`.  
4) Mantén `data/` y `mlruns/` fuera de git (ya previsto en `.gitignore`).

## Flujo sugerido
1. **ETL**  
   - Historia: `python src/etl/etl.py --symbol BTCUSDT --mode history --start 2020-01 --end 2020-03`  
   - Incremental: `python src/etl/etl.py --symbol BTCUSDT --mode incremental --lookback 36h`
2. **Features**  
   - `python src/features/build_features.py BTCUSDT` (ajusta parámetros en `config/features.yaml`).
3. **Research**  
   - Explora con `src/research/*.ipynb` o DuckDB (`queries_duckdb.sql`) sobre los Parquet ya generados.
4. **Backtest Lean**  
   - `bash src/lean/run_backtest.sh` (requiere CLI de Lean y credenciales configuradas).
5. **Evaluación**  
   - Usa `src/eval/export_report.py` para loggear `params/metrics/artifacts` en MLflow y renderizar un HTML rápido con `render_report`.

## Notas
- `_ingestion_log.parquet` rastrea cada descarga (mes, filas, hash, status) para evitar duplicados y auditar ingestas.
- `strategy_utils.py` monta un DataFrame con ATR y ejecuta las etapas de `strategies/` para pruebas rápidas sin Lean.
- Los features disponibles son mínimos; agrega nuevos módulos y referencia sus nombres en `config/features.yaml` para que `build_features.py` los importe dinámicamente.
