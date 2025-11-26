# Trading

Espacio liviano para experimentar con estrategias en Polars sin depender del pipeline completo de `binance/`. Incluye los mismos bloques modulares (entrada/target/stop) y un notebook rápido.

## Contenido
- `exploration.ipynb`: cuaderno de exploración manual con klines y señales.
- `strategies/`: patrón de etapas (`BaseStage`) con:
  - Entrada: `entry_registry/ma_signal.py` (cruce de medias móviles).
  - Salida: `target_price_registry/atr_target.py` (take profit por ATR) y `stop_loss_registry/atr_stop.py` (stop por ATR).

## Uso rápido
- Cada etapa es un transformer de scikit-learn y opera sobre un `pl.DataFrame` con `open_time`, `close` y (para TP/SL) una columna `atr`.
- Ejemplo mínimo:
```python
import polars as pl
from trading.strategies.entry_registry.ma_signal import MASignal
from trading.strategies.target_price_registry.atr_target import ATRTarget
from trading.strategies.stop_loss_registry.atr_stop import ATRStop

# df debe venir ordenado y, para TP/SL, con atr precalculado
df = MASignal(fast=10, slow=30).transform(df)
df = ATRTarget(multiplier=2.0).transform(df)
df = ATRStop(multiplier=1.5).transform(df)
```
- Para limpiar klines y simular trades puedes reutilizar `utils/strategy_utils.py`, que expone `apply_pipeline` para ensamblar etapas arbitrarias y `build_strategy_frame` para simular salidas.

### Pipeline por nombres
```python
from utils.strategy_utils import apply_pipeline, build_strategy_frame

stage_cfgs = [
    {'kind': 'entry', 'name': 'ma_signal', 'params': {'fast': 7, 'slow': 14}},
    {'kind': 'target_price', 'name': 'atr_target', 'params': {'multiplier': 3.0}},
    {'kind': 'stop_loss', 'name': 'atr_stop', 'params': {'multiplier': 1.5}},
    {'kind': 'general_transformations', 'name': 'simulate_trades', 'params': {}},
]

pipeline_df = apply_pipeline(df=market_df, stages=stage_cfgs)
strategy_df = build_strategy_frame(market_df=market_df, stages=stage_cfgs)
```

## Relación con `binance/`
Las implementaciones reflejan `binance/strategies` para usarlas fuera del ETL/Lean. Si amplías o modificas las etapas, mantén ambas carpetas alineadas o migra el código común a un solo módulo compartido.
