# Wallet Scenario Toolkit

Herramienta para describir flujos de efectivo recurrentes, guardarlos en
`events.parquet` y ejecutar comparaciones de escenarios usando Polars.

## Arquitectura

- `EventRepository` lee/escribe `events.parquet` con el esquema base
  definido en `EVENT_SCHEMA`.
- `CashFlowSpec` describe cada evento y se transforma en objetos
  `CashFlow` (único, semanal o mensual) que heredan de `CashFlow`.
- `ScenarioService` combina el repositorio con definiciones de escenarios
  (`Scenario` + `FlowDelta`) para materializar carteras, generar reportes
  y comparar variantes.
- `Wallet` contiene el saldo inicial, fecha de referencia y la lista de
  `CashFlow`. Puede usarse desde código directo o a través del servicio.

## Persistencia inicial

```python
from pathlib import Path
from main import build_default_service

service = build_default_service(
    path=Path("py4fi2nd/code/z_1/events.parquet")
)
```

`build_default_service` crea eventos de salario semanal y renta si el
archivo no existe y registra dos escenarios: `baseline` y `raise_plan`.
- Las wallets disponibles se guardan en `wallets.json`; cada entrada
  apunta a su propio archivo `events_*.parquet` para mantener los
  flujos separados.

## Acciones principales sobre la wallet

```python
from main import Wallet
import datetime as dt

wallet = Wallet(initial_balance=2500.0, reference_date=dt.date(2024, 1, 1))

wallet.add_one_time_income(
    name="Devolución impuestos",
    amount=1200.0,
    date=dt.date(2024, 3, 4),
)

wallet.add_one_time_expense(
    name="Seguro auto",
    amount=850.0,
    date=dt.date(2024, 2, 10),
)

wallet.add_weekly_income(
    name="Sueldo",
    amount=6000.0,
    first_date=dt.date(2024, 1, 5),
)

wallet.add_weekly_expense(
    name="Super",
    amount=1500.0,
    first_date=dt.date(2024, 1, 6),
)

wallet.add_monthly_income(
    name="Renta casa",
    amount=9000.0,
    first_date=dt.date(2024, 1, 10),
)

wallet.add_monthly_expense(
    name="Hipoteca",
    amount=7500.0,
    first_date=dt.date(2024, 1, 15),
)
```

- `add_one_time_income`/`add_one_time_expense` registran eventos
  puntuales positivos o negativos.
- `add_weekly_income`/`add_weekly_expense` generan series semanales con
  fecha inicial y opcional final.
- `add_monthly_income`/`add_monthly_expense` generan series mensuales en
  la fecha especificada.

## Métodos principales de análisis

### `events_report(start_date, end_date)`

Devuelve un `pl.DataFrame` con columnas `date`, `income`, `expenses` y
`concept` para cada evento que ocurra en el rango solicitado. La wallet
convierte gastos en positivos para facilitar totales.

```python
df_events = wallet.events_report(
    start_date=dt.date(2024, 1, 1),
    end_date=dt.date(2024, 2, 29),
)
```

### `summary_report(start_date, end_date, freq="daily")`

Agrupa los eventos por ventanas dinámicas (`daily`, `weekly`, `monthly`)
calculando ingreso, gasto, neto y balance acumulado. También concatena
los conceptos ocurridos en cada periodo.

```python
df_summary = wallet.summary_report(
    start_date=dt.date(2024, 1, 1),
    end_date=dt.date(2024, 3, 31),
    freq="weekly",
)
```

### `expected_balance(as_of)`

Calcula el saldo esperado en la fecha `as_of` usando el saldo inicial en
`reference_date` y todos los eventos entre ambas fechas.

```python
available = wallet.expected_balance(as_of=dt.date(2024, 4, 15))
```

### `ScenarioService.compare(base, variant, start_date, end_date, freq)`

Construye `Wallet` para cada escenario, ejecuta ambos reportes y regresa
un `ComparisonResult` con dos `pl.DataFrame`:

- `events`: columnas separadas para ingreso/gasto base y variante, más
  `income_delta` y `expenses_delta`.
- `summary`: columnas de ingreso/gasto/neto/balance para cada escenario
  y las columnas delta correspondientes.

```python
comparison = service.compare(
    base="baseline",
    variant="raise_plan",
    start_date=dt.date(2025, 11, 8),
    end_date=dt.date(2026, 1, 31),
    freq="weekly",
)

events_df = comparison.events
summary_df = comparison.summary
```

## Flujo típico

1. Crear o cargar `events.parquet` con `EventRepository` o la función
   `build_default_service`.
2. Definir escenarios adicionales agregando `FlowDelta` (subir monto,
   eliminar evento o reemplazarlo por otro `CashFlowSpec`).
3. Ejecutar acciones sobre la wallet o escenarios para preparar la
   simulación.
4. Llamar a `events_report`, `summary_report`, `expected_balance` o a
   `ScenarioService.compare` para obtener los análisis deseados.
5. Utilizar los DataFrames resultantes para tableros, notebooks o
   pipelines posteriores.

## API FastAPI

1. Instala dependencias del backend (por ejemplo con `pip install
   fastapi uvicorn polars` dentro del entorno del proyecto).
2. Desde `py4fi2nd/code/z_1` ejecuta `uvicorn api.main:app --reload`.
3. Usa `curl` o un cliente REST para probar salud y escenarios.

Endpoints principales:

- `GET /wallets`: lista las wallets registradas en `wallets.json`.
- `POST /wallets`: crea una nueva wallet (nombre, saldo inicial, fecha).
- `PUT /wallets/{id}` y `DELETE /wallets/{id}`: actualizan o eliminan
  registros.
- `GET /health`: estado del servicio.
- `GET /scenarios`: lista de escenarios disponibles (requiere
  `wallet_id`).
- `GET /scenarios/compare`: acepta `base`, `variant`, `start_date`,
  `end_date`, `freq`, `wallet_id` y regresa eventos + resumen alineados.
- `GET /alerts`: genera alertas (saldo negativo, gastos próximos,
  relación gasto/ingreso) para una wallet/escenario concreto.
- `GET /events`, `POST /events`, `PUT /events/{id}`, `DELETE /events/{id}`:
  CRUD completo sobre `CashFlowSpec` dentro de la wallet elegida.
- `GET /balance`: saldo esperado para un escenario y fecha de la wallet
  seleccionada.

## Dashboard Next.js

1. Copia `.env.example` (o crea `.env.local`) y define
   `NEXT_PUBLIC_WALLET_API`, apuntando al FastAPI local.
2. En `dashboard` ejecuta `pnpm install` (o `npm install` si usas npm).
3. Corre `pnpm dev` y abre `http://localhost:3000`.

Componentes clave:

- `useWalletDashboard` consulta escenarios, métricas, alertas y eventos
  del API y comparte controles (fechas, frecuencia, escenarios).
- `DashboardControls` permite cambiar escenario base/plan, rango y
  frecuencia, disparando refetches automáticos.
- `DashboardChart`, `DashboardStat`, `SecurityStatus`, `Notifications`
  muestran datos reales (`ComparisonResult`, alertas) sin `mock.json`.
- `EventsTable` expone agregar/editar/eliminar eventos vía los endpoints
  CRUD; tras cada acción se sincroniza el store y se refresca la vista.

Para ambientes productivos expone both servicios (FastAPI + Next.js) con
las variables de entorno adecuadas y asegúrate de persistir
`events.parquet` en un volumen compartido.
