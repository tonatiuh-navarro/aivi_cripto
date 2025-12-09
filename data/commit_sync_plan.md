# Plan para organizar commits y dejar el remoto al corriente

## Objetivo
Publicar al remoto los cambios pendientes (docs y código) en commits claros, atómicos y con mensajes consistentes.

## Preparativos
- `git status` para listar archivos modificados y asegurarte de no incluir secretos.
- `git diff` y `git diff --cached` para revisar el contenido antes y después de stage.
- `git fetch --all` para tener la referencia actualizada del remoto.

## Agrupar cambios en commits atómicos
- **Docs/README**: todos los cambios de documentación (ej. binance/README.md, data/README.md, airflow_home/README.md).
- **Código por feature**: separa por DAGs, ETL, alertas, estrategias, API, dashboard, etc.
- **Infra/scripts**: cambios en scripts de Airflow o helpers bash.
- **Datos de config**: entradas en `data/*.json` o `.env.example` si aplica.

## Secuencia sugerida
1) Crear/actualizar rama local a partir de main: `git checkout main && git pull`.  
2) Rama de trabajo si se requiere PR: `git checkout -b chore/docs-sync` (o similar).  
3) Stage y commit por grupo:
   - `git add binance/README.md data/README.md airflow_home/README.md`
   - `git commit -m "docs: alinear readmes con ETL y dags"`
   - Repetir por grupo de cambios pendiente, usando mensajes descriptivos.
4) Rebase interactivo (si la rama ya tiene commits) para ordenar y limpiar: `git rebase -i origin/main`.
5) Verificar historial: `git log --oneline -5`.
6) Push al remoto: `git push -u origin <rama>`.
7) Abrir PR con resumen breve (qué cambió y por qué) y checklist de pruebas.

## Formato de mensajes de commit
- Prefijo por tipo (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).
- Mensaje en imperativo y conciso. Ejemplos:
  - `docs: alinear readmes de etl y airflow`
  - `feat: agregar alerta de señales por ticker`
  - `fix: corregir cálculo de atr en market frame`
  - `chore: limpiar scripts de arranque de airflow`

## Checklist antes de subir
- Lint/tests relevantes corrieron o fueron evaluados.
- No se suben `.env`, credenciales ni artefactos grandes.
- `git status` limpio tras los commits.
