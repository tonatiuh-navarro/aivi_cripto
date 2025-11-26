import polars as pl
from ..base import BaseStage


class SplitDataSets(BaseStage):
    def __init__(
        self,
        pre_out_of_time_pct: float = 0.2,
        train_pct: float = 0.6,
        test_pct: float = 0.2,
    ):
        self.pre_out_of_time_pct = pre_out_of_time_pct
        self.train_pct = train_pct
        self.test_pct = test_pct

    def transform(self, frame: pl.DataFrame) -> pl.DataFrame:
        total = frame.height
        if total == 0:
            return frame.with_columns(pl.lit(None).alias("data_set"))

        # Normaliza proporciones para evitar suma distinta de 1.0
        total_pct = self.pre_out_of_time_pct + self.train_pct + self.test_pct
        if total_pct <= 0:
            raise ValueError("Las proporciones deben ser positivas")

        pre_cut = int(total * self.pre_out_of_time_pct)
        train_cut = pre_cut + int(total * self.train_pct)

        return (
            frame
            .sort("open_time")
            .with_row_count(name="_row_idx")
            .with_columns(
                pl.when(pl.col("_row_idx") < pre_cut)
                .then(pl.lit("pre_out_of_time"))
                .when(pl.col("_row_idx") < train_cut)
                .then(pl.lit("train"))
                .otherwise(pl.lit("test"))
                .alias("data_set")
            )
            .drop("_row_idx")
        )


def build(**params):
    return SplitDataSets(**params)
