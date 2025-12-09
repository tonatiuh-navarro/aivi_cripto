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

### Evaluar y optimizar
- Evaluar por splits (pre_out_of_time/train/test):
```python
from utils.strategy_utils import evaluate_strategy
pre_oos, train_res, test_res = evaluate_strategy(
    market_df=market_df,
    stage_cfgs=stage_cfgs,
)
```
- Optimizar hiperparámetros con búsqueda grid/random:
```python
from utils.strategy_utils import optimize_strategy
from utils.strategy_utils import trials_to_dataframe

search_space = {
    ("entry", "fast"): [5, 7, 10],
    ("entry", "slow"): [12, 14, 20],
    ("target_price", "multiplier"): [2.0, 3.0],
    ("stop_loss", "multiplier"): [1.0, 1.5, 2.0],
}
best_params, best_metrics, trials = optimize_strategy(
    market_df=market_df,
    base_stages=stage_cfgs[:3],
    search_space=search_space,
    sampler="grid",
    objective="total_return",
)
trials_df = trials_to_dataframe(trials)
```

## Relación con `binance/`
Las implementaciones reflejan `binance/strategies` para usarlas fuera del ETL/Lean. Si amplías o modificas las etapas, mantén ambas carpetas alineadas o migra el código común a un solo módulo compartido.
