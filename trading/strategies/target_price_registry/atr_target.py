import polars as pl
from ..base import BaseStage


class ATRTarget(BaseStage):
    def __init__(self, multiplier: float):
        self.multiplier = multiplier

    def transform(self, frame: pl.DataFrame) -> pl.DataFrame:
        target = (
            pl.when(pl.col('trade_event'))
            .then(
                pl.col('close') + pl.col('signal') * pl.col('atr') * self.multiplier
            )
        )
        return frame.with_columns(target.alias('tp_price'))


def build(**params):
    return ATRTarget(**params)
