import polars as pl
from ..base import BaseStage


class MASignal(BaseStage):
    def __init__(self, fast: int, slow: int):
        self.fast = fast
        self.slow = slow

    def apply(self, frame: pl.DataFrame) -> pl.DataFrame:
        ma_fast = pl.col('close').rolling_mean(window_size=self.fast)
        ma_slow = pl.col('close').rolling_mean(window_size=self.slow)
        signal = pl.when(ma_fast >= ma_slow).then(1).otherwise(-1)
        prev_signal = signal.shift(1).fill_null(0)
        trade_event = (signal != prev_signal) & prev_signal.is_in([1, -1])
        return (
            frame.sort('open_time')
            .with_columns([
                ma_fast.alias('ma_fast'),
                ma_slow.alias('ma_slow'),
                signal.alias('signal'),
                prev_signal.alias('signal_prev'),
                trade_event.alias('trade_event')
            ])
        )


def build(**params):
    return MASignal(**params)
