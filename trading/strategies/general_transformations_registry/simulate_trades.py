import polars as pl
from ..base import BaseStage


class SimulateTrades(BaseStage):
    def __init__(self):
        """No params needed; consumes columns from prior stages."""

    def transform(self, frame: pl.DataFrame) -> pl.DataFrame:
        trade_rows = frame.filter(pl.col('trade_event')).sort('open_time')
        if trade_rows.height < 2:
            return frame.with_columns([
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
            segment = frame.filter(
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
        exit_df = pl.DataFrame(
            exit_records,
            schema={
                'open_time': pl.Datetime('ms'),
                'strategy_return': pl.Float64,
                'trade_label': pl.Utf8,
                'exit_reason': pl.Utf8,
            }
        )
        return frame.join(exit_df, on='open_time', how='left')


def build(**_):
    return SimulateTrades()
