# Wallet Dashboard Integration Plan

**Global constraints**

- Scripts generados o modificados no deben incluir comentarios, prints,
  emojis ni líneas mayores a 80 caracteres.

## 1. FastAPI backend for wallet service

- Al terminar cada subpunto ejecutar pruebas manuales o unitarias según corresponda.

1.1 Structure  
- Create `py4fi2nd/code/z_1/api` package: `__init__.py`, `main.py`, `schemas.py`,
  `dependencies.py`.  
- Reuse existing wallet module via imports; avoid circular refs.

1.2 Schemas  
- Use Pydantic models matching `CashFlowSpec`, `FlowDelta`, `Scenario`, and
  outputs for events/summary (lists of dicts).  
- Include enums for `frequency`, `scenario_name`, `freq` (daily/weekly/monthly).

1.3 FastAPI app setup  
- Instantiate `FastAPI(title="Wallet API")`.  
- Dependency to load `ScenarioService` once per process via
  `build_default_service(Path("events.parquet"))`.  
- Include CORS middleware (allow localhost dev ports).

1.4 Endpoints  
- `GET /health`: returns status/version.  
- `GET /scenarios`: list available scenario names + metadata.  
- `GET /scenarios/compare`: query params
  `base`, `variant`, `start_date`, `end_date`, `freq`; returns `ComparisonResult`
  serialized (events + summary).  
- `GET /balance`: param `as_of`; returns expected balance.  
- `GET /events`: returns persisted `CashFlowSpec` rows.  
- `POST /events`: body `CashFlowSpec`; writes via repo and returns updated list.  
- `PUT /events/{event_id}`: replace event.  
- `DELETE /events/{event_id}`: remove event.  
- `GET /alerts`: derive alerts (see section 5) and return array with severity.

1.5 Serialization rules  
- Convert `pl.DataFrame` to Python lists via `to_dicts()`.  
- Ensure `date` fields are ISO strings; use custom encoder or `datetime.date`.

1.6 CLI + docs  
- Provide `uvicorn api.main:app --reload` instructions in README.  
- Enable OpenAPI docs; verify required query params described.

## 2. Replace mock JSON with typed data hooks

- Tras finalizar cada subpunto verificar en el dashboard que los datos remotos se consumen correctamente.

2.1 Remove `mock.json` usage  
- Delete imports from `app/page.tsx` and components.  
- Introduce `lib/wallet-client.ts` exporting fetchers (using `fetch` vs Next
  route handlers). Functions: `fetchDashboardStats`, `fetchSummary`,
  `fetchEvents`, `fetchAlerts`, `fetchScenarios`.

2.2 Types  
- Mirror FastAPI responses in `types/wallet.ts` (CardStat, SummaryPoint,
  WalletEvent, Alert, ScenarioMeta, ComparisonPayload).  
- Re-export for UI components.

2.3 Hooks / stores  
- Create `hooks/useWalletData.ts` using SWR or Zustand:
  - Inputs: `baseScenario`, `variantScenario`, `startDate`, `endDate`, `freq`.  
  - Returns `stats`, `chart`, `alerts`, `events`, `loading`, `error`.  
- Provide memoized selectors for `DashboardStat`, chart data.

2.4 Component wiring  
- `DashboardStat` list consumes `stats` derived from API.  
- `DashboardChart` receives `chartData` (dates, income, expenses, balance).  
- Alert widgets read typed `alerts` array.  
- Remove all typed `MockData` references and update props accordingly.

## 3. Scenario/date/frequency controls

- Después de completar cada parte probar que los cambios de estado disparan el refetch esperado.

3.1 Control panel design  
- Add new component (e.g., `components/dashboard/controls.tsx`).  
- Use Radix Select for scenarios, `react-day-picker` or date range picker for
  start/end, and Tabs or Select for frequency.  
- Provide compare toggle (baseline vs variant) and apply button.

3.2 State wiring  
- Controls update a global store (Zustand) or lift state to page-level.  
- On change, trigger refetch in `useWalletData`.  
- Show loading indicators/spinners on cards and chart during fetch.

3.3 Defaults  
- Initialize with scenarios returned by `/scenarios`.  
- Fall back to `baseline` and `raise_plan` if API not ready.

## 4. Wallet event list with dialogs

- Testear cada acción (crear, editar, eliminar) inmediatamente después de implementarla.

4.1 Component refactor  
- Replace `RebelsRanking` usage with new `components/dashboard/events-table`.  
- Display columns: concept, amount, frequency, start date, end date, tags for
  scenario overrides.  
- Provide action buttons per row (edit/delete) using Radix Dialog/AlertDialog.

4.2 CRUD workflow  
- `Add` button opens form (Radix Dialog) with inputs matching backend schema.  
- On submit, call FastAPI `POST /events`; refresh store afterward.  
- Edit uses `PUT /events/{id}`; pre-fill form.  
- Delete triggers confirm -> `DELETE`.  
- Show success/error toasts via `sonner`.

4.3 Validation  
- Use `react-hook-form` + `zod` for schema validation; sync types with backend.

## 5. Cash-health alerts + notifications

- Validar que cada alerta se calcule y muestre correctamente antes de continuar con la siguiente.

5.1 Backend alert logic  
- Within FastAPI `GET /alerts`, compute:
  - `projected_low_balance`: using summary net cumulative; emit warning when
    future balance < threshold (config).  
  - `upcoming_rent`: detect `monthly` expenses within next N days.  
  - `high_expense_ratio`: compare expense/income over window.  
- Each alert returns `id`, `title`, `message`, `severity`, `date`.

5.2 Frontend widget  
- Rename `SecurityStatus` to `CashHealthStatus`.  
- Accept list of alerts; map severity to variant colors.  
- Provide tooltip/details linking to events.

5.3 Notifications reuse  
- Feed alert array + near-term events into notifications panel to remind about
  upcoming payments.  
- Allow dismissing alerts locally while keeping backend list intact for future
  fetches.

## 6. Integration checklist

1. Implement FastAPI service, test endpoints with curl/Postman.  
2. Add `.env` or config for backend base URL used by Next.  
3. Migrate frontend to new hooks and controls; ensure SSR compatibility.  
4. QA flows: scenario switching, CRUD operations, alert rendering.  
5. Update README with API + dashboard usage instructions.  
6. Consider Docker Compose for running backend + Next simultaneously.
