# Plan: Hardening de Airflow local

## Objetivos
- Limpiar y excluir logs de git.
- Asegurar manejo de secrets (.env, fernet_key).
- Fijar puerto del webserver y documentar override.
- Robustecer scripts de arranque/paro (PIDs).
- Desactivar DAGs de ejemplo.
- Usar TZ local (no UTC).
- Mantener SQLite para dev.

## Pasos
1) Gitignore y limpieza de logs
- Añadir exclusiones: `airflow_home/logs/`, `airflow_home/airflow-scheduler.*`,
  `airflow_home/airflow-webserver.pid`, `actions/.pids/`.
- Si hay logs ya versionados, eliminarlos del repo.
- Opcional: mover `base_log_folder` fuera de git en `airflow.cfg`.

2) Secrets y fernet_key
- `.env` en la raíz con `TELEGRAM_BOT_TOKEN`, `ALERT_CHAT_ID` (ya se carga
  desde el DAG). Asegurar que `.env` está ignorado.
- Generar `fernet_key` y poner en `core.fernet_key` en `airflow.cfg`.
- Usar Variables/Connections en Airflow para credenciales sensibles si aplica.

3) Puerto del webserver
- Default 8084; override con `AIRFLOW_WEBSERVER_PORT`.
- Documentar puerto en `airflow_home/README.md`.

4) Scripts start/stop y PIDs
- `start_airflow.sh`: validar puerto libre (lsof), cargar `.env`, exportar
  `AIRFLOW_HOME`/`DAGS_FOLDER`, guardar PIDs.
- `stop_airflow.sh`: limpiar pidfiles, SIGTERM/SIGKILL, `pkill` y matar puertos
  8084/8793 como fallback.

5) Desactivar DAGs de ejemplo
- `load_examples = False` en `airflow.cfg`.

6) Zona horaria local
- `default_timezone = America/Mexico_City` en `airflow.cfg`.

7) SQLite
- Mantener `sqlite:///.../airflow.db` para dev. Respaldar si se recrea
  `AIRFLOW_HOME`. Documentar que es solo para local.

## Verificación
- `actions/start_airflow.sh` arranca sin conflictos de puerto y crea PID files.
- `airflow cfg get-value core load_examples` => False.
- `airflow cfg get-value core default_timezone` => America/Mexico_City.
- `lsof -i :8084` muestra webserver; `lsof -i :8793` solo cuando corre scheduler.
- `git status` sin logs ni pidfiles nuevos.
