import polars as pl
from datetime import timedelta
from importlib import import_module


def prepare_market_frame(
    klines: list,
    atr_period: int,
    months: int,
) -> pl.DataFrame:
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
    print(
        f"Datos limpios: {frame.height:,} filas, {recent.height:,} del periodo."
    )
    return recent


def load_stage(kind: str, name: str, params: dict):
    path = f'trading.strategies.{kind}_registry.{name}'
    module = import_module(path)
    builder = getattr(module, 'build')
    stage = builder(**params)
    print(f'{kind} {name} listo')
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
    return out


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
