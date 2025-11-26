# AIVI Cripto Toolkit

Repositorio con dos dominios:
- Finanzas personales: motor de wallets y escenarios en Python/Polars, API FastAPI y dashboard Next.js.
- Trading/cripto: pipeline de datos y backtests de Binance, más estrategias modulares para experimentos.

## Mapa rápido
- `main.py`: núcleo de Wallet/ScenarioService (flujos recurrentes, reportes, comparación de escenarios).
- `api/`: FastAPI que expone wallets, escenarios, alertas y CRUD de eventos.
- `dashboard/`: app Next.js que consume el API (ver `.env.example` dentro del dashboard).
- `binance/`: pipeline completo ETL → features → research → Lean → evaluación (detalles en `binance/README.md`).
- `trading/`: estrategias polars reutilizables y notebook de exploración (ver `trading/README.md`).
- `utils/`: utilidades (logging, helpers de estrategia).
- `wallets.json`: registro de wallets; los `events*.parquet` se guardan junto al repo.

## Requisitos rápidos
- Python 3.11+ para el núcleo, API y trading. Instala todo con `pip install -r requirements.txt` (incluye Polars, FastAPI/Uvicorn, scikit-learn y dependencias del pipeline de Binance).
- Dashboard: Node 18+; usa `pnpm install` (o npm) en `dashboard/`.

## Wallet y escenarios (core)
- `CashFlowSpec` describe eventos (único, semanal, mensual) y se convierte en `CashFlow`.
- `EventRepository` guarda/lee `events.parquet`; `ScenarioService` aplica `FlowDelta` para generar variantes.
- `Wallet` calcula reportes y saldos a partir de `cash_flows`.

### Crear servicio por defecto
```python
from pathlib import Path
from main import build_default_service

service = build_default_service(path=Path("events.parquet"))
```
Genera eventos de ejemplo y escenarios `baseline` y `raise_plan` si el archivo no existe.

### Operaciones clave
- Alta de flujos: `add_one_time_*`, `add_weekly_*`, `add_monthly_*`.
- Reportes: `events_report(start, end)` y `summary_report(start, end, freq)`.
- Métricas puntuales: `expected_balance(as_of)`.
- Comparación de escenarios: `ScenarioService.compare(base, variant, start_date, end_date, freq)` devuelve `ComparisonResult` con `events` y `summary` alineados.

## API FastAPI
- Arranque: `uvicorn api.main:app --reload`.
- Endpoints principales:
  - Wallets: `GET/POST/PUT/DELETE /wallets`.
  - Escenarios: `GET /scenarios`, `GET /scenarios/compare`, `GET /balance`, `GET /alerts`.
  - Eventos: `GET/POST/PUT/DELETE /events`, más `GET /health`.

## Dashboard Next.js
- Define `NEXT_PUBLIC_WALLET_API` en `.env.local`.
- En `dashboard`: `pnpm install && pnpm dev` y abre `http://localhost:3000`.

## Trading y cripto
- El pipeline de datos, features y backtests está documentado en `binance/README.md`.
- Las piezas ligeras de estrategia y notebooks rápidos viven en `trading/README.md`.

## Datos y persistencia
- `wallets.json` lista wallets disponibles; cada una apunta a su `events_*.parquet`.
- Archivos de eventos/parquets se crean en el directorio raíz; `binance/data/` y `binance/mlruns/` guardan artefactos de trading y deben ignorarse en git.
