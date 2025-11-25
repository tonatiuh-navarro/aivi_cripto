import polars as pl
from datetime import timedelta
from importlib import import_module


def prepare_market_frame(
    klines: list,
    atr_period: int,
    months: int,
) -> pl.DataFrame:
    columns = [
        'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
        'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume',
        'ignore'
    ]
    frame = pl.DataFrame(klines, schema=columns)
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    cast_exprs = [
        pl.col('open_time').cast(pl.Datetime('ms')).alias('open_time'),
        *[pl.col(col).cast(pl.Float64).alias(col) for col in numeric_cols]
    ]
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
        *cast_exprs,
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
    path = f'py4fi2nd.code.z_1.binance.strategies.{kind}_registry.{name}'
    module = import_module(path)
    builder = getattr(module, 'build')
    stage = builder(**params)
    print(f'{kind} {name} listo')
    return stage


def run_stages(
    market_df: pl.DataFrame,
    entry_cfg: dict,
    target_cfg: dict,
    stop_cfg: dict,
) -> pl.DataFrame:
    df = market_df
    for kind, cfg in (
        ('entry', entry_cfg),
        ('target_price', target_cfg),
        ('stop_loss', stop_cfg),
    ):
        stage = load_stage(kind, cfg.get('name'), cfg.get('params', {}))
        df = stage.apply(df)
    return df


def simulate_trades(df: pl.DataFrame) -> pl.DataFrame:
    trade_rows = df.filter(pl.col('trade_event')).sort('open_time')
    if trade_rows.height < 2:
        print('Sin trades para simular')
        return df.with_columns([
            pl.lit(None).alias('strategy_return'),
            pl.lit(None).alias('trade_label'),
            pl.lit(None).alias('exit_reason')
        ])
    exit_records = []
    for idx in range(1, trade_rows.height):
        entry = trade_rows.row(idx - 1, named=True)
        exit_row = trade_rows.row(idx, named=True)
        side = entry['signal']
        entry_price = entry['close']
        target = entry.get('tp_price')
        stop = entry.get('sl_price')
        if side == 0 or entry_price is None:
            continue
        entry_time = entry['open_time']
        exit_time = exit_row['open_time']
        segment = df.filter(
            (pl.col('open_time') > entry_time) &
            (pl.col('open_time') <= exit_time)
        ).select(['open_time', 'high', 'low', 'close'])
        exit_price = exit_row['close']
        exit_reason = 'crossover'
        for bar in segment.iter_rows(named=True):
            if target is not None and side == 1 and bar['high'] >= target:
                exit_price = target
                exit_reason = 'take_profit'
                exit_time = bar['open_time']
                break
            if stop is not None and side == 1 and bar['low'] <= stop:
                exit_price = stop
                exit_reason = 'stop_loss'
                exit_time = bar['open_time']
                break
            if target is not None and side == -1 and bar['low'] <= target:
                exit_price = target
                exit_reason = 'take_profit'
                exit_time = bar['open_time']
                break
            if stop is not None and side == -1 and bar['high'] >= stop:
                exit_price = stop
                exit_reason = 'stop_loss'
                exit_time = bar['open_time']
                break
        trade_return = ((exit_price / entry_price) - 1) * side
        exit_records.append({
            'open_time': exit_time,
            'strategy_return': trade_return,
            'trade_label': 'win' if trade_return > 0 else 'loss',
            'exit_reason': exit_reason
        })
    print(f'Se simularon {len(exit_records)} trades')
    exit_df = pl.DataFrame(
        exit_records,
        schema={
            'open_time': pl.Datetime('ms'),
            'strategy_return': pl.Float64,
            'trade_label': pl.Utf8,
            'exit_reason': pl.Utf8,
        }
    )
    return df.join(exit_df, on='open_time', how='left')


def build_strategy_frame(
    market_df: pl.DataFrame,
    entry: dict,
    target: dict,
    stop: dict,
) -> pl.DataFrame:
    df = run_stages(
        market_df=market_df,
        entry_cfg=entry,
        target_cfg=target,
        stop_cfg=stop,
    )
    df = simulate_trades(df)
    if 'tp_price' not in df.columns:
        df = df.with_columns(pl.lit(None).alias('tp_price'))
    if 'sl_price' not in df.columns:
        df = df.with_columns(pl.lit(None).alias('sl_price'))
    return df
