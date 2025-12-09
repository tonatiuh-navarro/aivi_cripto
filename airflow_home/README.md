Airflow local setup
===================

Ubicación
- AIRFLOW_HOME vive en `airflow_home` dentro del repo.
- Los DAGs están en `airflow_home/dags`; el DAG principal (`etl_signals_quarter_hour`) lee `data/etl_schedule.json`.

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
- Próxima ejecución: `airflow dags next-execution etl_signals_quarter_hour`
- Logs de task: `airflow tasks logs etl_signals_quarter_hour notify_btcusdt_1h <run_id>`

Configuración del DAG
- Entradas de ETL en `data/etl_schedule.json` (`enabled`, `start/end`, `interval_minutes`, `output`, etc.).
- El intervalo real se controla con `data/etl_schedule_state.json` para saltar corridas muy seguidas.
- Alertas de señales leen `data/alerts_config.json` y persisten en `data/alerts_state.json`.
- El DAG añade la raíz del repo al `PYTHONPATH` para importar `data/` y `utils/`.

Notas
- TZ local configurada en `airflow.cfg`: `default_timezone = America/Mexico_City`.
- DAGs de ejemplo desactivados (`load_examples = False`).
- ETL usa Parquets en `data/` y `data/etl_schedule_state.json`.
- Alertas usan `data/alerts_config.json` y `data/alerts_state.json`.
