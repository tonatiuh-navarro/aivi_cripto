# Binance Exploration & Feature Engineering Plan

## 1. Objetivo
Convertir la pestaña **Devices** en un laboratorio para estudiar la API
de Binance, familiarizarnos con sus respuestas y construir un catálogo de
features reutilizables (EMA, RSI, etc.) dentro del directorio
`binance/features`.

## 2. Preparación

1. **Variables de entorno**  
   - Guardar API Key y Secret en `.env.local`/`.env` para evitar hardcode
     en scripts/notebooks.  
   - El código Python debe tomar las claves vía `os.getenv`.

2. **Directorio de trabajo**  
   - `/binance/explore_binance.py`: script base para pruebas
     programáticas.  
   - `/binance/binance_exploration.ipynb`: notebook para análisis
     interactivo.  
   - `/binance/features/`: subdirectorio donde vivirá cada indicador.

## 3. Exploración de la API

1. **Script (`explore_binance.py`)**  
   - Helpers para firmas HMAC y requests autenticados.  
   - Funciones mínimas: `server_time`, `account_info`, `recent_trades`,
     `klines`.  
   - Uso como CLI rápido para validar que las claves funcionan.

2. **Notebook (`binance_exploration.ipynb`)**  
   - Celdas para consultar el tiempo del servidor, precios, balances,
     trades.  
   - Conversión a DataFrames para inspeccionar estructuras y preparar los
     datos que consumirán los features.  
   - Secciones TODO para documentar dudas o endpoints pendientes.

## 4. Directorio `features`

Objetivo: tener scripts auto-contenidos, sin dependencias circulares, que
tomen datos crudos y regresen indicadores listos para usar en backtests.

### 4.1 Estructura sugerida

```
binance/features/
  __init__.py
  base_feature.py        # clases utilitarias
  ema.py
  rsi.py
  atr.py
  volatility.py
```

Cada archivo debe exponer una función principal (ej. `compute_ema(df,
period=20)`) que:
1. Reciba DataFrame o Series con columnas estándar (`open`, `high`,
   `low`, `close`, `volume`, `timestamp`).  
2. Devuelva la serie calculada y, de ser necesario, agregue columnas al
   DataFrame original.

### 4.2 Ideas de features optimizados

1. **EMA / SMA / WMA**  
   - Usar `pandas.Series.ewm` o `numpy` vectorizado para evitar bucles.  
   - Permitir múltiples periodos en una sola llamada (devuelve dict de
     columnas).  
   - Opción `inplace` para controlar memoria.

2. **RSI / Stochastic RSI**  
   - Basarse en cambios positivos/negativos precomputados para minimizar
     pasos.  
   - Exponer parámetro `method` (`wilders`, `sma`) para adaptarse a
     distintas escuelas de trading.

3. **ATR / Volatility**  
   - Calcular `true_range` una sola vez y reutilizarlo (ATR, NATR,
     Donchian channels).  
   - Permitir modo “rolling window” configurable.

4. **Momentum & Macro Features**  
   - `roc`, `mfi`, `obv`, `vwap`.  
   - Estrategias que combinen precios con indicadores on-chain o con
     otras divisas (multi-stream support).

5. **Optimización / Lote**  
   - Diseñar los features para aceptar DataFrames con múltiples símbolos
     (multi-index) y procesar en vector.  
   - Soportar tipos `polars` en el futuro para acelerar (opcional).

### 4.3 Buenas prácticas

- Documentar cada feature con docstring tipo NumPy (inputs, outputs,
  ejemplo).  
- Incluir tests unitarios simples con data sintética en el futuro.  
- Mantener dependencias ligeras (`pandas`, `numpy`); evitar TA-Lib para
  no agregar compilación extra.

## 5. Próximos Pasos

1. Completar el script y notebook con ejemplos reales (balances, klines
   de BTCUSDT, etc.).  
2. Crear el paquete `features` con `ema.py` y `rsi.py` como MVP.  
3. Integrar en la pestaña Devices un panel que permita:
   - Seleccionar símbolo/intervalo.  
   - Descargar datos desde Binance.  
   - Aplicar uno o varios features (EMA, RSI) y visualizar resultados.  
4. Preparar hooks/backend en FastAPI para cachear datos descargados y
   servirlos al frontend.  
5. Documentar cómo reutilizar los features en backtests o notebooks.

Con este plan tendremos un flujo claro: obtenemos datos de Binance,
entendemos su estructura a través del script/notebook y generamos
indicadores optimizados dentro de `binance/features`, listos para
reutilizar en análisis o pruebas de estrategias.*** End Patch
