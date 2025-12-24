Airflow local setup
===================

Ubicación
- AIRFLOW_HOME vive en `airflow_home` dentro del repo.
- Los DAGs están en `airflow_home/dags`; el DAG principal (`etl_signals_refactored`) lee `data/etl_schedule.json`.
- Patrón de arquitectura: Loop-based task generation con Dataset pattern (file-based data passing).

Variables requeridas
- Define en `.env` (en la raíz del repo):
  - TELEGRAM_BOT_TOKEN=8543539764:AAEww9g0xAhbuIg7pa9bt0RY6v1XC3QIp5w
  - ALERT_CHAT_ID=6233147719
- `actions/start_airflow.sh` hace `source .env`. Si corres `airflow ...` a mano, exporta estas variables en tu shell:
  - AIRFLOW_HOME=$(pwd)/airflow_home
  - AIRFLOW__CORE__DAGS_FOLDER=$AIRFLOW_HOME/dags
  - AIRFLOW_WEBSERVER_PORT=8084 (puerto por defecto; cámbialo si hay conflicto)

Inicialización
1) `airflow db init`
2) Crear usuario admin:
   `airflow users create --role Admin --username admin --password admin --firstname a --lastname a --email a@a.com`

Ejecución
- Scripts recomendados:
  - Arrancar: `bash ./actions/start_airflow.sh`
  - Detener: `bash ./actions/stop_airflow.sh`
- Manual:
  - Scheduler: `airflow scheduler`
  - Webserver: `airflow webserver -p ${AIRFLOW_WEBSERVER_PORT:-8084}`
- Próxima ejecución: `airflow dags next-execution etl_signals_refactored`
- Logs de task: `airflow tasks logs etl_signals_refactored BTC_USD_1h.fetch_yfinance_data <run_id>`

Configuración del DAG
- Entradas de ETL en `data/etl_schedule.json` (`enabled`, `start/end`, `interval_minutes`, `output`, etc.).
- El intervalo real se controla con `data/etl_schedule_state.json` para saltar corridas muy seguidas.
- Alertas de señales leen `data/alerts_config.json` y persisten en `data/alerts_state.json`.
- El DAG añade la raíz del repo al `PYTHONPATH` para importar `data/` y `utils/`.

Arquitectura del DAG
====================

Estructura
----------
El DAG `etl_signals_refactored` usa un patrón de loops tradicionales en lugar de dynamic task mapping:

```python
for entry in etl_configs:
    @task_group(group_id=f"{ticker}_{freq}")
    def process_ticker(config: dict):
        validated = validate_config(config)
        raw_data = fetch_yfinance_data(validated) if yfinance else fetch_binance_data(validated)
        processed = transform_data(raw_data, validated)
        persisted = persist_data(processed, validated)
        quality = validate_data_quality(persisted)
        signals = analyze_signals(validated, quality)
        send_notification(persisted, signals, validated)
```

Dataset Pattern
---------------
- **Fetch tasks** escriben DataFrames a cache files (`data/market_data_{ticker}_{freq}_{datasource}.parquet`)
- **Transform tasks** leen del cache, procesan, y escriben de vuelta
- **XCom** solo pasa metadata: `{"cache_path": str, "rows": int, "ticker": str, "freq": str}`
- Evita errores de serialización con Polars DataFrames

Rate Limiting
-------------
- Built-in en fetch tasks: `should_run_etl(ticker, freq, interval_minutes)`
- Si no ha pasado el intervalo, task se salta con `AirflowSkipException`
- Estado en `data/etl_schedule_state.json`

Notas
- TZ local configurada en `airflow.cfg`: `default_timezone = America/Mexico_City`.
- DAGs de ejemplo desactivados (`load_examples = False`).
- ETL usa Parquets en `data/` y `data/etl_schedule_state.json`.
- Alertas usan `data/alerts_config.json` y `data/alerts_state.json`.
