# Implementation Guardrails

1. Estilo: no comments, no prints, no long lines (>80), sin emojis, priorizar
   eficiencia y mínimo código.
2. Documentación: usar siempre el bloque siguiente cuando se requiera
   escribir docstrings NumPy-style. No agregar docstrings a `__init__`.
   ```yaml

   Write a docstring for the selected Python function or method using
   NumPy documentation style.

   The docstring **must include** the following sections:
   1. **Workflow**: Step-by-step explanation of the internal logic or
      operations.
   2. **Parameters**: With type hints and descriptions.
   3. **Returns**: If applicable.
   4. **Example**: A usage example if appropriate.

   Follow this format:

   \"\"\"
   {Short summary of what the function does.}

   Workflow
   --------
   1. {Step one of internal logic}
   2. {Step two...}
   ...

   Parameters
   ----------
   param1 : type
       Description of param1.
   param2 : type
       Description of param2.

   Returns
   -------
   type
       Description of the return value.

   Examples
   --------
   >>> example_function(args)
   \"\"\"

   \"\"\"
   Rules & Conventions
   1. Always use the short library aliases:
   - pd.DataFrame (never pandas.DataFrame)
   - pl.DataFrame (never polars.DataFrame)
   2. For every parameter whose type is pl.DataFrame, add a “Schema”
      block that lists all required columns and dtypes. Follow the format
      shown in etl_rto_metrics.py.

   \"\"\"
   Schema example

           de_data: pl.DataFrame
               Frame containing the DE data.
               Schema:
                   |-- model_data_scoring_datetime: datetime
                   |-- model_data_scoring_result: str
                   |-- model_data_scoring_id: int
                   |-- model_data_score: float
                   |-- voters_id: str
                   |-- model_data_max_remaining_value: float
                   |-- customer_exist_in_HT: str
                   |-- registration_date: date
                   |-- model_data_model_time: float
                   |-- user_agreement_request_id: str

   \"\"\"

   3. Determine required columns/dtypes revisando el código circundante.
   4. Mantener todas las líneas ≤ 80 caracteres.
   ```

3. Argumentos: al invocar funciones o crear instancias, pasar cada
   argumento como `param=param`.

# Scenario Comparison Plan

1. Scenario descriptor  
   - Ahora: `Wallet` solo guarda `CashFlow` creados manualmente en
     `cash_flows` (`py4fi2nd/code/z_1/main.py:171`).  
   - Cambio: definir dataclasses inmutables para escenarios y overrides
     con ids y metadatos, lo que permite describir escenarios sin mutar
     el baseline.
   ```python
   @dataclass(frozen=True)
   class Scenario:
       name: str
       parent: str | None = None
       deltas: list[FlowDelta] = field(default_factory=list)
   @dataclass(frozen=True)
   class FlowDelta:
       id: str
       amount_delta: float = 0.0
       remove: bool = False
       replacement: CashFlowSpec | None = None
   ```

2. Construcción de `Wallet` desde escenarios  
   - Ahora: los flujos se agregan con `add_*` y quedan ligados al script
     (`main.py:175-236`).  
   - Cambio: exponer un constructor alterno que reciba un `Scenario` y
     materialice `CashFlow` a partir de specs persistidas, permitiendo
     alternar escenarios con la misma base.
   ```python
   wallet = Wallet.from_scenario(
       initial_balance=5000.0,
       reference_date=hoy,
       scenario=baseline_scn,
       repo=event_repo,
   )
   ```

3. Loader con overrides  
   - Ahora: no existe clonación del baseline, cualquier ajuste implica
     editar código.  
   - Cambio: agregar `ScenarioLoader` que tome los eventos base, aplique
     deltas (sumas, remociones, reemplazos) y devuelva los `CashFlow`
     finales para esa corrida.
   ```python
   flows = ScenarioLoader(repo).materialize("raise_plan")
   wallet = Wallet(initial_balance=..., reference_date=..., cash_flows=flows)
   ```

4. Reportes multi escenario  
   - Ahora: cada reporte devuelve un solo DataFrame (`main.py:241-427`).  
   - Cambio: crear helpers que reciban `[Scenario]`, ejecuten
     `events_report` o `summary_report` por cada uno y devuelvan frames
     alineados por fecha para poder comparar.
   ```python
   comparison = ScenarioReporter(wallet_repo).events_report_many(
       ["baseline", "raise_plan"], inicio, fin
   )
   ```

5. Utilidades de deltas  
   - Ahora: cualquier comparación debe hacerse manualmente.  
   - Cambio: introducir módulos que calculen `income_delta`,
     `expenses_delta`, `net_delta` por fecha y por resumen, listos para
     graficar o mostrar en UI.
   ```python
   deltas = ScenarioDiff(comparison).per_date()
   ```

6. API `compare(a, b)`  
   - Ahora: no existe función explícita.  
   - Cambio: añadir `compare_scenarios(a, b, window)` que regrese un
     `ComparisonResult` con frames detallados y totales agregados.
   ```python
   result = ScenarioService(repo).compare("baseline", "raise_plan", inicio, fin)
   ```

7. Demo actualizada  
   - Ahora: el bloque `__main__` solo imprime un escenario  
     (`main.py:429-454`).  
   - Cambio: actualizar la demo para crear `baseline` desde parquet,
     derivar `raise_plan`, invocar `compare` y mostrar los datos clave.

# Event Persistence Plan

1. Esquema parquet  
   - Ahora: los eventos viven solo en memoria; se pierden al cerrar el
     script.  
   - Cambio: definir un esquema mínimo (`id`, `concept`, `amount`,
     `frequency`, `start_date`, `end_date`, `metadata`) almacenado en
     `events.parquet` para que sea la fuente de verdad.
   ```python
   EVENT_SCHEMA = {
       "id": pl.Utf8,
       "concept": pl.Utf8,
       "amount": pl.Float64,
       "frequency": pl.Utf8,
       "start_date": pl.Date,
       "end_date": pl.Date,
       "metadata": pl.Struct,
   }
   ```

2. Repositorio dedicado  
   - Ahora: `Wallet` maneja lógica y datos a la vez.  
   - Cambio: crear `EventRepository` que exponga `load_events()` con
     `pl.scan_parquet` y `save_events(df)` con `write_parquet`, aislando
     IO del resto del dominio.
   ```python
   repo = EventRepository(path)
   events = repo.load_events()
   repo.save_events(events)
   ```

3. Lectura al inicio  
   - Ahora: los flujos se hardcodean en `__main__`.  
   - Cambio: al iniciar, intentar leer el parquet; si no existe, generar
     un frame vacío con `EVENT_SCHEMA` para mantener consistencia.
   ```python
   events = repo.load_or_empty()
   ```

4. CRUD persistente  
   - Ahora: `add_*` solo muta listas.  
   - Cambio: reemplazar esas funciones por operaciones CRUD que actualicen
     el DataFrame persistido y luego reconstruyan el `Wallet`.
   ```python
   repo.add_event(EventSpec(...))
   repo.update_event(event_id, EventSpec(...))
   repo.remove_event(event_id)
   ```

5. Mapear frecuencia a `CashFlow`  
   - Ahora: la frecuencia está implícita en qué método se llama.  
   - Cambio: convertir cada fila del parquet a un `CashFlowSpec`
     (`frequency` -> clase concreta) para ensamblar los objetos en tiempo
     de ejecución.
   ```python
   spec = CashFlowSpec.from_row(row)
   cash_flow = spec.to_cash_flow()
   ```

6. Deltas por escenario  
   - Ahora: escenarios tendrían que duplicar filas.  
   - Cambio: mantener el parquet como baseline y guardar overrides en
     estructuras separadas o columnas dedicadas para que `ScenarioLoader`
     pueda aplicar solo diferencias.
   ```python
   repo.save_delta("raise_plan", FlowDelta(...))
   ```

7. Validaciones y pruebas  
   - Ahora: no hay validaciones ni tests para persistencia.  
   - Cambio: antes de escribir, validar tipos y fechas; cubrir con tests
     de `add/update/delete` y reload idempotente para asegurar integridad.
