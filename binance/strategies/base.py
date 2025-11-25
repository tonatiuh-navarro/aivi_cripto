import polars as pl


class BaseStage:
    def fit(self, frame: pl.DataFrame):
        return self

    def apply(self, frame: pl.DataFrame) -> pl.DataFrame:
        raise NotImplementedError

    def fit_apply(self, frame: pl.DataFrame) -> pl.DataFrame:
        return self.fit(frame).apply(frame)
