# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: core wallet/cash-flow engine (scenarios, reports, parquet-backed event repo).
- `api/`: FastAPI surface for wallets, comparisons, alerts/optimization.
- `data/`: market-data ETL + alert runner; parquet outputs under `data/market_data_{ticker}_{freq}_{datasource}.parquet`; scheduler state in `data/etl_schedule_state.json`.
- `data/etl/tasks/`: modular Airflow task implementations (extraction, processing, persistence, validation, signals, notifications).
- `dashboard/`: Next.js app for the UI; see `dashboard/package.json` scripts.
- `trading/`: strategy registry and transformations reused by ETL/alerts.
- `actions/` & `airflow_home/`: local Airflow bootstrap scripts (`actions/start_airflow.sh`, `actions/stop_airflow.sh`); DAG principal en `airflow_home/dags/etl_signals_refactored.py`.
- `utils/`: logging/performance helpers (MetaEngine); tests live in `tests/`.

## Setup, Build, and Development
- Python 3.11+: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
- API: `uvicorn api.main:app --reload --reload-dir api` (run from repo root).
- ETL one-off: `python -m data.etl.cli --ticker BTCUSDT --freq 1h --start 2024-01-01 --end 2024-02-01`; scheduler loop: `python data/run_schedule.py --config data/etl_schedule.json --loop`.
- Airflow (local): `bash actions/start_airflow.sh` / `bash actions/stop_airflow.sh`; webserver port via `AIRFLOW_WEBSERVER_PORT` (default 8084).
- Dashboard: `cd dashboard && npm install && npm run dev` (Next.js 15).

## Airflow ETL Patterns

### DAG Structure
- **DAG principal**: `airflow_home/dags/etl_signals_refactored.py`
- **Pattern**: Loop-based task generation (avoid `.expand()` dynamic mapping)
- **Task organization**: Modular tasks in `data/etl/tasks/` (extraction, processing, persistence, validation, signals, notifications)

### Dataset Pattern (File-based Data Passing)
- Fetch tasks write DataFrames to parquet cache files
- Transform/persist tasks read from cache files
- Only metadata (dict with cache_path, rows, ticker, freq) passes through XCom
- Avoids XCom serialization errors with Polars DataFrames

### Ticker Format Conventions
- **yfinance datasource**: Use hyphenated format (BTC-USD, ETH-USD)
- **Binance datasource**: Use concatenated format (BTCUSDT, ETHUSDT)
- Configure in `data/etl_schedule.json` with explicit `"datasource": "yfinance"` or `"binance"`

## Coding Style & Naming Conventions
- Python: 4-space indent, type hints enforced at runtime (`typeguard` via `MetaEngine`); keep docstrings describing DataFrame schemas when possible. Use `utils.logging_utils.setup_logger` for consistent formatting and file creation.
- Data files: keep parquet names `market_data_{ticker}_{freq}_{datasource}.parquet`; scenario/event ids in snake_case (e.g., `weekly_salary`, `raise_plan`).
- JS/TS (dashboard): follow ESLint/TS config in `dashboard`; prefer functional React components and keep paths relative to `dashboard/`.

## Testing Guidelines
- Backend: `python -m pytest tests -q`; current coverage focuses on logging/performance helpers—add tests near new modules under `tests/` mirroring package paths.
- Frontend lint: `cd dashboard && npm run lint` before pushing.

## Commit & Pull Request Guidelines
- Git history uses conventional prefixes (`feat: ...`, `chore: ...`); keep subjects short and present tense.
- PRs: describe intent and scope, link issue/task when available, list commands run (pytest, lint, ETL sample), and attach screenshots/GIFs for dashboard changes. Note any schema or data-location changes (e.g., new parquet names or DAGs).
