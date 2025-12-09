# ETL de mercado (ticker, frecuencia)

## Requisitos
- Python 3.11+
- Dependencias del proyecto instaladas (`pip install -r requirements.txt` aporta `polars`, `httpx`, `scikit-learn`, etc.).

## ETL CLI
- Comando base:
  ```bash
  python -m data.etl.cli --ticker BTCUSDT --freq 1h \
    [--start 2024-01-01 --end 2024-02-01] \
    [--limit 1000] [--atr-period 14] [--months 6] \
    [--output data/custom_btcusdt_4h.parquet]
  ```
- Parquet destino por defecto: `data/market_data_{ticker}_{freq}.parquet`.
- `--months` controla la ventana reciente del `market_df`; `--atr-period` ajusta el ATR; `--limit` es el tamaño de página de Binance.

## Frecuencias soportadas
`1m, 5m, 15m, 30m, 45m (se aproxima a 1h en Binance), 1h, 4h, 6h, 12h, 1d, 1w, 1month`

## Rango automático
- Si no pasas `--start` ni `--end`, el extractor:
  - Busca `data/market_data_{ticker}_{freq}.parquet`.
  - Toma el último `open_time` como `start`.
  - Usa la fecha de hoy como `end`.
  - Si no hay parquet, usa un lookback de 90 días.

## Scheduler local (sin Airflow)
- Configura entradas en `data/etl_schedule.json` (o un `.cfg/.ini` compatible): campos `ticker`, `freq`, `atr_period`, `months`, `interval_minutes`, `enabled`, etc.
- Una pasada: `python data/run_schedule.py --config data/etl_schedule.json --once`
- Loop alineado a cada :00/:15/:30/:45: `python data/run_schedule.py --config data/etl_schedule.json --loop`
- El estado de última ejecución queda en `data/etl_schedule_state.json` y se evita la concurrencia con `data/etl_schedule.lock`.
- Cada corrida dispara `data.alerts_runner.run_signal_check` al terminar el ETL.

## Alertas de señal
- Configuración en `data/alerts_config.json` (ejemplo incluido); estado en `data/alerts_state.json`.
- Requiere `TELEGRAM_BOT_TOKEN` en el entorno y `chat_id` por configuración.
- Reutiliza las etapas de `trading/strategies` y respeta `throttle_seconds` para no spamear.

## Script helper
- Ejecutar el ETL de BTCUSDT 1h: `bash data/run_btcusdt_1h.sh`
- Si el archivo ya está al día, verás en logs: `Sin nuevas velas; ticker=... freq=... ya estaba actualizado`

## Flujo interno
1. `ExtractionStage`: descarga klines de Binance REST para el rango.
2. `MarketFrameStage`: arma el `market_df` listo para estrategias.
3. `ParquetUpsertStage`: hace upsert y ordena por `open_time`.

Logs detallan inicio, rango usado, filas nuevas y total en el parquet.
