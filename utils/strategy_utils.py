import polars as pl
from datetime import timedelta
from importlib import import_module
import itertools
import random
import time

from utils.logging_utils import setup_logger_for_child


def prepare_market_frame(
    klines: list,
    atr_period: int,
    months: int,
) -> pl.DataFrame:
    logger = setup_logger_for_child(
        parent_name='strategy_utils',
        child_name='prepare_market_frame',
        log_level='INFO',
        console=False,
    )
    schema = {
        'open_time': pl.Int64,
        'open': pl.Float64,
        'high': pl.Float64,
        'low': pl.Float64,
        'close': pl.Float64,
        'volume': pl.Float64,
        'close_time': pl.Int64,
        'quote_asset_volume': pl.Float64,
        'number_of_trades': pl.Int64,
        'taker_buy_base_asset_volume': pl.Float64,
        'taker_buy_quote_asset_volume': pl.Float64,
        'ignore': pl.Float64,
    }
    if not klines:
        raise ValueError("No hay datos de klines para procesar")
    frame = pl.DataFrame(klines, schema=schema)
    frame = frame.with_columns(
        pl.col('open_time').cast(pl.Datetime('ms')).alias('open_time')
    )
    prev_close = pl.col('close').shift(1)
    true_range = pl.max_horizontal([
        pl.col('high') - pl.col('low'),
        (pl.col('high') - prev_close).abs(),
        (pl.col('low') - prev_close).abs()
    ])
    atr_expr = true_range.rolling_mean(
        window_size=atr_period,
        min_periods=1
    )
    frame = frame.sort('open_time').with_columns([
        prev_close.alias('prev_close'),
        true_range.alias('true_range'),
        atr_expr.alias('atr')
    ])
    max_time = frame.select(pl.col('open_time').max()).item()
    cutoff = max_time - timedelta(days=30 * months)
    recent = frame.filter(pl.col('open_time') >= cutoff)
    logger.info(
        f"Datos limpios: {frame.height:,} filas, {recent.height:,} del periodo."
    )
    return recent


def load_stage(kind: str, name: str, params: dict):
    logger = setup_logger_for_child(
        parent_name='strategy_utils',
        child_name='load_stage',
        log_level='INFO',
        console=False,
    )
    path = f'trading.strategies.{kind}_registry.{name}'
    module = import_module(path)
    builder = getattr(module, 'build')
    stage = builder(**params)
    logger.info(f'{kind} {name} listo')
    return stage


def apply_pipeline(
    df: pl.DataFrame,
    stages: list[dict],
) -> pl.DataFrame:
    if not stages:
        return df
    out = df
    for cfg in stages:
        kind = cfg.get('kind')
        name = cfg.get('name')
        params = cfg.get('params', {})
        if not kind or not name:
            raise ValueError("Cada etapa requiere 'kind' y 'name'")
        stage = load_stage(kind, name, params)
        out = stage.transform(out)
        if not isinstance(out, pl.DataFrame):
            return out
    return out


def evaluate_strategy(
    market_df: pl.DataFrame,
    stage_cfgs: list[dict],
    split_params: dict | None = None,
) -> tuple[object, object, object]:
    split_stage = [{
        "kind": "general_transformations",
        "name": "split_data_sets",
        "params": split_params or {},
    }]
    split_df = apply_pipeline(df=market_df, stages=split_stage)
    if not isinstance(split_df, pl.DataFrame) or "data_set" not in split_df.columns:
        raise ValueError("split_data_sets debe devolver DataFrame con columna data_set")
    outputs = []
    for label in ("pre_out_of_time", "train", "test"):
        subset = split_df.filter(pl.col("data_set") == label)
        outputs.append(apply_pipeline(df=subset, stages=stage_cfgs))
    return tuple(outputs)


def _range_to_list(entry: dict) -> list:
    start = entry.get("min")
    end = entry.get("max")
    step = entry.get("step")
    if start is None or end is None or step is None or step == 0:
        raise ValueError("range entry requires min, max, step")
    values = []
    current = start
    while (step > 0 and current <= end) or (step < 0 and current >= end):
        values.append(current)
        current = current + step
    return values


def _normalize_search_space(search_space: dict) -> tuple[list, list]:
    items = []
    for key, val in search_space.items():
        if isinstance(val, dict):
            items.append((key, _range_to_list(val)))
        else:
            values = list(val)
            if not values:
                raise ValueError(f"Empty search space for {key}")
            items.append((key, values))
    keys, values = zip(*items)
    return list(keys), list(values)


def optimize_strategy(
    market_df: pl.DataFrame,
    base_stages: list[dict],
    search_space: dict,
    sampler: str = "grid",
    max_iters: int | None = None,
    max_time: float | None = None,
    seed: int | None = None,
    log=None,
    objective: str = "total_return",
    early_stop: int | None = None,
) -> tuple[dict | None, dict | None, list]:
    logger = log or setup_logger_for_child(
        parent_name='strategy_utils',
        child_name='optimize_strategy',
        log_level='INFO',
        console=True,
    )
    if sampler not in {"grid", "random", "bayes"}:
        raise ValueError("sampler must be grid, random or bayes")
    random.seed(seed)
    keys, values = _normalize_search_space(search_space)
    grid = list(itertools.product(*values))
    combos = grid
    if sampler == "random" and max_iters:
        combos = random.sample(grid, min(max_iters, len(grid)))
    if sampler == "bayes":
        combos = grid  # placeholder; use full grid until bayes sampler is added
    best_score = None
    best_params = None
    best_metrics = None
    trials = []
    start = time.time()
    no_improve = 0
    total = len(combos)
    logger.info(f"Combinaciones a evaluar: {total}")
    for idx, combo in enumerate(combos):
        stages = [dict(s) for s in base_stages]
        param_map: dict[str, dict] = {}
        for (kind, param), value in zip(keys, combo):
            for s in stages:
                if s.get("kind") == kind:
                    s.setdefault("params", {})[param] = value
            param_map.setdefault(kind, {})[param] = value
        stages.extend([
            {"kind": "general_transformations", "name": "simulate_trades", "params": {}},
            {"kind": "general_transformations", "name": "metrics_summary", "params": {"output_format": "dict"}},
        ])
        metrics = apply_pipeline(df=market_df, stages=stages)
        trial = {"trial_id": idx, "params": param_map, "metrics": metrics}
        trials.append(trial)
        score = metrics.get(objective) if isinstance(metrics, dict) else None
        if score is not None and (best_score is None or score > best_score):
            best_score = score
            best_params = param_map
            best_metrics = metrics
            no_improve = 0
            logger.info(f"Nuevo mejor {objective}: {best_score}")
        else:
            no_improve += 1
        elapsed = time.time() - start
        if total:
            progress = (idx + 1) / total
            eta = None
            if progress > 0:
                eta = (elapsed / progress) - elapsed
            if (idx + 1) % max(1, total // 10) == 0:
                msg = f"Progreso {idx + 1}/{total}"
                if eta is not None:
                    msg += f", ETA {eta:.1f}s"
                logger.info(msg)
        if early_stop and no_improve >= early_stop:
            logger.info("Early stop por falta de mejora")
            break
        if max_time and elapsed >= max_time:
            logger.info("Tiempo máximo alcanzado")
            break
    return best_params, best_metrics, trials


def trials_to_dataframe(trials: list) -> pl.DataFrame:
    rows = []
    for trial in trials:
        metrics = trial.get("metrics") or {}
        params = trial.get("params") or {}
        row = {"trial_id": trial.get("trial_id")}
        for stage, values in params.items():
            for key, val in values.items():
                row[f"{stage}_{key}"] = val
        row.update(metrics if isinstance(metrics, dict) else {})
        rows.append(row)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def build_strategy_frame(
    market_df: pl.DataFrame,
    stages: list[dict],
) -> pl.DataFrame:
    df = apply_pipeline(df=market_df, stages=stages)
    if 'tp_price' not in df.columns:
        df = df.with_columns(pl.lit(None).alias('tp_price'))
    if 'sl_price' not in df.columns:
        df = df.with_columns(pl.lit(None).alias('sl_price'))
    return df
