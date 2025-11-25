# Wallet Overview Layout Update Plan

## Objetivo
Reorganizar la vista principal (actual “Overview”, futura “Actions”) para
que el flujo sea:

1. Seleccionar/crear wallet en la parte superior (ya existente).
2. Sección principal dedicada a agregar/editar acciones (eventos).
3. Debajo, mostrar la información agregada de la wallet (totales,
   balances, alertas o comparaciones si hacen sentido aquí).
4. Eliminar el bloque inferior de notificaciones para mantener la vista
   enfocada.

## Plan Detallado

### 1. Encabezado (Wallet selector)
- Mantener el dropdown de wallets y el botón “Nueva wallet”. Se podría
  mover a un componente `WalletSelector` reusable para Actions/Analysis.
- Considerar mostrar breve info de la wallet seleccionada (saldo inicial,
  fecha de referencia) justo al lado del selector para contexto rápido.

### 2. Sección de acciones (Eventos)
- Mover `EventsTable` (o un nuevo componente ActionsBoard) justo debajo
  del selector con ancho completo.  
- Desglose:
  - Botón “Nueva acción” (ya existe).
  - Select + botón “Ejecutar acción” (ya existe).
  - Tabla con columnas de concepto/monto/frecuencia/fechas.
  - Acciones de editar/eliminar/seleccionar.
- Esta sección debe ocupar el bloque principal, reemplazando donde antes
  estaban las tarjetas de stats y el chart.

### 3. Información de la wallet
- Debajo de la sección de eventos, colocar un bloque que muestre:
  - Tarjetas con totales (ingresos planeados, gastos, saldo final).
  - Opcional: un mini resumen del futuro balance o un sparkline simple.
  - Alertas de la wallet (lo que hoy está en `SecurityStatus`).
- Si el chart sigue siendo útil, moverlo aquí pero a una sola columna
  para que acompañe los stats de la wallet. También puede incluir el
  resultado del `ScenarioService.compare` si es relevante.

### 4. Eliminar Notifications
- Quitar el componente `Notifications` de esta página para evitar
  distracciones. Las notificaciones/global alerts pueden vivir en otra
  sección (Analysis, sidebar, etc.).
- Si necesitas mantener algún aviso corto (ej. errores de guardado),
  usar toasts/snackbar en vez del bloque completo.

### 5. Ajustes visuales
- Verificar que el layout preserve buen espaciado al tener sólo dos
  secciones (acciones + info).  
- Considerar dividir la info de la wallet en tarjetas (grid) para evitar
  que se vea vacía cuando haya pocos datos.
- En el panel derecho (donde hoy está el widget), mostrar el balance
  total proyectado de la wallet para la `end_date` seleccionada. El hook
  puede calcularlo con `summary_report` o usando el balance final del
  comparativo. El reloj se reubica en pequeño junto a la fecha mostrada,
  para conservar la referencia temporal sin ocupar todo el panel.

### 6. Implementación sugerida

1. Crear un nuevo componente `WalletInfoPanel` que reciba `stats`,
   `chart`, `alerts` y los renderice en un grid debajo de eventos.
2. Renderizar `EventsTable` inmediatamente después del selector.
3. Eliminar `DashboardControls`, `DashboardStat`, `DashboardChart`,
   `SecurityStatus`, `Notifications` del componente `app/page.tsx`.
   Reusar `DashboardControls` sólo si se necesita cambiar escenarios en
   esta misma vista; si no, moverlo a Analysis.
4. `useWalletDashboard` seguirá proporcionando stats/alerts en caso de
   que quieras mostrarlos, pero la sección principal se centra ahora en
   CRUD de acciones.
5. Testear el flujo: crear/editar/eliminar acciones y validar que la
   sección de info se actualiza (si muestra totales).
