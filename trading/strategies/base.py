import polars as pl
from sklearn.base import BaseEstimator, TransformerMixin


class BaseStage(BaseEstimator, TransformerMixin):
    def fit(self, frame: pl.DataFrame, y=None):  # noqa: D401
        """No-op fit for compatibility with sklearn Pipeline."""
        return self

    def transform(self, frame: pl.DataFrame) -> pl.DataFrame:
        raise NotImplementedError
